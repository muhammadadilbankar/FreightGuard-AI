"""Unit tests for deterministic weighted weekly route-cost analytics."""

from pathlib import Path

import pandas as pd
import pytest

from backend.app.core.config import Settings
from backend.app.services.analytics import (
    AnalyticsInputError,
    AnalyticsInvariantError,
    calculate_weekly_route_metrics,
    validate_weekly_metrics_reconciliation,
)
from backend.app.services.analytics.contracts import (
    ANALYTICS_REQUIRED_COLUMNS,
    WEEKLY_METRIC_COLUMNS,
)
from backend.scripts.inspect_weekly_metrics import main as inspect_main


def _shipment(
    shipment_id: str,
    *,
    route: str = "A-B",
    route_type: str = "Short",
    week_of: str = "2024-01-01",
    quantity: float = 10.0,
    distance: float = 10.0,
    cost: float = 100.0,
    material: str = "Food",
    transporter: str = "Carrier One",
) -> dict[str, object]:
    return {
        "shipment_id": shipment_id,
        "origin": route.split("-")[0],
        "destination": route.split("-")[-1],
        "route_type": route_type,
        "material": material,
        "quantity_tonnes": quantity,
        "distance_km": distance,
        "freight_cost_inr": cost,
        "shipment_date": pd.Timestamp(week_of),
        "transporter": transporter,
        "route": route,
        "week_of": pd.Timestamp(week_of),
        "tonne_km": quantity * distance,
    }


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(rows or (_shipment("S-1"),))


def test_weighted_formula_aggregates_before_division() -> None:
    shipments = _frame(
        _shipment("A", quantity=10, distance=10, cost=100, material="Food"),
        _shipment(
            "B",
            quantity=20,
            distance=10,
            cost=600,
            material="Steel",
            transporter="Carrier Two",
        ),
    )

    result = calculate_weekly_route_metrics(shipments)

    assert len(result) == 1
    assert result.loc[0, "shipment_count"] == 2
    assert result.loc[0, "total_freight_cost_inr"] == 700
    assert result.loc[0, "total_quantity_tonnes"] == 30
    assert result.loc[0, "total_tonne_km"] == 300
    assert result.loc[0, "cost_per_tonne_km"] == pytest.approx(
        2.3333333333333335, rel=1e-12, abs=1e-12
    )
    assert result.loc[0, "cost_per_tonne_km"] != 2.0


def test_grouping_uses_only_route_type_and_week() -> None:
    shipments = _frame(
        _shipment("S-1", material="Food", transporter="One"),
        _shipment("S-2", material="Steel", transporter="Two"),
        _shipment("S-3", route="A-C"),
        _shipment("S-4", route="B-A"),
        _shipment("S-5", route_type="Medium"),
        _shipment("S-6", week_of="2024-01-08"),
    )

    result = calculate_weekly_route_metrics(shipments)

    assert len(result) == 5
    first_group = result[
        (result["route"] == "A-B")
        & (result["route_type"] == "Short")
        & (result["week_of"] == pd.Timestamp("2024-01-01"))
    ].iloc[0]
    assert first_group["shipment_count"] == 2
    assert set(result["route"]) == {"A-B", "A-C", "B-A"}


def test_one_shipment_group_uses_its_cost_and_tonne_km() -> None:
    result = calculate_weekly_route_metrics(
        _frame(_shipment("S-1", quantity=3, distance=7, cost=84))
    )

    assert result.loc[0, "total_tonne_km"] == 21
    assert result.loc[0, "cost_per_tonne_km"] == 4


def test_output_contract_precision_sorting_and_reset_index() -> None:
    shipments = _frame(
        _shipment(
            "S-2", route="B-C", quantity=1.23456789, distance=9.87654321, cost=37.1
        ),
        _shipment("S-1", route="A-B", cost=10.0),
    )

    result = calculate_weekly_route_metrics(shipments)

    assert tuple(result.columns) == WEEKLY_METRIC_COLUMNS
    assert result["route"].tolist() == ["A-B", "B-C"]
    assert result.index.tolist() == [0, 1]
    expected = 37.1 / (1.23456789 * 9.87654321)
    assert result.loc[1, "cost_per_tonne_km"] == pytest.approx(
        expected, rel=1e-12, abs=1e-12
    )
    assert isinstance(result.loc[1, "cost_per_tonne_km"], float)


def test_shuffled_input_and_repeated_calls_are_identical() -> None:
    shipments = _frame(
        _shipment("S-1", route="B-C", cost=200),
        _shipment("S-2", route="A-B", cost=100),
        _shipment("S-3", route="B-C", cost=300),
    )
    shuffled = shipments.sample(frac=1, random_state=42).reset_index(drop=True)

    first = calculate_weekly_route_metrics(shipments)
    second = calculate_weekly_route_metrics(shipments)
    shuffled_result = calculate_weekly_route_metrics(shuffled)

    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(first, shuffled_result)


def test_input_is_not_mutated_and_result_does_not_alias_it() -> None:
    shipments = _frame(_shipment("S-1"), _shipment("S-2", route="B-C"))
    shipments.index = pd.Index([10, 20])
    original = shipments.copy(deep=True)

    result = calculate_weekly_route_metrics(shipments)
    result.loc[0, "route"] = "changed"

    pd.testing.assert_frame_equal(shipments, original)
    assert "changed" not in shipments["route"].tolist()


def test_empty_input_fails() -> None:
    with pytest.raises(AnalyticsInputError, match="at least one shipment"):
        calculate_weekly_route_metrics(pd.DataFrame(columns=ANALYTICS_REQUIRED_COLUMNS))


def test_missing_required_column_fails() -> None:
    shipments = _frame().drop(columns="tonne_km")

    with pytest.raises(AnalyticsInputError, match="missing required columns: tonne_km"):
        calculate_weekly_route_metrics(shipments)


def test_duplicate_required_column_fails() -> None:
    shipments = _frame()
    shipments = pd.concat([shipments, shipments[["route"]]], axis=1)

    with pytest.raises(AnalyticsInputError, match="duplicate required columns: route"):
        calculate_weekly_route_metrics(shipments)


@pytest.mark.parametrize(("column", "value"), [("route", None), ("route_type", " ")])
def test_invalid_group_keys_fail(column: str, value: object) -> None:
    shipments = _frame()
    shipments.loc[0, column] = value

    with pytest.raises(AnalyticsInputError, match=column):
        calculate_weekly_route_metrics(shipments)


@pytest.mark.parametrize("week", ["2024-01-02", "not-a-date", "2024-01-01 12:00"])
def test_invalid_or_non_monday_weeks_fail(week: str) -> None:
    shipments = _frame()
    shipments["week_of"] = shipments["week_of"].astype(object)
    shipments.loc[0, "week_of"] = week

    with pytest.raises(AnalyticsInputError, match="week_of|Monday"):
        calculate_weekly_route_metrics(shipments)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("tonne_km", 0.0),
        ("tonne_km", -1.0),
        ("tonne_km", float("nan")),
        ("freight_cost_inr", float("inf")),
        ("quantity_tonnes", float("-inf")),
    ],
)
def test_nonpositive_or_nonfinite_numeric_values_fail(column: str, value: float) -> None:
    shipments = _frame()
    shipments.loc[0, column] = value

    with pytest.raises(AnalyticsInputError, match=column):
        calculate_weekly_route_metrics(shipments)


def test_nonnumeric_input_fails() -> None:
    shipments = _frame()
    shipments["distance_km"] = "10"

    with pytest.raises(AnalyticsInputError, match="distance_km must contain numeric"):
        calculate_weekly_route_metrics(shipments)


def test_inconsistent_tonne_km_fails() -> None:
    shipments = _frame()
    shipments.loc[0, "tonne_km"] += 0.1

    with pytest.raises(AnalyticsInputError, match="tonne_km must match"):
        calculate_weekly_route_metrics(shipments)


def test_duplicate_shipment_identifier_fails() -> None:
    shipments = _frame(_shipment("S-1"), _shipment("S-1"))

    with pytest.raises(AnalyticsInputError, match="shipment_id values must be unique"):
        calculate_weekly_route_metrics(shipments)


@pytest.mark.parametrize(
    ("column", "replacement", "message"),
    [
        ("shipment_count", 0, "shipment counts"),
        ("total_freight_cost_inr", 0.0, "freight cost"),
        ("total_quantity_tonnes", 0.0, "quantity"),
        ("total_tonne_km", 1.0, "tonne-kilometres"),
        ("cost_per_tonne_km", 999.0, "cost-per-tonne-kilometre"),
    ],
)
def test_reconciliation_rejects_inconsistent_results(
    column: str, replacement: float, message: str
) -> None:
    shipments = _frame()
    weekly = calculate_weekly_route_metrics(shipments)
    weekly.loc[0, column] = replacement

    with pytest.raises(AnalyticsInvariantError, match=message):
        validate_weekly_metrics_reconciliation(shipments, weekly)


def test_reconciliation_rejects_duplicate_group_keys() -> None:
    shipments = _frame()
    weekly = calculate_weekly_route_metrics(shipments)
    duplicated = pd.concat([weekly, weekly], ignore_index=True)

    with pytest.raises(AnalyticsInvariantError, match="duplicate"):
        validate_weekly_metrics_reconciliation(shipments, duplicated)


def test_inspection_cli_returns_nonzero_for_missing_inputs(tmp_path: Path) -> None:
    result = inspect_main(Settings(input_data_dir=tmp_path, _env_file=None))

    assert result == 2
