"""Evidence verdict mapping into the authoritative eight-column CSV."""

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

from ...domain.evidence import EvidenceDecision, EvidenceVerdict
from ..analytics.contracts import CANDIDATE_METRIC_COLUMNS
from ..ingestion.contracts import OUTPUT_COLUMNS
from .candidate_csv import build_candidate_output, write_candidate_csv
from .errors import EvidenceOutputContractError

EVIDENCE_REVIEWED_FILENAME = "evidence_reviewed_anomalies.csv"
UNEXPLAINED_REASON = (
    "No context note passed all route, date, direction, cost-impact, and scope checks."
)


def build_evidence_reviewed_output(
    candidate_metrics: pd.DataFrame,
    decisions: tuple[EvidenceDecision, ...],
    output_columns: tuple[str, ...],
) -> pd.DataFrame:
    """Preserve Phase 5 display values while applying deterministic verdict fields."""
    if tuple(candidate_metrics.columns) != CANDIDATE_METRIC_COLUMNS:
        raise EvidenceOutputContractError("Candidate metrics schema is not canonical.")
    output = build_candidate_output(candidate_metrics, output_columns)
    decision_map = {(item.route, item.week_of.isoformat()): item for item in decisions}
    output_keys = list(zip(output["route"], output["week_of"], strict=True))
    if set(output_keys) != set(decision_map) or len(output_keys) != len(decision_map):
        raise EvidenceOutputContractError(
            "Reviewed decisions must match every Phase 5 candidate exactly once."
        )
    for index, key in enumerate(output_keys):
        decision = decision_map[key]
        if decision.verdict == EvidenceVerdict.JUSTIFIED:
            output.loc[index, "flagged"] = "No (justified)"
            output.loc[index, "matched_note_id"] = decision.selected_note_id
            output.loc[index, "reason"] = (
                f"Valid context evidence {decision.selected_note_id} applies to this route "
                "and week and explicitly supports a transport-cost increase."
            )
        elif decision.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED:
            display_note = decision.supporting_note_ids[0]
            output.loc[index, "reason"] = (
                f"Context note {display_note} may explain the own-history rise, but its "
                "all-routes scope does not explain the route-specific peer premium."
            )
        else:
            output.loc[index, "reason"] = UNEXPLAINED_REASON
    return output.loc[:, OUTPUT_COLUMNS]


def write_evidence_reviewed_csv(output: pd.DataFrame, destination: Path) -> Path:
    return write_candidate_csv(output, destination)


def validate_evidence_reviewed_csv(
    path: Path, decisions: tuple[EvidenceDecision, ...]
) -> None:
    try:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, csv.Error) as exc:
        raise EvidenceOutputContractError(f"Unable to read reviewed CSV: {exc}") from exc
    if not rows or tuple(rows[0]) != OUTPUT_COLUMNS:
        raise EvidenceOutputContractError("Reviewed CSV header is invalid.")
    records = [dict(zip(OUTPUT_COLUMNS, row, strict=True)) for row in rows[1:]]
    decision_map = {(item.route, item.week_of.isoformat()): item for item in decisions}
    if len(records) != len(decision_map):
        raise EvidenceOutputContractError("Reviewed CSV row count is invalid.")
    previous: tuple[str, str] | None = None
    for record in records:
        key = (record["route"], record["week_of"])
        if key not in decision_map or (previous is not None and key < previous):
            raise EvidenceOutputContractError("Reviewed CSV keys are invalid or unsorted.")
        previous = key
        try:
            datetime.strptime(record["week_of"], "%Y-%m-%d")
            float(record["cost_per_tonne_km"])
        except ValueError as exc:
            raise EvidenceOutputContractError("Reviewed CSV date or cost is invalid.") from exc
        decision = decision_map[key]
        justified = decision.verdict == EvidenceVerdict.JUSTIFIED
        if justified:
            if record["flagged"] != "No (justified)" or record["matched_note_id"] != decision.selected_note_id:
                raise EvidenceOutputContractError("Justified CSV mapping is invalid.")
        elif record["flagged"] != "Yes" or record["matched_note_id"]:
            raise EvidenceOutputContractError("Non-justified CSV mapping is invalid.")
        if not record["reason"] or not record["vs_own_history"] or not record["vs_similar_routes"]:
            raise EvidenceOutputContractError("Reviewed CSV display fields must be non-empty.")
