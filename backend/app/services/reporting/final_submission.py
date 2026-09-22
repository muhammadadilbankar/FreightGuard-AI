"""Final submission reconciliation using immutable Phase 7 output fields."""

import csv
from pathlib import Path
import re

import pandas as pd

from ...domain.evidence import EvidenceVerdict
from ...domain.explanations import FinalExplanationRecord
from ..ingestion.contracts import OUTPUT_COLUMNS
from .candidate_csv import write_candidate_csv
from .errors import FinalSubmissionError

FINAL_SUBMISSION_FILENAME = "final_submission.csv"
_NOTE_ID = re.compile(r"\bN\d+\b", re.IGNORECASE)


def build_final_submission(
    evidence_reviewed: pd.DataFrame,
    records: tuple[FinalExplanationRecord, ...],
) -> pd.DataFrame:
    if tuple(evidence_reviewed.columns) != OUTPUT_COLUMNS:
        raise FinalSubmissionError("Phase 7 reviewed output schema is invalid.")
    result = evidence_reviewed.copy(deep=True)
    record_map = {(item.route, item.week_of.isoformat()): item for item in records}
    keys = list(zip(result["route"], result["week_of"], strict=True))
    if len(keys) != len(record_map) or set(keys) != set(record_map):
        raise FinalSubmissionError("Final records do not match Phase 7 candidate keys.")
    for index, key in enumerate(keys):
        record = record_map[key]
        expected_flag = (
            "No (justified)"
            if record.verdict == EvidenceVerdict.JUSTIFIED
            else "Yes"
        )
        expected_note = record.selected_note_id or ""
        if (
            result.loc[index, "flagged"] != expected_flag
            or result.loc[index, "matched_note_id"] != expected_note
        ):
            raise FinalSubmissionError("Final record conflicts with Phase 7 authority.")
        mentioned = {item.upper() for item in _NOTE_ID.findall(record.reason)}
        if not mentioned.issubset(set(record.allowed_note_ids)):
            raise FinalSubmissionError("Final reason contains a non-allowlisted note ID.")
        result.loc[index, "reason"] = record.reason
    return result.loc[:, OUTPUT_COLUMNS]


def write_final_submission(output: pd.DataFrame, destination: Path) -> Path:
    return write_candidate_csv(output, destination)


def validate_final_submission_csv(
    path: Path,
    evidence_reviewed: pd.DataFrame,
    records: tuple[FinalExplanationRecord, ...],
) -> None:
    expected = build_final_submission(evidence_reviewed, records)
    try:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, csv.Error) as exc:
        raise FinalSubmissionError("Unable to read final submission.") from exc
    expected_rows = [list(OUTPUT_COLUMNS)] + [
        list(row) for row in expected.itertuples(index=False, name=None)
    ]
    if rows != expected_rows:
        raise FinalSubmissionError("Final submission round-trip mismatch.")
