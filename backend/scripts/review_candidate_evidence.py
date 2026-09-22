"""Run Phases 2 through 7 and write validated evidence-review artifacts."""

from collections import Counter
import logging
from pathlib import Path

from backend.app.core.config import PROJECT_ROOT, Settings, get_settings
from backend.app.core.logging import LOGGER_NAME, configure_logging
from backend.app.domain.evidence import EvidencePolicy, EvidenceVerdict, RetrievalConfig
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
from backend.app.services.ingestion import IngestionError, load_input_bundle
from backend.app.services.reporting import (
    EVIDENCE_AUDIT_FILENAME,
    EVIDENCE_REVIEWED_FILENAME,
    ReportingError,
    build_evidence_reviewed_output,
    candidate_csv_sha256,
    evidence_audit_sha256,
    validate_evidence_audit_jsonl,
    validate_evidence_reviewed_csv,
    write_evidence_audit_jsonl,
    write_evidence_reviewed_csv,
)
from backend.app.services.retrieval import SentenceTransformerEmbeddingProvider


def main(settings: Settings | None = None) -> int:
    """Execute the deterministic review and stop before any Phase 8 wording."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)
    logger = logging.getLogger(f"{LOGGER_NAME}.evidence_cli")
    logger.info(
        "Embedding model name=%s revision=%s path=%s local_only=%s",
        active_settings.embedding_model_name,
        active_settings.embedding_model_revision,
        (
            _display_path(active_settings.embedding_model_path)
            if active_settings.embedding_model_path is not None
            else "none"
        ),
        active_settings.embedding_local_only,
    )
    print("FreightGuard evidence review")
    audit_path = active_settings.output_data_dir / EVIDENCE_AUDIT_FILENAME
    csv_path = active_settings.output_data_dir / EVIDENCE_REVIEWED_FILENAME
    try:
        bundle = load_input_bundle(active_settings)
        weekly = calculate_weekly_route_metrics(bundle.shipments)
        baselines = add_comparison_baselines(weekly)
        comparisons = add_percentage_comparisons(baselines)
        detected = detect_candidate_anomalies(
            comparisons, active_settings.anomaly_threshold_percent
        )
        candidates = detected.loc[detected["candidate_anomaly"]].copy(deep=True)
        notes = compile_context_notes(
            bundle.context_notes, frozenset(bundle.shipments["route"].unique())
        )
        queries = build_candidate_queries(detected)
        retrieval_config = RetrievalConfig(
            top_k=active_settings.retrieval_top_k,
            rrf_k=active_settings.retrieval_rrf_k,
            sparse_weight=active_settings.retrieval_sparse_weight,
            dense_weight=active_settings.retrieval_dense_weight,
        )
        policy = EvidencePolicy(
            global_magnitude_tolerance_percent=(
                active_settings.global_magnitude_tolerance_percent
            )
        )
        provider = SentenceTransformerEmbeddingProvider(
            active_settings.embedding_model_name,
            active_settings.embedding_model_revision,
            active_settings.embedding_model_path,
            local_only=active_settings.embedding_local_only,
        )
        result = review_candidate_evidence(
            queries, notes, provider, retrieval_config, policy
        )
        decisions = tuple(packet.decision for packet in result.packets)

        write_evidence_audit_jsonl(result.audits, audit_path)
        validate_evidence_audit_jsonl(audit_path, result.audits)
        reviewed = build_evidence_reviewed_output(
            detected, decisions, bundle.output_columns
        )
        write_evidence_reviewed_csv(reviewed, csv_path)
        validate_evidence_reviewed_csv(csv_path, decisions)
        audit_digest = evidence_audit_sha256(audit_path)
        csv_digest = candidate_csv_sha256(csv_path)
    except IngestionError as exc:
        print(f"Result: FAIL (input validation): {exc}")
        return 2
    except (AnalyticsError, ContextCompilationError, EvidenceError) as exc:
        print(f"Result: FAIL (evidence pipeline): {exc}")
        return 1
    except ReportingError as exc:
        print(f"Result: FAIL (reporting): {exc}")
        return 1

    counts = Counter(decision.verdict for decision in decisions)
    matched = sum(decision.selected_note_id is not None for decision in decisions)
    _print_summary(
        len(detected), len(candidates), len(notes), counts, matched,
        audit_path, audit_digest, csv_path, csv_digest,
    )
    return 0


def _print_summary(
    weekly_count: int,
    candidate_count: int,
    note_count: int,
    counts: Counter[EvidenceVerdict],
    matched: int,
    audit_path: Path,
    audit_digest: str,
    csv_path: Path,
    csv_digest: str,
) -> None:
    print(f"Weekly route groups evaluated: {weekly_count}")
    print(f"Candidates reviewed: {candidate_count}")
    print(f"Compiled notes: {note_count}")
    print("Retrieval channels: sparse + dense + structured recall")
    print(f"Justified: {counts[EvidenceVerdict.JUSTIFIED]}")
    print(f"Partially explained: {counts[EvidenceVerdict.PARTIALLY_EXPLAINED]}")
    print(f"Unexplained: {counts[EvidenceVerdict.UNEXPLAINED]}")
    print(f"Flagged Yes: {candidate_count - counts[EvidenceVerdict.JUSTIFIED]}")
    print(f"Flagged No (justified): {counts[EvidenceVerdict.JUSTIFIED]}")
    print(f"Matched note IDs: {matched}")
    print("Audit contract: PASS")
    print("CSV contract: PASS")
    print(f"Audit: {_display_path(audit_path)}")
    print(f"Audit SHA-256: {audit_digest}")
    print(f"CSV: {_display_path(csv_path)}")
    print(f"CSV SHA-256: {csv_digest}")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
