"""Explicit Phase 2-9 orchestration used by CLI and application layers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pandas as pd

from ..core.config import Settings
from ..domain.context_notes import CompiledContextNote
from ..domain.evaluation import EvaluationReport
from ..domain.evidence import EvidencePolicy, EvidenceReviewResult, RetrievalConfig
from ..domain.explanations import (
    ExplanationSettings,
    FinalExplanationRecord,
    GenerationMode,
)
from ..domain.root_cause import RootCauseAnalysis
from ..evaluation.contracts import configuration_fingerprint
from ..evaluation.inputs import fingerprint_inputs
from ..services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from ..services.context import compile_context_notes
from ..services.evidence import build_candidate_queries, review_candidate_evidence
from ..services.explanations import ExplanationCache, generate_explanations
from ..services.explanations.providers import (
    OpenAIExplanationProvider,
    ReplayIdentityProvider,
    TemplateExplanationProvider,
)
from ..services.ingestion import load_input_bundle
from ..services.ingestion.contracts import InputBundle
from ..services.reporting import (
    EXPLANATION_AUDIT_FILENAME,
    FINAL_SUBMISSION_FILENAME,
    build_evidence_reviewed_output,
    build_explanation_audits,
    build_final_submission,
    validate_explanation_audit_jsonl,
    validate_final_submission_csv,
    write_explanation_audit_jsonl,
    write_final_submission,
)
from ..services.retrieval import SentenceTransformerEmbeddingProvider
from ..services.root_cause import (
    ROOT_CAUSE_FILENAME,
    RootCausePolicy,
    analyze_operational_root_causes,
    write_root_cause_artifact,
)
from ..state.errors import AnalysisRunFailedError


@dataclass(frozen=True, slots=True)
class PipelineExecutionResult:
    bundle: InputBundle
    weekly: pd.DataFrame
    candidate_metrics: pd.DataFrame
    notes: tuple[CompiledContextNote, ...]
    evidence: EvidenceReviewResult
    explanation_records: tuple[FinalExplanationRecord, ...]
    final_output: pd.DataFrame
    final_csv_path: Path
    final_csv_sha256: str
    explanation_audit_path: Path
    explanation_audit_sha256: str
    root_causes: tuple[RootCauseAnalysis, ...]
    root_cause_artifact_path: Path
    root_cause_artifact_sha256: str
    evaluation: EvaluationReport
    evaluation_report_path: Path
    evaluation_report_sha256: str
    stage_durations_ms: dict[str, int]
    total_duration_ms: int


def execute_pipeline(settings: Settings, mode: str) -> PipelineExecutionResult:
    """Run Phases 2-8 privately and bind them to a validated Phase 9 report."""
    total_started = perf_counter()
    durations: dict[str, int] = {}

    started = perf_counter()
    bundle = load_input_bundle(settings)
    durations["ingestion"] = _elapsed_ms(started)

    started = perf_counter()
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    detected = detect_candidate_anomalies(
        add_percentage_comparisons(add_comparison_baselines(weekly)),
        settings.anomaly_threshold_percent,
    )
    durations["analytics"] = _elapsed_ms(started)

    started = perf_counter()
    notes = compile_context_notes(
        bundle.context_notes, frozenset(bundle.shipments["route"].unique())
    )
    durations["context_compilation"] = _elapsed_ms(started)

    started = perf_counter()
    evidence = review_candidate_evidence(
        build_candidate_queries(detected),
        notes,
        SentenceTransformerEmbeddingProvider(
            settings.embedding_model_name,
            settings.embedding_model_revision,
            settings.embedding_model_path,
            local_only=settings.embedding_local_only,
        ),
        RetrievalConfig(
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
            sparse_weight=settings.retrieval_sparse_weight,
            dense_weight=settings.retrieval_dense_weight,
        ),
        EvidencePolicy(
            global_magnitude_tolerance_percent=(
                settings.global_magnitude_tolerance_percent
            )
        ),
    )
    durations["retrieval_and_evidence"] = _elapsed_ms(started)

    started = perf_counter()
    root_causes = analyze_operational_root_causes(
        bundle.shipments,
        detected,
        tuple(packet.decision for packet in evidence.packets),
        RootCausePolicy(
            min_current_category_shipments=settings.root_cause_min_current_category_shipments,
            min_reference_category_shipments=settings.root_cause_min_reference_category_shipments,
            min_lead_abs_effect=settings.root_cause_min_lead_abs_effect,
            min_lead_abs_share_pct=settings.root_cause_min_lead_abs_share_pct,
            max_leads_per_lens=settings.root_cause_max_leads_per_lens,
            metric_highlight_percent=settings.root_cause_metric_highlight_percent,
            reconstruction_tolerance=settings.root_cause_reconstruction_tolerance,
        ),
    )
    root_cause_path = settings.output_data_dir / ROOT_CAUSE_FILENAME
    root_cause_hash = write_root_cause_artifact(root_causes, root_cause_path)
    durations["operational_root_cause"] = _elapsed_ms(started)

    started = perf_counter()
    runtime = _explanation_settings(settings, mode)
    records = generate_explanations(
        evidence.packets,
        _provider(settings, runtime.mode),
        ExplanationCache(
            settings.explanation_cache_path,
            enabled=settings.explanation_cache_enabled,
        ),
        runtime,
    )
    durations["explanations"] = _elapsed_ms(started)

    started = perf_counter()
    decisions = tuple(packet.decision for packet in evidence.packets)
    reviewed = build_evidence_reviewed_output(
        detected, decisions, bundle.output_columns
    )
    final = build_final_submission(reviewed, records)
    audit_path = settings.output_data_dir / EXPLANATION_AUDIT_FILENAME
    final_path = settings.output_data_dir / FINAL_SUBMISSION_FILENAME
    audits = build_explanation_audits(records)
    write_explanation_audit_jsonl(audits, audit_path)
    validate_explanation_audit_jsonl(audit_path, audits)
    write_final_submission(final, final_path)
    validate_final_submission_csv(final_path, reviewed, records)
    final_hash = hashlib.sha256(final_path.read_bytes()).hexdigest()
    audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    durations["reporting"] = _elapsed_ms(started)

    started = perf_counter()
    evaluation_path = settings.evaluation_output_root / "evaluation_report.json"
    evaluation, evaluation_hash = _load_associated_evaluation(
        evaluation_path, settings, mode, final_hash
    )
    durations["evaluation_validation"] = _elapsed_ms(started)
    return PipelineExecutionResult(
        bundle=bundle,
        weekly=weekly,
        candidate_metrics=detected,
        notes=notes,
        evidence=evidence,
        explanation_records=records,
        final_output=final,
        final_csv_path=final_path,
        final_csv_sha256=final_hash,
        explanation_audit_path=audit_path,
        explanation_audit_sha256=audit_hash,
        root_causes=root_causes,
        root_cause_artifact_path=root_cause_path,
        root_cause_artifact_sha256=root_cause_hash,
        evaluation=evaluation,
        evaluation_report_path=evaluation_path,
        evaluation_report_sha256=evaluation_hash,
        stage_durations_ms=durations,
        total_duration_ms=_elapsed_ms(total_started),
    )


def _provider(settings: Settings, mode: GenerationMode):
    if mode == GenerationMode.TEMPLATE:
        return TemplateExplanationProvider()
    if not settings.explanation_model.strip():
        raise AnalysisRunFailedError("Configured explanation mode requires a model.")
    if mode == GenerationMode.REPLAY:
        return ReplayIdentityProvider(
            settings.explanation_provider, settings.explanation_model
        )
    if settings.openai_api_key is None:
        raise AnalysisRunFailedError("Live explanation mode is not configured.")
    return OpenAIExplanationProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.explanation_model,
        timeout_seconds=settings.explanation_timeout_seconds,
        max_output_tokens=settings.explanation_max_output_tokens,
        temperature=settings.explanation_temperature,
        supports_temperature=settings.explanation_temperature_supported,
    )


def _explanation_settings(settings: Settings, mode: str) -> ExplanationSettings:
    return ExplanationSettings(
        mode=GenerationMode(mode),
        prompt_version=settings.explanation_prompt_version,
        max_attempts=settings.explanation_max_attempts,
        max_concurrency=settings.explanation_max_concurrency,
        cache_enabled=settings.explanation_cache_enabled,
        input_cost_per_1m_usd=settings.model_input_cost_per_1m_usd,
        cached_input_cost_per_1m_usd=settings.model_cached_input_cost_per_1m_usd,
        output_cost_per_1m_usd=settings.model_output_cost_per_1m_usd,
        pricing_snapshot_date=settings.model_pricing_snapshot_date,
    )


def _load_associated_evaluation(
    path: Path, settings: Settings, mode: str, final_hash: str
) -> tuple[EvaluationReport, str]:
    try:
        raw = path.read_bytes()
        report = EvaluationReport.model_validate_json(raw)
    except (OSError, ValueError) as exc:
        raise AnalysisRunFailedError(
            "A valid Phase 9 evaluation report is required before publication."
        ) from exc
    if report.overall_status != "pass" or report.run_count != 3:
        raise AnalysisRunFailedError("Phase 9 evaluation is not a formal PASS.")
    expected_config = configuration_fingerprint(settings, mode)
    if report.configuration_fingerprint != expected_config:
        raise AnalysisRunFailedError(
            "Phase 9 configuration fingerprint does not match this run."
        )
    if report.inputs != fingerprint_inputs(settings.input_data_dir):
        raise AnalysisRunFailedError(
            "Phase 9 input fingerprints do not match this run."
        )
    comparison = next(
        (
            item
            for item in report.reproducibility.comparisons
            if item.artifact_name == FINAL_SUBMISSION_FILENAME
        ),
        None,
    )
    if (
        comparison is None
        or not comparison.identical
        or final_hash not in comparison.hashes
    ):
        raise AnalysisRunFailedError(
            "Final CSV hash is not covered by the passing Phase 9 report."
        )
    root_comparison = next(
        (
            item
            for item in report.reproducibility.comparisons
            if item.artifact_name == ROOT_CAUSE_FILENAME
        ),
        None,
    )
    root_path = settings.output_data_dir / ROOT_CAUSE_FILENAME
    root_hash = hashlib.sha256(root_path.read_bytes()).hexdigest()
    if (
        root_comparison is None
        or not root_comparison.identical
        or root_hash not in root_comparison.hashes
    ):
        raise AnalysisRunFailedError(
            "Root-cause artifact hash is not covered by the passing evaluation."
        )
    return report, hashlib.sha256(raw).hexdigest()


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
