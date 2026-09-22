"""Supplied-data regression tests for Phase 5 detection and output."""

from pathlib import Path

import pandas as pd
import pytest

from backend.app.core.config import Settings
from backend.app.services.analytics import (
    add_comparison_baselines,
    add_percentage_comparisons,
    calculate_weekly_route_metrics,
    detect_candidate_anomalies,
)
from backend.app.services.ingestion import load_input_bundle
from backend.app.services.ingestion.contracts import OUTPUT_COLUMNS
from backend.app.services.reporting import (
    PRELIMINARY_REASON,
    build_candidate_output,
    candidate_csv_sha256,
    validate_candidate_csv,
    write_candidate_csv,
)

EXPECTED = (
    ("Ahmedabad-Mumbai", "2025-01-20", 3.29, 29.5, 22.5),
    ("Chennai-Bangalore", "2025-02-24", 3.58, 31.5, 38.7),
    ("Chennai-Bangalore", "2025-03-03", 3.48, 22.8, 32.0),
    ("Chennai-Bangalore", "2025-03-10", 3.57, 22.1, 33.8),
    ("Chennai-Bangalore", "2025-03-17", 3.47, 13.7, 33.5),
    ("Delhi-Jaipur", "2024-11-11", 4.17, 35.5, 21.0),
    ("Delhi-Jaipur", "2024-11-18", 4.09, 27.6, 19.7),
    ("Mumbai-Pune", "2025-06-23", 3.76, 6.2, 20.6),
    ("Mumbai-Pune", "2025-09-15", 3.98, 9.2, 23.6),
    ("Mumbai-Pune", "2025-10-06", 3.94, 5.4, 22.9),
    ("Mumbai-Pune", "2025-10-20", 4.10, 7.7, 24.8),
    ("Mumbai-Pune", "2025-10-27", 4.07, 5.5, 28.3),
    ("Mumbai-Pune", "2025-11-03", 4.20, 7.4, 24.1),
    ("Mumbai-Pune", "2025-11-17", 4.32, 8.9, 31.6),
    ("Mumbai-Pune", "2025-11-24", 4.16, 3.0, 23.0),
    ("Mumbai-Pune", "2025-12-01", 4.39, 7.7, 37.4),
    ("Mumbai-Pune", "2025-12-08", 4.43, 7.2, 38.8),
    ("Mumbai-Pune", "2025-12-15", 4.39, 4.4, 35.5),
    ("Mumbai-Pune", "2025-12-22", 4.49, 5.7, 38.9),
)


@pytest.fixture(scope="module")
def supplied_candidates() -> tuple[pd.DataFrame, pd.DataFrame]:
    settings = Settings(_env_file=None)
    bundle = load_input_bundle(settings)
    weekly = calculate_weekly_route_metrics(bundle.shipments)
    baselines = add_comparison_baselines(weekly)
    comparisons = add_percentage_comparisons(baselines)
    detected = detect_candidate_anomalies(
        comparisons, settings.anomaly_threshold_percent
    )
    return detected, build_candidate_output(detected, bundle.output_columns)


def test_supplied_candidate_keys_counts_and_trigger_reconciliation(
    supplied_candidates: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    detected, output = supplied_candidates
    candidates = detected.loc[detected["candidate_anomaly"]]

    assert len(detected) == 728
    assert len(candidates) == len(output) == 19
    assert int(candidates["own_threshold_breached"].sum()) == 6
    assert int(candidates["peer_threshold_breached"].sum()) == 18
    assert int(
        (
            candidates["own_threshold_breached"]
            & candidates["peer_threshold_breached"]
        ).sum()
    ) == 5
    assert list(zip(output["route"], output["week_of"], strict=True)) == [
        (route, week) for route, week, *_ in EXPECTED
    ]
    assert tuple(output.columns) == OUTPUT_COLUMNS
    assert output["flagged"].eq("Yes").sum() == 19
    assert output["matched_note_id"].eq("").sum() == 19
    assert output["reason"].eq(PRELIMINARY_REASON).sum() == 19


def test_supplied_candidate_internal_and_display_regressions(
    supplied_candidates: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    detected, output = supplied_candidates
    candidates = detected.loc[detected["candidate_anomaly"]].set_index(
        ["route", "week_of"]
    )
    rendered = output.set_index(["route", "week_of"])

    for route, week, cost, own, peer in EXPECTED:
        internal = candidates.loc[(route, pd.Timestamp(week))]
        display = rendered.loc[(route, week)]
        assert float(display["cost_per_tonne_km"]) == pytest.approx(cost, abs=0.005)
        assert display["vs_own_history"].startswith(f"{own:+.1f}% ")
        assert display["vs_similar_routes"].startswith(f"{peer:+.1f}% ")
        assert internal["vs_own_history_pct"] == pytest.approx(own, abs=0.05)
        assert internal["vs_similar_routes_pct"] == pytest.approx(peer, abs=0.05)


def test_supplied_candidate_csv_round_trip_and_determinism(
    supplied_candidates: tuple[pd.DataFrame, pd.DataFrame], tmp_path: Path
) -> None:
    _, output = supplied_candidates
    first = write_candidate_csv(output, tmp_path / "first.csv")
    first_bytes = first.read_bytes()
    first_hash = candidate_csv_sha256(first)
    second = write_candidate_csv(output, tmp_path / "second.csv")

    validate_candidate_csv(first, expected_rows=19)
    validate_candidate_csv(second, expected_rows=19)

    assert first_bytes == second.read_bytes()
    assert first_hash == candidate_csv_sha256(second)
