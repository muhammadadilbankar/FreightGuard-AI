"""Cache/provider/validation/fallback orchestration for Phase 8."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
import time

from ...domain.evidence import EvidenceVerdict, ValidatedEvidencePacket
from ...domain.explanations import (
    ExplanationCacheEntry,
    ExplanationFailureCode,
    ExplanationSettings,
    ExplanationSource,
    FinalExplanationRecord,
    GeneratedExplanation,
    GenerationMode,
    ProviderGenerationResult,
    TokenUsage,
    ValidationStatus,
)
from .cache import (
    ExplanationCache,
    build_cache_key,
    request_sha256,
    response_schema_fingerprint,
)
from .costing import estimate_cost_usd
from .errors import ExplanationCacheError, ProviderCallError
from .fallbacks import render_fallback_explanation
from .prompts import build_explanation_prompt
from .providers import ExplanationProvider
from .requests import build_grounded_request
from .validation import validate_generated_explanation


def generate_explanation(
    packet: ValidatedEvidencePacket,
    provider: ExplanationProvider,
    cache: ExplanationCache,
    settings: ExplanationSettings,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> FinalExplanationRecord:
    request = build_grounded_request(packet, settings.prompt_version)
    prompt = build_explanation_prompt(request, settings.prompt_version)
    identity = provider.identity
    cache_key = build_cache_key(request, identity)
    if request.verdict == EvidenceVerdict.UNEXPLAINED:
        return _template_record(packet, request, cache_key, settings)
    if settings.mode == GenerationMode.TEMPLATE:
        return _template_record(packet, request, cache_key, settings)

    try:
        cached = cache.get(cache_key, request, identity) if settings.cache_enabled else None
    except ExplanationCacheError:
        if settings.mode == GenerationMode.REPLAY:
            raise
        return _fallback_record(
            packet,
            request,
            cache_key,
            settings,
            (ExplanationFailureCode.CACHE_ENTRY_INVALID,),
            identity=identity,
        )
    if cached is not None:
        validation = validate_generated_explanation(request, cached.generated)
        if not validation.accepted:
            if settings.mode == GenerationMode.REPLAY:
                raise ExplanationCacheError("Replay cache entry failed grounding validation.")
            return _fallback_record(
                packet,
                request,
                cache_key,
                settings,
                (ExplanationFailureCode.CACHE_ENTRY_INVALID,),
                identity=identity,
            )
        return FinalExplanationRecord(
            **_authority_fields(packet),
            reason=validation.reason or "",
            cited_note_ids=validation.cited_note_ids,
            explanation_source=ExplanationSource.CACHE,
            provider=identity.provider,
            model=identity.model,
            prompt_version=settings.prompt_version,
            cache_key=cache_key,
            cache_hit=True,
            provider_attempts=0,
            validation_status=ValidationStatus.ACCEPTED,
            failure_codes=(),
            usage=TokenUsage(),
            original_generation_usage=cached.usage,
            estimated_cost_usd=estimate_cost_usd(TokenUsage(), settings),
            pricing_snapshot_date=settings.pricing_snapshot_date,
            latency_ms=0,
        )
    if settings.mode == GenerationMode.REPLAY:
        raise ExplanationCacheError(
            f"Replay cache miss for {request.route} {request.week_of.isoformat()}."
        )

    result: ProviderGenerationResult | None = None
    attempts = 0
    failure: ExplanationFailureCode | None = None
    while attempts < settings.max_attempts:
        attempts += 1
        try:
            result = provider.generate(prompt, GeneratedExplanation)
        except ProviderCallError as exc:
            failure = exc.code
            if exc.transient and attempts < settings.max_attempts:
                sleeper(min(0.1 * (2 ** (attempts - 1)), 1.0))
                continue
            break
        if result.refusal is not None:
            failure = ExplanationFailureCode.PROVIDER_REFUSAL
            break
        if result.parsed is None:
            failure = ExplanationFailureCode.STRUCTURED_OUTPUT_MISSING
            break
        validation = validate_generated_explanation(request, result.parsed)
        if not validation.accepted:
            return _fallback_record(
                packet,
                request,
                cache_key,
                settings,
                validation.failure_codes,
                attempts=attempts,
                result=result,
                identity=identity,
            )
        entry = ExplanationCacheEntry(
            cache_key=cache_key,
            provider_identity=identity,
            prompt_version=settings.prompt_version,
            request_sha256=request_sha256(request),
            schema_fingerprint=response_schema_fingerprint(),
            generated=result.parsed,
            usage=result.usage,
        )
        if settings.cache_enabled:
            cache.put(entry)
        return FinalExplanationRecord(
            **_authority_fields(packet),
            reason=validation.reason or "",
            cited_note_ids=validation.cited_note_ids,
            explanation_source=ExplanationSource.MODEL,
            provider=identity.provider,
            model=identity.model,
            prompt_version=settings.prompt_version,
            cache_key=cache_key,
            cache_hit=False,
            provider_attempts=attempts,
            validation_status=ValidationStatus.ACCEPTED,
            failure_codes=(),
            usage=result.usage,
            estimated_cost_usd=estimate_cost_usd(result.usage, settings),
            pricing_snapshot_date=settings.pricing_snapshot_date,
            provider_request_id=result.provider_request_id,
            latency_ms=result.latency_ms,
        )
    return _fallback_record(
        packet,
        request,
        cache_key,
        settings,
        (failure or ExplanationFailureCode.PROVIDER_PROTOCOL_ERROR,),
        attempts=attempts,
        result=result,
        identity=identity,
    )


def generate_explanations(
    packets: Sequence[ValidatedEvidencePacket],
    provider: ExplanationProvider,
    cache: ExplanationCache,
    settings: ExplanationSettings,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[FinalExplanationRecord, ...]:
    ordered = tuple(sorted(packets, key=lambda item: (item.candidate.route, item.candidate.week_of)))
    keys = [(item.candidate.route, item.candidate.week_of) for item in ordered]
    if not ordered or len(keys) != len(set(keys)):
        from .errors import ExplanationInputError

        raise ExplanationInputError("Explanation packets must be non-empty and unique.")
    if settings.mode == GenerationMode.TEMPLATE or all(
        packet.decision.verdict == EvidenceVerdict.UNEXPLAINED for packet in ordered
    ):
        return tuple(
            generate_explanation(packet, provider, cache, settings, sleeper=sleeper)
            for packet in ordered
        )
    with ThreadPoolExecutor(max_workers=settings.max_concurrency) as executor:
        futures = [
            executor.submit(
                generate_explanation,
                packet,
                provider,
                cache,
                settings,
                sleeper=sleeper,
            )
            for packet in ordered
        ]
        return tuple(future.result() for future in futures)


def _template_record(packet, request, cache_key, settings) -> FinalExplanationRecord:
    cited = _fallback_citations(request)
    return FinalExplanationRecord(
        **_authority_fields(packet),
        reason=render_fallback_explanation(request),
        cited_note_ids=cited,
        explanation_source=ExplanationSource.TEMPLATE,
        provider=None,
        model=None,
        prompt_version=settings.prompt_version,
        cache_key=cache_key,
        cache_hit=False,
        provider_attempts=0,
        validation_status=ValidationStatus.NOT_APPLICABLE,
        failure_codes=(),
        usage=TokenUsage(),
        estimated_cost_usd=estimate_cost_usd(TokenUsage(), settings),
        pricing_snapshot_date=settings.pricing_snapshot_date,
    )


def _fallback_record(
    packet,
    request,
    cache_key,
    settings,
    failure_codes,
    *,
    attempts: int = 0,
    result: ProviderGenerationResult | None = None,
    identity=None,
) -> FinalExplanationRecord:
    return FinalExplanationRecord(
        **_authority_fields(packet),
        reason=render_fallback_explanation(request),
        cited_note_ids=_fallback_citations(request),
        explanation_source=ExplanationSource.FALLBACK,
        provider=identity.provider if identity is not None else None,
        model=identity.model if identity is not None else None,
        prompt_version=settings.prompt_version,
        cache_key=cache_key,
        cache_hit=False,
        provider_attempts=attempts,
        validation_status=ValidationStatus.FALLBACK,
        failure_codes=tuple(sorted(set(failure_codes), key=lambda item: item.value)),
        usage=result.usage if result is not None else TokenUsage(),
        estimated_cost_usd=(
            estimate_cost_usd(result.usage if result is not None else TokenUsage(), settings)
        ),
        pricing_snapshot_date=settings.pricing_snapshot_date,
        provider_request_id=(result.provider_request_id if result is not None else None),
        latency_ms=(result.latency_ms if result is not None else 0),
    )


def _authority_fields(packet: ValidatedEvidencePacket) -> dict[str, object]:
    return {
        "route": packet.candidate.route,
        "week_of": packet.candidate.week_of,
        "verdict": packet.decision.verdict,
        "selected_note_id": packet.decision.selected_note_id,
        "supporting_note_ids": packet.decision.supporting_note_ids,
        "allowed_note_ids": packet.allowed_note_ids,
    }


def _fallback_citations(request) -> tuple[str, ...]:
    if request.verdict == EvidenceVerdict.JUSTIFIED:
        return (request.selected_note_id,) if request.selected_note_id else ()
    if request.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED:
        return request.allowed_note_ids[:1]
    return ()
