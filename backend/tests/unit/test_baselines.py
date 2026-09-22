"""Unit tests for leak-free history and self-excluding peer baselines."""

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.app.core.config import Settings
from backend.app.services.analytics import (
    AnalyticsInputError,
    AnalyticsInvariantError,
    add_comparison_baselines,
    validate_baseline_reconciliation,
)
from backend.app.services.analytics.contracts import (
    BASELINE_METRIC_COLUMNS,
    WEEKLY_METRIC_COLUMNS,
)
from backend.scripts.inspect_baselines import main as inspect_main

HISTORY = "own_history_avg_cost_per_tonne_km"
HISTORY_COUNT = "history_weeks_used"
PEER = "similar_routes_avg_cost_per_tonne_km"
PEER_COUNT = "peer_routes_used"


def _weekly_row(
    route: str,
    week: str,
    rate: float,
    *,
    route_type: str = "Short",
    shipment_count: int = 1,
    total_quantity: float = 10.0,
    total_tonne_km: float = 100.0,
) -> dict[str, object]:
    return {
        "route": route,
        "route_type": route_type,
        "week_of": pd.Timestamp(week),
        "shipment_count": shipment_count,
        "total_freight_cost_inr": rate * total_tonne_km,
        "total_quantity_tonnes": total_quantity,
        "total_tonne_km": total_tonne_km,
        "cost_per_tonne_km": rate,
    }


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(rows).loc[:, WEEKLY_METRIC_COLUMNS]


def _history_frame(count: int = 10) -> pd.DataFrame:
    return _frame(
        *(
            _weekly_row(
                "A-B",
                (pd.Timestamp("2024-01-01") + timedelta(days=7 * index))
                .date()
                .isoformat(),
                float(index + 1),
            )
            for index in range(count)
        )
    )


def _set_rate(frame: pd.DataFrame, index: int, rate: float) -> None:
    frame.loc[index, "cost_per_tonne_km"] = rate
    frame.loc[index, "total_freight_cost_inr"] = (
        rate * frame.loc[index, "total_tonne_km"]
    )


def test_history_shifts_current_value_and_caps_at_eight() -> None:
    result = add_comparison_baselines(_history_frame())

    assert pd.isna(result.loc[0, HISTORY])
    assert result.loc[0, HISTORY_COUNT] == 0
    assert result.loc[1, HISTORY] == pytest.approx(1.0)
    assert result.loc[1, HISTORY_COUNT] == 1
    assert result.loc[2, HISTORY] == pytest.approx(1.5)
    assert result.loc[2, HISTORY_COUNT] == 2
    assert result.loc[8, HISTORY] == pytest.approx(4.5)
    assert result.loc[8, HISTORY_COUNT] == 8
    assert result.loc[9, HISTORY] == pytest.approx(5.5)
    assert result.loc[9, HISTORY_COUNT] == 8
    assert result[HISTORY_COUNT].tolist() == [0, 1, 2, 3, 4, 5, 6, 7, 8, 8]
    assert pd.api.types.is_integer_dtype(result[HISTORY_COUNT])


def test_route_and_route_type_histories_never_mix() -> None:
    weekly = _frame(
        _weekly_row("A-B", "2024-01-01", 2.0, route_type="Short"),
        _weekly_row("A-B", "2024-01-08", 4.0, route_type="Short"),
        _weekly_row("A-B", "2024-01-01", 10.0, route_type="Medium"),
        _weekly_row("A-B", "2024-01-08", 20.0, route_type="Medium"),
        _weekly_row("C-D", "2024-01-01", 100.0, route_type="Short"),
        _weekly_row("C-D", "2024-01-08", 200.0, route_type="Short"),
    )

    result = add_comparison_baselines(weekly)

    short_ab = result[(result.route == "A-B") & (result.route_type == "Short")]
    medium_ab = result[(result.route == "A-B") & (result.route_type == "Medium")]
    short_cd = result[(result.route == "C-D") & (result.route_type == "Short")]
    assert short_ab.iloc[1][HISTORY] == pytest.approx(2.0)
    assert medium_ab.iloc[1][HISTORY] == pytest.approx(10.0)
    assert short_cd.iloc[1][HISTORY] == pytest.approx(100.0)


def test_current_and_future_changes_do_not_leak_backwards() -> None:
    weekly = _history_frame(11)
    original = add_comparison_baselines(weekly)

    current_changed = weekly.copy(deep=True)
    _set_rate(current_changed, 5, 999.0)
    current_result = add_comparison_baselines(current_changed)
    assert current_result.loc[5, HISTORY] == original.loc[5, HISTORY]

    future_changed = weekly.copy(deep=True)
    _set_rate(future_changed, 9, 999.0)
    future_result = add_comparison_baselines(future_changed)
    pd.testing.assert_series_equal(
        future_result.loc[:8, HISTORY], original.loc[:8, HISTORY]
    )


def test_past_changes_only_affect_windows_that_include_them() -> None:
    weekly = _history_frame(11)
    original = add_comparison_baselines(weekly)
    changed = weekly.copy(deep=True)
    _set_rate(changed, 1, 100.0)

    result = add_comparison_baselines(changed)

    assert result.loc[9, HISTORY] != original.loc[9, HISTORY]
    assert result.loc[10, HISTORY] == original.loc[10, HISTORY]


def test_value_more_than_eight_observations_back_is_excluded() -> None:
    weekly = _history_frame(10)
    original = add_comparison_baselines(weekly)
    changed = weekly.copy(deep=True)
    _set_rate(changed, 0, 1000.0)

    result = add_comparison_baselines(changed)

    assert result.loc[9, HISTORY] == original.loc[9, HISTORY]


def test_missing_calendar_weeks_use_previous_available_observations() -> None:
    weekly = _frame(
        *(
            _weekly_row(
                "A-B",
                (pd.Timestamp("2024-01-01") + timedelta(days=14 * index))
                .date()
                .isoformat(),
                float(index + 1),
            )
            for index in range(10)
        )
    )

    result = add_comparison_baselines(weekly)

    assert len(result) == 10
    assert result.loc[9, HISTORY_COUNT] == 8
    assert result.loc[9, HISTORY] == pytest.approx(5.5)


def test_three_route_peer_average_is_unweighted_and_self_excluding() -> None:
    weekly = _frame(
        _weekly_row(
            "A-B", "2024-01-01", 2.0, shipment_count=20, total_tonne_km=1000
        ),
        _weekly_row(
            "C-D", "2024-01-01", 4.0, shipment_count=1, total_tonne_km=10
        ),
        _weekly_row(
            "E-F", "2024-01-01", 8.0, shipment_count=100, total_tonne_km=5000
        ),
        _weekly_row("G-H", "2024-01-01", 30.0, route_type="Long"),
    )

    result = add_comparison_baselines(weekly).set_index("route")

    assert result.loc["A-B", PEER] == pytest.approx(6.0)
    assert result.loc["C-D", PEER] == pytest.approx(5.0)
    assert result.loc["E-F", PEER] == pytest.approx(3.0)
    assert result.loc["A-B", PEER_COUNT] == 2
    assert result.loc["C-D", PEER_COUNT] == 2
    assert result.loc["E-F", PEER_COUNT] == 2
    assert pd.isna(result.loc["G-H", PEER])
    assert result.loc["G-H", PEER_COUNT] == 0


def test_two_route_peers_equal_the_other_route_exactly() -> None:
    weekly = _frame(
        _weekly_row("A-B", "2024-01-01", 2.125),
        _weekly_row("C-D", "2024-01-01", 7.875),
    )

    result = add_comparison_baselines(weekly).set_index("route")

    assert result.loc["A-B", PEER] == pytest.approx(7.875, abs=1e-12)
    assert result.loc["C-D", PEER] == pytest.approx(2.125, abs=1e-12)


def test_peer_groups_do_not_cross_week_or_route_type() -> None:
    weekly = _frame(
        _weekly_row("A-B", "2024-01-01", 2.0),
        _weekly_row("C-D", "2024-01-01", 4.0),
        _weekly_row("E-F", "2024-01-08", 8.0),
        _weekly_row("G-H", "2024-01-01", 16.0, route_type="Medium"),
    )

    result = add_comparison_baselines(weekly).set_index("route")

    assert result.loc["A-B", PEER] == pytest.approx(4.0)
    assert result.loc["C-D", PEER] == pytest.approx(2.0)
    assert pd.isna(result.loc["E-F", PEER])
    assert pd.isna(result.loc["G-H", PEER])


def test_output_is_deterministic_sorted_and_does_not_mutate_input() -> None:
    weekly = _frame(
        _weekly_row("C-D", "2024-01-08", 4.0),
        _weekly_row("A-B", "2024-01-01", 2.0),
        _weekly_row("C-D", "2024-01-01", 3.0),
        _weekly_row("A-B", "2024-01-08", 2.5),
    )
    weekly.index = pd.Index([10, 20, 30, 40])
    original = weekly.copy(deep=True)
    shuffled = weekly.sample(frac=1, random_state=42)

    first = add_comparison_baselines(weekly)
    repeated = add_comparison_baselines(weekly)
    shuffled_result = add_comparison_baselines(shuffled)

    pd.testing.assert_frame_equal(first, repeated)
    pd.testing.assert_frame_equal(first, shuffled_result)
    pd.testing.assert_frame_equal(weekly, original)
    assert tuple(first.columns) == BASELINE_METRIC_COLUMNS
    assert first.index.tolist() == list(range(4))
    first.loc[0, "route"] = "changed"
    assert "changed" not in weekly["route"].tolist()


def test_baseline_availability_matches_zero_counts() -> None:
    result = add_comparison_baselines(_history_frame())

    assert result[HISTORY].isna().equals(result[HISTORY_COUNT].eq(0))
    assert result[PEER].isna().equals(result[PEER_COUNT].eq(0))
    assert pd.api.types.is_integer_dtype(result[PEER_COUNT])


def test_empty_input_fails() -> None:
    empty = pd.DataFrame(columns=WEEKLY_METRIC_COLUMNS)

    with pytest.raises(AnalyticsInputError, match="must contain weekly metrics"):
        add_comparison_baselines(empty)


def test_missing_column_fails() -> None:
    weekly = _history_frame(1).drop(columns="cost_per_tonne_km")

    with pytest.raises(AnalyticsInputError, match="missing Phase 3 columns"):
        add_comparison_baselines(weekly)


def test_duplicate_group_key_fails() -> None:
    row = _weekly_row("A-B", "2024-01-01", 2.0)
    weekly = _frame(row, row.copy())

    with pytest.raises(AnalyticsInputError, match="unique route"):
        add_comparison_baselines(weekly)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("route", None, "route must not contain null"),
        ("route_type", "unknown", "route_type must contain only"),
        ("week_of", pd.Timestamp("2024-01-02"), "Monday"),
        ("cost_per_tonne_km", 0.0, "strictly greater"),
        ("cost_per_tonne_km", -1.0, "strictly greater"),
        ("cost_per_tonne_km", float("nan"), "finite"),
        ("cost_per_tonne_km", float("inf"), "finite"),
    ],
)
def test_invalid_input_values_fail(column: str, value: object, message: str) -> None:
    weekly = _history_frame(1)
    weekly.loc[0, column] = value
    if column == "cost_per_tonne_km" and isinstance(value, float) and value > 0:
        weekly.loc[0, "total_freight_cost_inr"] = value * 100

    with pytest.raises(AnalyticsInputError, match=message):
        add_comparison_baselines(weekly)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (HISTORY_COUNT, 8, "history_weeks_used"),
        (PEER_COUNT, 1, "peer_routes_used"),
    ],
)
def test_reconciliation_rejects_tampered_baselines(
    column: str, value: float, message: str
) -> None:
    weekly = _history_frame(2)
    enriched = add_comparison_baselines(weekly)
    enriched.loc[0, column] = value

    with pytest.raises(AnalyticsInvariantError, match=message):
        validate_baseline_reconciliation(weekly, enriched)


def test_reconciliation_rejects_tampered_history_value() -> None:
    weekly = _history_frame(2)
    enriched = add_comparison_baselines(weekly)
    enriched.loc[1, HISTORY] = 999.0

    with pytest.raises(AnalyticsInvariantError, match="Own-history baselines"):
        validate_baseline_reconciliation(weekly, enriched)


def test_reconciliation_rejects_tampered_peer_value() -> None:
    weekly = _frame(
        _weekly_row("A-B", "2024-01-01", 2.0),
        _weekly_row("C-D", "2024-01-01", 4.0),
    )
    enriched = add_comparison_baselines(weekly)
    enriched.loc[0, PEER] = 999.0

    with pytest.raises(AnalyticsInvariantError, match="Peer baselines"):
        validate_baseline_reconciliation(weekly, enriched)


def test_inspection_cli_returns_nonzero_for_missing_inputs(tmp_path: Path) -> None:
    result = inspect_main(Settings(input_data_dir=tmp_path, _env_file=None))

    assert result == 2
