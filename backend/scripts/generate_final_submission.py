"""Run Phases 2 through 8 and write the final grounded submission."""

from collections import Counter
from decimal import Decimal
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.core.logging import configure_logging
from backend.app.domain.evidence import EvidencePolicy, EvidenceVerdict, RetrievalConfig
from backend.app.domain.explanations import (
    ExplanationSettings,
    ExplanationSource,
    GenerationMode,
)
from backend.app.services.analytics import (
    AnalyticsError,
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.services.context import ContextCompilationError, compile_context_notes
from backend.app.services.evidence import (
    EvidenceError,
    build_candidate_queries,
    review_candidate_evidence,
)
from backend.app.services.explanations import (
    ExplanationCache,
    ExplanationError,
    generate_explanations,
)
from backend.app.services.explanations.providers import (
    OpenAIExplanationProvider,
    ReplayIdentityProvider,
    TemplateExplanationProvider,
)
from backend.app.services.ingestion import IngestionError, load_input_bundle
from backend.app.services.reporting import (
    EXPLANATION_AUDIT_FILENAME,
    FINAL_SUBMISSION_FILENAME,
    ReportingError,
    build_evidence_reviewed_output,
    build_explanation_audits,
    build_final_submission,
    candidate_csv_sha256,
    explanation_audit_sha256,
    validate_explanation_audit_jsonl,
    validate_final_submission_csv,
    write_explanation_audit_jsonl,
    write_final_submission,
)
from backend.app.services.retrieval import SentenceTransformerEmbeddingProvider


def main(settings: Settings | None = None) -> int:
    active = settings or get_settings()
    configure_logging(active.log_level)
    print("FreightGuard grounded explanation generation")
    try:
        runtime = _runtime_settings(active)
        provider = _provider(active, runtime.mode)
        cache = ExplanationCache(
            active.explanation_cache_path, enabled=active.explanation_cache_enabled
        )
        bundle = load_input_bundle(active)
        weekly = calculate_weekly_route_metrics(bundle.shipments)
        detected = detect_candidate_anomalies(
            add_percentage_comparisons(
                add_comparison_baselines(weekly)
            ),
            active.anomaly_threshold_percent,
        )
        notes = compile_context_notes(
            bundle.context_notes, frozenset(bundle.shipments["route"].unique())
        )
        evidence = review_candidate_evidence(
            build_candidate_queries(detected),
            notes,
            SentenceTransformerEmbeddingProvider(
                active.embedding_model_name,
                active.embedding_model_revision,
                active.embedding_model_path,
                local_only=active.embedding_local_only,
            ),
            RetrievalConfig(
                top_k=active.retrieval_top_k,
                rrf_k=active.retrieval_rrf_k,
                sparse_weight=active.retrieval_sparse_weight,
                dense_weight=active.retrieval_dense_weight,
            ),
            EvidencePolicy(
                global_magnitude_tolerance_percent=(
                    active.global_magnitude_tolerance_percent
                )
            ),
        )
        decisions = tuple(packet.decision for packet in evidence.packets)
        reviewed = build_evidence_reviewed_output(
            detected, decisions, bundle.output_columns
        )
        records = generate_explanations(evidence.packets, provider, cache, runtime)
        audits = build_explanation_audits(records)
        final_output = build_final_submission(reviewed, records)

        audit_path = active.output_data_dir / EXPLANATION_AUDIT_FILENAME
        final_path = active.output_data_dir / FINAL_SUBMISSION_FILENAME
        write_explanation_audit_jsonl(audits, audit_path)
        validate_explanation_audit_jsonl(audit_path, audits)
        write_final_submission(final_output, final_path)
        validate_final_submission_csv(final_path, reviewed, records)
        audit_hash = explanation_audit_sha256(audit_path)
        final_hash = candidate_csv_sha256(final_path)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except (AnalyticsError, ContextCompilationError, EvidenceError, ExplanationError) as exc:
        print(f"Result: FAIL (pipeline): {exc}")
        return 1
    except ReportingError as exc:
        print(f"Result: FAIL (reporting): {exc}")
        return 1

    _print_summary(
        runtime,
        records,
        audit_path,
        audit_hash,
        final_path,
        final_hash,
        weekly_count=len(weekly),
    )
    return 0


def _runtime_settings(settings: Settings) -> ExplanationSettings:
    return ExplanationSettings(
        mode=GenerationMode(settings.explanation_mode),
        prompt_version=settings.explanation_prompt_version,
        max_attempts=settings.explanation_max_attempts,
        max_concurrency=settings.explanation_max_concurrency,
        cache_enabled=settings.explanation_cache_enabled,
        input_cost_per_1m_usd=settings.model_input_cost_per_1m_usd,
        cached_input_cost_per_1m_usd=settings.model_cached_input_cost_per_1m_usd,
        output_cost_per_1m_usd=settings.model_output_cost_per_1m_usd,
        pricing_snapshot_date=settings.model_pricing_snapshot_date,
    )


def _provider(settings: Settings, mode: GenerationMode):
    if mode == GenerationMode.TEMPLATE:
        return TemplateExplanationProvider()
    if not settings.explanation_model.strip():
        from backend.app.services.explanations.errors import ProviderConfigurationError

        raise ProviderConfigurationError("Live/replay mode requires EXPLANATION_MODEL.")
    if mode == GenerationMode.REPLAY:
        return ReplayIdentityProvider(settings.explanation_provider, settings.explanation_model)
    if settings.openai_api_key is None:
        from backend.app.services.explanations.errors import ProviderConfigurationError

        raise ProviderConfigurationError("Live mode requires OPENAI_API_KEY.")
    return OpenAIExplanationProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.explanation_model,
        timeout_seconds=settings.explanation_timeout_seconds,
        max_output_tokens=settings.explanation_max_output_tokens,
        temperature=settings.explanation_temperature,
        supports_temperature=settings.explanation_temperature_supported,
    )


def _print_summary(runtime, records, audit_path, audit_hash, final_path, final_hash, *, weekly_count):
    verdicts = Counter(record.verdict for record in records)
    sources = Counter(record.explanation_source for record in records)
    failures = Counter(code.value for record in records for code in record.failure_codes)
    usage = {
        "input": sum(record.usage.input_tokens for record in records),
        "cached": sum(record.usage.cached_input_tokens for record in records),
        "output": sum(record.usage.output_tokens for record in records),
        "reasoning": sum(record.usage.reasoning_tokens or 0 for record in records),
        "total": sum(record.usage.total_tokens for record in records),
    }
    costs = [record.estimated_cost_usd for record in records]
    total_cost = None if any(cost is None for cost in costs) else sum(costs, Decimal(0))
    print(f"Weekly route groups: {weekly_count}")
    print(f"Candidates: {len(records)}")
    print(f"Mode: {runtime.mode.value}")
    print(f"Justified: {verdicts[EvidenceVerdict.JUSTIFIED]}")
    print(f"Partially explained: {verdicts[EvidenceVerdict.PARTIALLY_EXPLAINED]}")
    print(f"Unexplained: {verdicts[EvidenceVerdict.UNEXPLAINED]}")
    print(f"Eligible model requests: {len(records) - verdicts[EvidenceVerdict.UNEXPLAINED]}")
    print(f"Provider attempts: {sum(record.provider_attempts for record in records)}")
    print(f"Accepted model explanations: {sources[ExplanationSource.MODEL]}")
    print(f"Cache hits: {sources[ExplanationSource.CACHE]}")
    print(f"Fallbacks: {sources[ExplanationSource.FALLBACK]}")
    print(f"Direct templates: {sources[ExplanationSource.TEMPLATE]}")
    print(f"Validation failures: {dict(sorted(failures.items())) or 'none'}")
    print(f"Input tokens: {usage['input']}")
    print(f"Cached input tokens: {usage['cached']}")
    print(f"Output tokens: {usage['output']}")
    print(f"Reasoning tokens: {usage['reasoning']}")
    print(f"Total tokens: {usage['total']}")
    print(f"Estimated cost: {'unavailable' if total_cost is None else f'USD {total_cost:.6f}'}")
    print("Audit contract: PASS")
    print("CSV contract: PASS")
    print(f"Audit: {_display_path(audit_path)}")
    print(f"Audit SHA-256: {audit_hash}")
    print(f"Final CSV: {_display_path(final_path)}")
    print(f"Final CSV SHA-256: {final_hash}")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
