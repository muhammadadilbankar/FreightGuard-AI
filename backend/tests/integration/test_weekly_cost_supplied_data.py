"""Supplied-data regression tests for canonical weekly route metrics."""

import math

import pandas as pd
import pytest

from backend.app.core.config import Settings
from backend.app.services.analytics import calculate_weekly_route_metrics
from backend.app.services.analytics.contracts import WEEKLY_METRIC_COLUMNS
from backend.app.services.ingestion import load_input_bundle

REGRESSION_CASES = (
    (
        "Mumbai-Pune",
        "2024-01-01",
        "Short",
        5,
        34849,
        70.7,
        10556.220000000001,
        3.3012764038642617,
    ),
    (
        "Delhi-Jaipur",
        "2024-11-11",
        "Short",
        4,
        84388,
        72.0,
        20222.59,
        4.1729570742422215,
    ),
    (
        "Ahmedabad-Mumbai",
        "2025-01-20",
        "Medium",
        5,
        134631,
        76.7,
        40916.71,
        3.290367187391166,
    ),
    (
        "Chennai-Bangalore",
        "2025-02-24",
        "Medium",
        5,
        120133,
        95.5,
        33530.229999999996,
        3.5828266015473207,
    ),
    (
        "Mumbai-Pune",
        "2025-09-15",
        "Short",
        4,
        34203,
        57.5,
        8591.97,
        3.9808099888616932,
    ),
)


@pytest.fixture(scope="module")
def supplied_metrics() -> tuple[pd.DataFrame, pd.DataFrame]:
    shipments = load_input_bundle(Settings(_env_file=None)).shipments
    return shipments, calculate_weekly_route_metrics(shipments)


def test_supplied_data_group_counts_and_contract(
    supplied_metrics: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    shipments, weekly = supplied_metrics

    assert len(shipments) == 2940
    assert len(weekly) == 728
    assert tuple(weekly.columns) == WEEKLY_METRIC_COLUMNS
    assert weekly["route"].nunique() == 7
    assert weekly["route_type"].nunique() == 3
    assert weekly["week_of"].nunique() == 104
    assert weekly["week_of"].min() == pd.Timestamp("2024-01-01")
    assert weekly["week_of"].max() == pd.Timestamp("2025-12-22")
    assert weekly["shipment_count"].min() == 3
    assert weekly["shipment_count"].max() == 5


@pytest.mark.parametrize(
    (
        "route",
        "week_of",
        "route_type",
        "shipment_count",
        "total_cost",
        "total_quantity",
        "total_tonne_km",
        "rate",
    ),
    REGRESSION_CASES,
)
def test_supplied_numerical_regression_rows(
    supplied_metrics: tuple[pd.DataFrame, pd.DataFrame],
    route: str,
    week_of: str,
    route_type: str,
    shipment_count: int,
    total_cost: float,
    total_quantity: float,
    total_tonne_km: float,
    rate: float,
) -> None:
    _, weekly = supplied_metrics
    row = weekly[
        (weekly["route"] == route)
        & (weekly["week_of"] == pd.Timestamp(week_of))
    ].iloc[0]

    assert row["route_type"] == route_type
    assert row["shipment_count"] == shipment_count
    assert row["total_freight_cost_inr"] == pytest.approx(
        total_cost, rel=1e-12, abs=1e-12
    )
    assert row["total_quantity_tonnes"] == pytest.approx(
        total_quantity, rel=1e-12, abs=1e-12
    )
    assert row["total_tonne_km"] == pytest.approx(
        total_tonne_km, rel=1e-12, abs=1e-12
    )
    assert row["cost_per_tonne_km"] == pytest.approx(
        rate, rel=1e-12, abs=1e-12
    )


def test_supplied_totals_reconcile(
    supplied_metrics: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    shipments, weekly = supplied_metrics

    assert weekly["shipment_count"].sum() == len(shipments)
    assert math.isclose(
        weekly["total_freight_cost_inr"].sum(),
        shipments["freight_cost_inr"].sum(),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        weekly["total_quantity_tonnes"].sum(),
        shipments["quantity_tonnes"].sum(),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        weekly["total_tonne_km"].sum(),
        shipments["tonne_km"].sum(),
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
