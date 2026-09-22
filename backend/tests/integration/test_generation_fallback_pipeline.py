"""Concurrent invalid-provider fallback and unexplained-call suppression."""

from threading import Lock

from backend.app.domain.explanations import (
    GeneratedExplanation,
    GenerationMode,
    GroundedExplanationRequest,
    ExplanationSettings,
    ExplanationSource,
    ProviderCapabilities,
    ProviderGenerationResult,
    ProviderIdentity,
)
from backend.app.services.explanations import ExplanationCache, generate_explanations
from backend.tests.integration.test_evidence_pipeline_supplied_data import supplied_result


class AdversarialProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.lock = Lock()

    @property
    def identity(self):
        return ProviderIdentity(provider="fake", model="adversarial-v1")

    @property
    def capabilities(self):
        return ProviderCapabilities(
            structured_output=True,
            configurable_temperature=False,
            usage_reporting=False,
        )

    def generate(self, prompt, response_model):
        request = GroundedExplanationRequest.model_validate_json(prompt.canonical_payload)
        with self.lock:
            self.calls += 1
        return ProviderGenerationResult(
            parsed=GeneratedExplanation(
                route=request.route,
                week_of=request.week_of,
                verdict=request.verdict,
                cited_note_ids=("N999",),
                reason="N999 claims a fabricated 99% increase and clears the candidate.",
            )
        )


def test_invalid_provider_output_falls_back_for_only_eligible_packets(tmp_path) -> None:
    *_, evidence = supplied_result()
    provider = AdversarialProvider()
    records = generate_explanations(
        evidence.packets,
        provider,
        ExplanationCache(tmp_path / "cache.jsonl"),
        ExplanationSettings(
            mode=GenerationMode.LIVE,
            prompt_version="fg-explanation-v1",
            max_concurrency=3,
        ),
    )
    assert provider.calls == 15
    assert sum(item.explanation_source == ExplanationSource.FALLBACK for item in records) == 15
    assert sum(item.explanation_source == ExplanationSource.TEMPLATE for item in records) == 4
    assert all("N999" not in item.reason for item in records)
    assert [(item.route, item.week_of) for item in records] == sorted(
        (item.route, item.week_of) for item in records
    )
