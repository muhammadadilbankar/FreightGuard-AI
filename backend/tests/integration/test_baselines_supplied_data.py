"""Supplied-data regression tests for history and peer baseline metrics."""

import pandas as pd
import pytest

from backend.app.core.config import Settings
from backend.app.services.analytics import (
    add_comparison_baselines,
    calculate_weekly_route_metrics,
)
from backend.app.services.analytics.contracts import BASELINE_METRIC_COLUMNS
from backend.app.services.ingestion import load_input_bundle

HISTORY = "own_history_avg_cost_per_tonne_km"
HISTORY_COUNT = "history_weeks_used"
PEER = "similar_routes_avg_cost_per_tonne_km"
PEER_COUNT = "peer_routes_used"

REGRESSION_CASES = (
    (
        "Mumbai-Pune",
        "2024-01-01",
        3.3012764038642617,
        None,
        0,
        3.000124589086287,
        1,
    ),
    (
        "Mumbai-Pune",
        "2024-01-08",
        3.3819401535881366,
        3.3012764038642617,
        1,
        3.053238844499479,
        1,
    ),
    (
        "Mumbai-Pune",
        "2024-02-26",
        3.249925923123964,
        3.3380877267885767,
        8,
        3.0959226120172616,
        1,
    ),
    (
        "Delhi-Jaipur",
        "2024-11-11",
        4.1729570742422215,
        3.079216557951722,
        8,
        3.447745798728505,
        1,
    ),
    (
        "Ahmedabad-Mumbai",
        "2025-01-20",
        3.290367187391166,
        2.541351823620185,
        8,
        2.6861515905915425,
        2,
    ),
    (
        "Chennai-Bangalore",
        "2025-02-24",
        3.5828266015473207,
        2.7253267565207007,
        8,
        2.5837434925863763,
        2,
    ),
    (
        "Mumbai-Pune",
        "2025-09-15",
        3.9808099888616932,
        3.643772458181048,
        8,
        3.220063126502312,
        1,
    ),
)


@pytest.fixture(scope="module")
def supplied_baselines() -> tuple[pd.DataFrame, pd.DataFrame]:
    shipments = load_input_bundle(Settings(_env_file=None)).shipments
    weekly = calculate_weekly_route_metrics(shipments)
    return weekly, add_comparison_baselines(weekly)


def test_supplied_baseline_counts_and_contract(
    supplied_baselines: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    weekly, enriched = supplied_baselines

    assert len(weekly) == len(enriched) == 728
    assert tuple(enriched.columns) == BASELINE_METRIC_COLUMNS
    assert enriched[HISTORY].isna().sum() == 7
    assert enriched[HISTORY].notna().sum() == 721
    history_distribution = enriched[HISTORY_COUNT].value_counts().to_dict()
    assert history_distribution[0] == 7
    for count in range(1, 8):
        assert history_distribution[count] == 7
    assert history_distribution[8] == 672
    assert enriched[PEER].isna().sum() == 0
    assert enriched[PEER_COUNT].value_counts().to_dict() == {1: 416, 2: 312}


@pytest.mark.parametrize(
    (
        "route",
        "week",
        "current_rate",
        "history_rate",
        "history_count",
        "peer_rate",
        "peer_count",
    ),
    REGRESSION_CASES,
)
def test_supplied_baseline_regression_rows(
    supplied_baselines: tuple[pd.DataFrame, pd.DataFrame],
    route: str,
    week: str,
    current_rate: float,
    history_rate: float | None,
    history_count: int,
    peer_rate: float,
    peer_count: int,
) -> None:
    _, enriched = supplied_baselines
    row = enriched[
        (enriched["route"] == route)
        & (enriched["week_of"] == pd.Timestamp(week))
    ].iloc[0]

    assert row["cost_per_tonne_km"] == pytest.approx(
        current_rate, rel=1e-12, abs=1e-12
    )
    if history_rate is None:
        assert pd.isna(row[HISTORY])
    else:
        assert row[HISTORY] == pytest.approx(history_rate, rel=1e-12, abs=1e-12)
    assert row[HISTORY_COUNT] == history_count
    assert row[PEER] == pytest.approx(peer_rate, rel=1e-12, abs=1e-12)
    assert row[PEER_COUNT] == peer_count


def test_reference_percentages_are_supported_but_not_persisted(
    supplied_baselines: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    _, enriched = supplied_baselines
    row = enriched[
        (enriched["route"] == "Delhi-Jaipur")
        & (enriched["week_of"] == pd.Timestamp("2024-11-11"))
    ].iloc[0]

    own_reference = (row["cost_per_tonne_km"] / row[HISTORY] - 1) * 100
    peer_reference = (row["cost_per_tonne_km"] / row[PEER] - 1) * 100
    assert own_reference == pytest.approx(35.52009076679068, rel=1e-12, abs=1e-12)
    assert peer_reference == pytest.approx(
        21.034360357459292, rel=1e-12, abs=1e-12
    )
    assert "vs_own_history_pct" not in enriched.columns
    assert "vs_similar_routes_pct" not in enriched.columns
