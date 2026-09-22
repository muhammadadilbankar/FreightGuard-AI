"""Exact preliminary candidate output construction and CSV persistence."""

import csv
import hashlib
import logging
import math
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
from pandas.api.types import is_bool_dtype

from ...core.logging import LOGGER_NAME
from ..analytics.contracts import CANDIDATE_METRIC_COLUMNS
from ..ingestion.contracts import (
    CONTEXT_NOTES_FILENAME,
    OUTPUT_COLUMNS,
    OUTPUT_CONTRACT_FILENAME,
    SHIPMENTS_FILENAME,
)
from .errors import OutputContractError, ReportingError

logger = logging.getLogger(f"{LOGGER_NAME}.candidate_csv")

CANDIDATE_OUTPUT_FILENAME = "candidate_anomalies.csv"
PRELIMINARY_REASON = (
    "Context review pending. Cost rise is currently flagged for review."
)
PEER_UNAVAILABLE_TEXT = "Not available: no other same-type routes this week"


def build_candidate_output(
    candidate_metrics: pd.DataFrame, output_columns: tuple[str, ...]
) -> pd.DataFrame:
    """Filter candidates and map them into the exact eight-column contract."""
    if tuple(output_columns) != OUTPUT_COLUMNS:
        raise OutputContractError(
            "Output columns do not match the authoritative eight-column contract."
        )
    if not isinstance(candidate_metrics, pd.DataFrame):
        raise OutputContractError("Candidate metrics must be a Pandas DataFrame.")
    if tuple(candidate_metrics.columns) != CANDIDATE_METRIC_COLUMNS:
        raise OutputContractError(
            "Candidate metrics must use the canonical Phase 5 column order."
        )
    decisions = candidate_metrics["candidate_anomaly"]
    if decisions.isna().any() or not is_bool_dtype(decisions.dtype):
        raise OutputContractError(
            "candidate_anomaly must contain non-null Boolean values."
        )

    candidates = candidate_metrics.loc[
        candidate_metrics["candidate_anomaly"]
    ].copy(deep=True)
    candidates = candidates.sort_values(
        ["route", "week_of"], kind="mergesort"
    ).reset_index(drop=True)
    if candidates.duplicated(["route", "route_type", "week_of"]).any():
        raise OutputContractError("Candidate keys must be unique.")
    if candidates["vs_own_history_pct"].isna().any():
        raise OutputContractError(
            "Every candidate must have an own-history comparison."
        )

    output = pd.DataFrame(index=candidates.index)
    output["route"] = candidates["route"].astype(str)
    output["week_of"] = pd.to_datetime(candidates["week_of"]).dt.strftime("%Y-%m-%d")
    output["cost_per_tonne_km"] = candidates["cost_per_tonne_km"].map(
        lambda value: f"{value:.2f}"
    )
    output["vs_own_history"] = candidates["vs_own_history_pct"].map(
        lambda value: f"{value:+.1f}% vs this route's past average"
    )
    output["vs_similar_routes"] = candidates["vs_similar_routes_pct"].map(
        lambda value: (
            PEER_UNAVAILABLE_TEXT
            if pd.isna(value)
            else f"{value:+.1f}% vs similar-length routes this week"
        )
    )
    output["flagged"] = "Yes"
    output["matched_note_id"] = ""
    output["reason"] = PRELIMINARY_REASON
    result = output.loc[:, OUTPUT_COLUMNS].copy(deep=True)
    if len(result) != int(candidate_metrics["candidate_anomaly"].sum()):
        raise OutputContractError(
            "Output row count does not reconcile to candidate decisions."
        )
    return result


def write_candidate_csv(output: pd.DataFrame, destination: Path) -> Path:
    """Atomically write deterministic UTF-8 CSV bytes with RFC-safe quoting."""
    _validate_output_frame(output)
    destination = Path(destination)
    if destination.name in {
        SHIPMENTS_FILENAME,
        CONTEXT_NOTES_FILENAME,
        OUTPUT_CONTRACT_FILENAME,
    }:
        raise OutputContractError("Refusing to overwrite a supplied input filename.")
    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            delete=False,
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        ) as temporary:
            temporary_path = Path(temporary.name)
            writer = csv.writer(
                temporary, quoting=csv.QUOTE_MINIMAL, lineterminator="\n"
            )
            writer.writerow(OUTPUT_COLUMNS)
            writer.writerows(output.itertuples(index=False, name=None))
        os.replace(temporary_path, destination)
    except (OSError, csv.Error, TypeError, ValueError) as exc:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise ReportingError(f"Unable to write candidate CSV: {exc}") from exc
    logger.info("Wrote candidate CSV path=%s rows=%d", destination, len(output))
    return destination


def validate_candidate_csv(path: Path, expected_rows: int) -> None:
    """Independently read and validate the serialized candidate CSV contract."""
    try:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, csv.Error) as exc:
        raise OutputContractError(f"Unable to read candidate CSV: {exc}") from exc
    if not rows or tuple(rows[0]) != OUTPUT_COLUMNS:
        raise OutputContractError("Candidate CSV header does not match the contract.")
    data_rows = rows[1:]
    if len(data_rows) != expected_rows:
        raise OutputContractError(
            f"Candidate CSV row count is {len(data_rows)}; expected {expected_rows}."
        )
    if any(len(row) != len(OUTPUT_COLUMNS) for row in data_rows):
        raise OutputContractError("Every candidate CSV row must contain eight fields.")

    previous_key: tuple[str, str] | None = None
    for row in data_rows:
        record = dict(zip(OUTPUT_COLUMNS, row, strict=True))
        key = (record["route"], record["week_of"])
        if previous_key is not None and key < previous_key:
            raise OutputContractError("Candidate CSV rows are not deterministically sorted.")
        previous_key = key
        try:
            parsed_cost = float(record["cost_per_tonne_km"])
        except ValueError as exc:
            raise OutputContractError(
                "Candidate CSV cost_per_tonne_km must be numeric."
            ) from exc
        if not math.isfinite(parsed_cost):
            raise OutputContractError(
                "Candidate CSV cost_per_tonne_km must be finite."
            )
        if re.fullmatch(r"-?\d+\.\d{2}", record["cost_per_tonne_km"]) is None:
            raise OutputContractError(
                "Candidate CSV cost_per_tonne_km must use two decimal places."
            )
        try:
            parsed_week = datetime.strptime(record["week_of"], "%Y-%m-%d")
        except ValueError as exc:
            raise OutputContractError(
                "Candidate CSV week_of must use YYYY-MM-DD."
            ) from exc
        if parsed_week.strftime("%Y-%m-%d") != record["week_of"]:
            raise OutputContractError(
                "Candidate CSV week_of must use canonical YYYY-MM-DD."
            )
        if not record["vs_own_history"] or not record["vs_similar_routes"]:
            raise OutputContractError("Candidate comparison fields must be non-empty.")
        if record["flagged"] != "Yes":
            raise OutputContractError("Every Phase 5 candidate must be flagged Yes.")
        if record["matched_note_id"] != "":
            raise OutputContractError(
                "Every Phase 5 matched_note_id cell must be blank."
            )
        if record["reason"] != PRELIMINARY_REASON:
            raise OutputContractError(
                "Every Phase 5 reason must use the preliminary wording."
            )
    logger.info("Validated candidate CSV path=%s rows=%d contract=PASS", path, expected_rows)


def candidate_csv_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a generated candidate CSV."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ReportingError(f"Unable to hash candidate CSV: {exc}") from exc


def _validate_output_frame(output: pd.DataFrame) -> None:
    if not isinstance(output, pd.DataFrame):
        raise OutputContractError("Candidate output must be a Pandas DataFrame.")
    if tuple(output.columns) != OUTPUT_COLUMNS:
        raise OutputContractError(
            "Candidate output columns do not match the authoritative contract."
        )
    if output.isna().any().any():
        raise OutputContractError("Candidate output must not contain null cells.")
