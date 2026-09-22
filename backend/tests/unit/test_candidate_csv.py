"""Unit tests for exact deterministic preliminary candidate CSV output."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from backend.app.services.analytics import detect_candidate_anomalies
from backend.app.services.analytics.contracts import COMPARISON_METRIC_COLUMNS
from backend.app.services.ingestion.contracts import OUTPUT_COLUMNS
from backend.app.services.reporting import (
    PEER_UNAVAILABLE_TEXT,
    PRELIMINARY_REASON,
    OutputContractError,
    build_candidate_output,
    candidate_csv_sha256,
    validate_candidate_csv,
    write_candidate_csv,
)


def _detected() -> pd.DataFrame:
    rows = []
    for route, week, cost, own, peer in (
        ("C-D", "2024-01-08", 4.126, 25.04, None),
        ("A-B", "2024-01-01", 3.294, 19.96, 21.04),
        ("E-F", "2024-01-15", 3.0, -2.0, 50.0),
    ):
        rows.append(
            {
                "route": route,
                "route_type": "Short",
                "week_of": pd.Timestamp(week),
                "shipment_count": 1,
                "total_freight_cost_inr": cost * 100,
                "total_quantity_tonnes": 10.0,
                "total_tonne_km": 100.0,
                "cost_per_tonne_km": cost,
                "own_history_avg_cost_per_tonne_km": cost / (1 + own / 100),
                "history_weeks_used": 1,
                "similar_routes_avg_cost_per_tonne_km": (
                    None if peer is None else cost / (1 + peer / 100)
                ),
                "peer_routes_used": 0 if peer is None else 1,
                "vs_own_history_pct": own,
                "vs_similar_routes_pct": peer,
            }
        )
    return detect_candidate_anomalies(
        pd.DataFrame(rows).loc[:, COMPARISON_METRIC_COLUMNS], 20.0
    )


def test_build_output_filters_formats_and_sorts_candidates() -> None:
    output = build_candidate_output(_detected(), OUTPUT_COLUMNS)

    assert tuple(output.columns) == OUTPUT_COLUMNS
    assert output["route"].tolist() == ["A-B", "C-D"]
    assert output["week_of"].tolist() == ["2024-01-01", "2024-01-08"]
    assert output["cost_per_tonne_km"].tolist() == ["3.29", "4.13"]
    assert output.loc[0, "vs_own_history"] == "+20.0% vs this route's past average"
    assert output.loc[0, "vs_similar_routes"] == (
        "+21.0% vs similar-length routes this week"
    )
    assert output.loc[1, "vs_similar_routes"] == PEER_UNAVAILABLE_TEXT
    assert output["flagged"].tolist() == ["Yes", "Yes"]
    assert output["matched_note_id"].tolist() == ["", ""]
    assert output["reason"].tolist() == [PRELIMINARY_REASON] * 2


def test_header_only_output_is_valid_when_there_are_no_candidates(tmp_path: Path) -> None:
    detected = _detected().copy(deep=True)
    detected.loc[:, "candidate_anomaly"] = False
    output = build_candidate_output(detected, OUTPUT_COLUMNS)
    path = write_candidate_csv(output, tmp_path / "empty.csv")

    validate_candidate_csv(path, expected_rows=0)

    assert output.empty
    assert path.read_text(encoding="utf-8") == ",".join(OUTPUT_COLUMNS) + "\n"


@pytest.mark.parametrize(
    "reason", ['Delay, congestion', 'Carrier said "urgent"', "Line one\nLine two"]
)
def test_csv_writer_round_trips_commas_quotes_and_newlines(
    tmp_path: Path, reason: str
) -> None:
    output = build_candidate_output(_detected(), OUTPUT_COLUMNS).iloc[[0]].copy()
    output.loc[0, "reason"] = reason

    path = write_candidate_csv(output, tmp_path / "quoted.csv")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert len(rows) == 2
    assert len(rows[1]) == 8
    assert rows[1][-1] == reason


def test_repeated_writes_have_identical_bytes_and_hash(tmp_path: Path) -> None:
    output = build_candidate_output(_detected(), OUTPUT_COLUMNS)
    first = write_candidate_csv(output, tmp_path / "first.csv")
    second = write_candidate_csv(output, tmp_path / "second.csv")

    validate_candidate_csv(first, expected_rows=2)
    validate_candidate_csv(second, expected_rows=2)

    assert first.read_bytes() == second.read_bytes()
    assert candidate_csv_sha256(first) == candidate_csv_sha256(second)
    assert not first.read_text(encoding="utf-8").startswith(",")


def test_output_contract_mismatch_and_tampered_csv_fail(tmp_path: Path) -> None:
    detected = _detected()
    with pytest.raises(OutputContractError, match="authoritative"):
        build_candidate_output(detected, tuple(reversed(OUTPUT_COLUMNS)))

    output = build_candidate_output(detected, OUTPUT_COLUMNS)
    output.loc[0, "flagged"] = "No"
    path = write_candidate_csv(output, tmp_path / "tampered.csv")
    with pytest.raises(OutputContractError, match="flagged Yes"):
        validate_candidate_csv(path, expected_rows=2)
