"""Phase 9 end-to-end independent evaluation orchestration."""

from __future__ import annotations

import sys
from pathlib import Path

from ..core.config import PROJECT_ROOT, Settings
from ..domain.evaluation import (
    EvaluationDomain,
    EvaluationReport,
    EvaluationMetric,
    derive_status,
)
from ..domain.evidence import EvidencePolicy, RetrievalConfig
from ..domain.explanations import ExplanationSettings, GenerationMode
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
    ReplayIdentityProvider,
    TemplateExplanationProvider,
)
from ..services.ingestion import load_input_bundle
from ..services.reporting import build_evidence_reviewed_output, build_final_submission
from ..services.retrieval import SentenceTransformerEmbeddingProvider
from .candidates import evaluate_candidates
from .compilation import evaluate_compilation
from .contracts import check, configuration_fingerprint, environment_fingerprint
from .evidence import evaluate_evidence_gate
from .errors import EvaluationConfigurationError
from .explanations import evaluate_explanations
from .inputs import (
    evaluate_input_fingerprints,
    evaluate_raw_headers,
    fingerprint_inputs,
)
from .mathematics import evaluate_mathematics
from .metamorphic import evaluate_evidence_metamorphic, evaluate_metamorphic
from .outputs import evaluate_final_csv, evaluate_negative_controls
from .registry import normalize_registry
from .reporting import write_reports
from .reproducibility import run_reproducibility
from .retrieval import evaluate_retrieval

FIXTURE_ROOT = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "evaluation"


def run_evaluation(
    settings: Settings, *, run_count: int, mode: str
) -> tuple[EvaluationReport, tuple[Path, Path, Path]]:
    if mode not in {"template", "replay"}:
        raise EvaluationConfigurationError(
            "Formal evaluation forbids live explanation mode."
        )
    if run_count < 1:
        raise EvaluationConfigurationError("Evaluation run count must be positive.")
    output_root = settings.evaluation_output_root.resolve()
    input_root = settings.input_data_dir.resolve()
    if output_root == input_root or input_root in output_root.parents:
        raise EvaluationConfigurationError(
            "Evaluation output root must not overlap source inputs."
        )
    if mode == "replay" and (
        not settings.explanation_model.strip()
        or not settings.explanation_cache_path.is_file()
    ):
        raise EvaluationConfigurationError(
            "Replay evaluation requires EXPLANATION_MODEL and a frozen cache file."
        )
    before = fingerprint_inputs(settings.input_data_dir)
    bundle = load_input_bundle(settings)
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    baselines = add_comparison_baselines(weekly)
    candidates = detect_candidate_anomalies(
        add_percentage_comparisons(baselines), settings.anomaly_threshold_percent
    )
    notes = compile_context_notes(
        bundle.context_notes, frozenset(bundle.shipments.route.unique())
    )
    evidence = review_candidate_evidence(
        build_candidate_queries(candidates),
        notes,
        SentenceTransformerEmbeddingProvider(
            settings.embedding_model_name,
            settings.embedding_model_revision,
            settings.embedding_model_path,
            local_only=True,
        ),
        RetrievalConfig(
            top_k=settings.retrieval_top_k,
            rrf_k=settings.retrieval_rrf_k,
            sparse_weight=settings.retrieval_sparse_weight,
            dense_weight=settings.retrieval_dense_weight,
        ),
        EvidencePolicy(
            global_magnitude_tolerance_percent=settings.global_magnitude_tolerance_percent
        ),
    )
    decisions = tuple(packet.decision for packet in evidence.packets)
    reviewed = build_evidence_reviewed_output(
        candidates, decisions, bundle.output_columns
    )
    runtime_mode = GenerationMode(mode)
    runtime = ExplanationSettings(
        mode=runtime_mode,
        prompt_version=settings.explanation_prompt_version,
    )
    provider = (
        TemplateExplanationProvider()
        if runtime_mode == GenerationMode.TEMPLATE
        else ReplayIdentityProvider(
            settings.explanation_provider, settings.explanation_model
        )
    )
    records = generate_explanations(
        evidence.packets,
        provider,
        ExplanationCache(
            settings.explanation_cache_path,
            enabled=runtime_mode == GenerationMode.REPLAY,
        ),
        runtime,
    )
    final = build_final_submission(reviewed, records)
    authoritative_records = [
        {column: str(value) for column, value in row.items()}
        for row in final.to_dict(orient="records")
    ]

    checks = []
    metrics: list[EvaluationMetric] = []
    checks.extend(evaluate_input_fingerprints(before))
    checks.extend(evaluate_raw_headers(settings.input_data_dir))
    checks.extend(
        [
            check(
                "input.shipment_rows",
                EvaluationDomain.INPUT_INTEGRITY,
                "2,940 shipment rows load",
                len(bundle.shipments) == 2940,
                expected=2940,
                actual=len(bundle.shipments),
            ),
            check(
                "input.note_rows",
                EvaluationDomain.INPUT_INTEGRITY,
                "10 context notes load",
                len(bundle.context_notes) == 10,
                expected=10,
                actual=len(bundle.context_notes),
            ),
            check(
                "input.shipment_ids_unique",
                EvaluationDomain.INPUT_INTEGRITY,
                "Shipment IDs are unique",
                bool(bundle.shipments.shipment_id.is_unique),
            ),
            check(
                "input.note_ids_unique",
                EvaluationDomain.INPUT_INTEGRITY,
                "Note IDs are unique",
                bool(bundle.context_notes.note_id.is_unique),
            ),
            check(
                "input.required_values",
                EvaluationDomain.INPUT_INTEGRITY,
                "Required normalized inputs contain no missing values",
                not bundle.shipments.isna().any().any()
                and not bundle.context_notes.isna().any().any(),
            ),
            check(
                "input.directional_routes",
                EvaluationDomain.INPUT_INTEGRITY,
                "Seven directional routes exist",
                bundle.shipments.route.nunique() == 7,
                expected=7,
                actual=bundle.shipments.route.nunique(),
            ),
        ]
    )
    checks.extend(
        evaluate_mathematics(
            bundle.shipments,
            weekly,
            baselines,
            rel_tolerance=settings.evaluation_rel_tolerance,
            abs_tolerance=settings.evaluation_abs_tolerance,
        )
    )
    checks.extend(
        evaluate_candidates(candidates, FIXTURE_ROOT / "expected_candidate_keys.json")
    )
    checks.extend(
        evaluate_compilation(notes, FIXTURE_ROOT / "expected_compiled_notes.json")
    )
    section_checks, section_metrics = evaluate_retrieval(evidence)
    checks.extend(section_checks)
    metrics.extend(section_metrics)
    section_checks, section_metrics = evaluate_evidence_gate(
        evidence, FIXTURE_ROOT / "expected_evidence_decisions.json"
    )
    checks.extend(section_checks)
    metrics.extend(section_metrics)
    section_checks, section_metrics = evaluate_explanations(
        evidence.packets, records, settings.explanation_prompt_version
    )
    checks.extend(section_checks)
    metrics.extend(section_metrics)
    checks.extend(
        evaluate_metamorphic(
            bundle.shipments,
            bundle.context_notes,
            weekly,
            candidates,
            notes,
            settings.anomaly_threshold_percent,
        )
    )
    checks.extend(
        evaluate_evidence_metamorphic(
            candidates,
            notes,
            evidence,
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
    )

    reproducibility = run_reproducibility(
        [sys.executable, "-m", "backend.scripts.generate_final_submission"],
        run_count,
        output_root,
        {
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "EXPLANATION_MODE": mode,
            "EMBEDDING_LOCAL_ONLY": "true",
            "PYTHONIOENCODING": "utf-8",
            "EXPLANATION_CACHE_PATH": str(settings.explanation_cache_path),
            "EXPLANATION_MODEL": settings.explanation_model,
        },
        settings.evaluation_run_timeout_seconds,
        cwd=PROJECT_ROOT,
        authoritative_records=authoritative_records,
    )
    first_final = output_root / "runs" / "run_01" / "final_submission.csv"
    if first_final.exists():
        checks.extend(evaluate_final_csv(first_final, authoritative_records))
        checks.append(
            evaluate_negative_controls(
                first_final, authoritative_records, output_root / "negative_controls"
            )
        )
    checks.extend(
        [
            check(
                "reproducibility.formal_run_count",
                EvaluationDomain.REPRODUCIBILITY,
                "Formal evaluation uses exactly three runs",
                run_count == 3,
                expected=3,
                actual=run_count,
            ),
            check(
                "reproducibility.processes_succeeded",
                EvaluationDomain.REPRODUCIBILITY,
                "Every isolated pipeline subprocess exits zero",
                all(item.exit_code == 0 for item in reproducibility.runs),
                expected=[0] * run_count,
                actual=[item.exit_code for item in reproducibility.runs],
            ),
            check(
                "reproducibility.final_csv_bytes",
                EvaluationDomain.REPRODUCIBILITY,
                "All final CSV files are byte-identical",
                reproducibility.overall_reproducible,
                expected=True,
                actual=reproducibility.overall_reproducible,
            ),
        ]
    )
    after = fingerprint_inputs(settings.input_data_dir)
    checks.extend(evaluate_input_fingerprints(before, after)[-1:])
    checks, metric_tuple = normalize_registry(checks, metrics)
    artifacts = tuple(
        artifact for run in reproducibility.runs for artifact in run.artifacts
    )
    status = derive_status(checks, metric_tuple, reproducibility)
    report = EvaluationReport(
        overall_status=status,
        evaluation_mode=mode,
        run_count=run_count,
        environment=environment_fingerprint(settings, mode),
        inputs=before,
        configuration_fingerprint=configuration_fingerprint(settings, mode),
        checks=checks,
        metrics=metric_tuple,
        reproducibility=reproducibility,
        artifacts=artifacts,
    )
    paths = write_reports(report, output_root)
    return report, paths
