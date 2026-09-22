"""Cache, Decimal costing, mode, retry, and fallback orchestration tests."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.domain.explanations import (
    ExplanationFailureCode,
    ExplanationSettings,
    ExplanationSource,
    GeneratedExplanation,
    GenerationMode,
    ProviderCapabilities,
    ProviderGenerationResult,
    ProviderIdentity,
    TokenUsage,
)
from backend.app.services.explanations import (
    ExplanationCache,
    ExplanationCacheError,
    ProviderCallError,
    build_cache_key,
    build_grounded_request,
    estimate_cost_usd,
    generate_explanation,
)


class FakeProvider:
    def __init__(self, results=()) -> None:
        self.results = list(results)
        self.calls = 0

    @property
    def identity(self):
        return ProviderIdentity(provider="fake", model="fixed-v1")

    @property
    def capabilities(self):
        return ProviderCapabilities(
            structured_output=True,
            configurable_temperature=True,
            usage_reporting=True,
        )

    def generate(self, prompt, response_model):
        self.calls += 1
        value = self.results.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def settings(mode=GenerationMode.TEMPLATE, **changes):
    values = {
        "mode": mode,
        "prompt_version": "fg-explanation-v1",
        "max_attempts": 2,
        "max_concurrency": 2,
    }
    values.update(changes)
    return ExplanationSettings(**values)


def valid_result(packet):
    return ProviderGenerationResult(
        parsed=GeneratedExplanation(
            route=packet.candidate.route,
            week_of=packet.candidate.week_of,
            verdict=packet.decision.verdict,
            cited_note_ids=packet.allowed_note_ids,
            reason=(
                f"{packet.allowed_note_ids[0]} documents a route-specific "
                "transport-cost increase for this week."
            ),
        ),
        usage=TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120),
        provider_request_id="req_test",
        latency_ms=5,
    )


def test_costing_uses_decimal_and_handles_missing_rates() -> None:
    usage = TokenUsage(
        input_tokens=1000,
        cached_input_tokens=400,
        output_tokens=200,
        total_tokens=1200,
    )
    priced = settings(
        input_cost_per_1m_usd=Decimal("2"),
        cached_input_cost_per_1m_usd=Decimal("1"),
        output_cost_per_1m_usd=Decimal("8"),
        pricing_snapshot_date=date(2025, 1, 1),
    )
    assert estimate_cost_usd(usage, priced) == Decimal("0.0032")
    assert estimate_cost_usd(usage, settings()) is None
    assert estimate_cost_usd(TokenUsage(), settings()) == Decimal(0)


def test_cache_key_changes_with_prompt_or_model(justified_packet) -> None:
    request = build_grounded_request(justified_packet, "fg-explanation-v1")
    first = build_cache_key(request, ProviderIdentity(provider="fake", model="one"))
    second = build_cache_key(request, ProviderIdentity(provider="fake", model="two"))
    changed = request.model_copy(update={"prompt_version": "fg-explanation-v2"})
    assert first != second
    assert first != build_cache_key(changed, ProviderIdentity(provider="fake", model="one"))


def test_template_and_unexplained_never_call_provider(tmp_path, justified_packet, unexplained_packet) -> None:
    provider = FakeProvider()
    cache = ExplanationCache(tmp_path / "cache.jsonl")
    template = generate_explanation(justified_packet, provider, cache, settings())
    unexplained = generate_explanation(
        unexplained_packet, provider, cache, settings(GenerationMode.LIVE)
    )
    assert provider.calls == 0
    assert template.explanation_source == ExplanationSource.TEMPLATE
    assert unexplained.explanation_source == ExplanationSource.TEMPLATE


def test_valid_live_result_is_cached_and_replayed(tmp_path, justified_packet) -> None:
    provider = FakeProvider([valid_result(justified_packet)])
    cache = ExplanationCache(tmp_path / "cache.jsonl")
    live = generate_explanation(
        justified_packet, provider, cache, settings(GenerationMode.LIVE)
    )
    replay = generate_explanation(
        justified_packet, provider, cache, settings(GenerationMode.REPLAY)
    )
    assert live.explanation_source == ExplanationSource.MODEL
    assert replay.explanation_source == ExplanationSource.CACHE
    assert replay.usage.total_tokens == 0
    assert replay.original_generation_usage == live.usage
    assert provider.calls == 1


def test_replay_miss_fails(tmp_path, justified_packet) -> None:
    with pytest.raises(ExplanationCacheError, match="Replay cache miss"):
        generate_explanation(
            justified_packet,
            FakeProvider(),
            ExplanationCache(tmp_path / "missing.jsonl"),
            settings(GenerationMode.REPLAY),
        )


def test_invalid_live_content_falls_back_without_repair(tmp_path, justified_packet) -> None:
    bad = valid_result(justified_packet).model_copy(
        update={
            "parsed": GeneratedExplanation(
                route="wrong",
                week_of=justified_packet.candidate.week_of,
                verdict=justified_packet.decision.verdict,
                cited_note_ids=("N999",),
                reason="N999 invents 99% and claims the candidate was cleared from review.",
            )
        }
    )
    provider = FakeProvider([bad])
    record = generate_explanation(
        justified_packet,
        provider,
        ExplanationCache(tmp_path / "cache.jsonl"),
        settings(GenerationMode.LIVE),
    )
    assert record.explanation_source == ExplanationSource.FALLBACK
    assert provider.calls == 1
    assert ExplanationFailureCode.IDENTITY_MISMATCH in record.failure_codes


def test_transient_failure_retries_but_refusal_does_not(tmp_path, justified_packet) -> None:
    timeout = ProviderCallError(ExplanationFailureCode.PROVIDER_TIMEOUT, transient=True)
    provider = FakeProvider([timeout, valid_result(justified_packet)])
    record = generate_explanation(
        justified_packet,
        provider,
        ExplanationCache(tmp_path / "retry.jsonl"),
        settings(GenerationMode.LIVE),
        sleeper=lambda _: None,
    )
    assert record.explanation_source == ExplanationSource.MODEL
    assert provider.calls == 2

    refusing = FakeProvider([ProviderGenerationResult(parsed=None, refusal="no")])
    fallback = generate_explanation(
        justified_packet,
        refusing,
        ExplanationCache(tmp_path / "refusal.jsonl"),
        settings(GenerationMode.LIVE),
    )
    assert refusing.calls == 1
    assert fallback.failure_codes == (ExplanationFailureCode.PROVIDER_REFUSAL,)


def test_duplicate_cache_keys_are_rejected_on_read(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.jsonl"
    path.write_text('{"cache_key":"x"}\n{"cache_key":"x"}\n', encoding="utf-8")
    with pytest.raises(ExplanationCacheError):
        ExplanationCache(path).get(
            "x",
            object(),
            ProviderIdentity(provider="fake", model="one"),
        )
