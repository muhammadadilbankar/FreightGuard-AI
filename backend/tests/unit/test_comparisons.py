"""Unit tests for full-precision Phase 5 percentage comparisons."""

import pandas as pd
import pytest

from backend.app.services.analytics import (
    AnalyticsInputError,
    add_percentage_comparisons,
)
from backend.app.services.analytics.contracts import (
    BASELINE_METRIC_COLUMNS,
    COMPARISON_METRIC_COLUMNS,
)


def _row(
    route: str,
    week: str,
    current: float,
    own: float | None,
    peer: float | None,
) -> dict[str, object]:
    return {
        "route": route,
        "route_type": "Short",
        "week_of": pd.Timestamp(week),
        "shipment_count": 1,
        "total_freight_cost_inr": current * 100,
        "total_quantity_tonnes": 10.0,
        "total_tonne_km": 100.0,
        "cost_per_tonne_km": current,
        "own_history_avg_cost_per_tonne_km": own,
        "history_weeks_used": 0 if own is None else 1,
        "similar_routes_avg_cost_per_tonne_km": peer,
        "peer_routes_used": 0 if peer is None else 1,
    }


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(rows).loc[:, BASELINE_METRIC_COLUMNS]


def test_percentage_formulas_preserve_full_precision_and_missing_values() -> None:
    baseline = _frame(
        _row("A-B", "2024-01-01", 4.0, 3.0, 5.0),
        _row("C-D", "2024-01-08", 3.0, 4.0, 2.0),
        _row("E-F", "2024-01-15", 3.0, 3.0, None),
        _row("G-H", "2024-01-22", 2.0, None, 1.0),
    )
    original = baseline.copy(deep=True)

    result = add_percentage_comparisons(baseline).set_index("route")

    assert result.loc["A-B", "vs_own_history_pct"] == pytest.approx(100 / 3)
    assert result.loc["A-B", "vs_similar_routes_pct"] == pytest.approx(-20.0)
    assert result.loc["C-D", "vs_own_history_pct"] == pytest.approx(-25.0)
    assert result.loc["C-D", "vs_similar_routes_pct"] == pytest.approx(50.0)
    assert result.loc["E-F", "vs_own_history_pct"] == pytest.approx(0.0)
    assert pd.isna(result.loc["E-F", "vs_similar_routes_pct"])
    assert pd.isna(result.loc["G-H", "vs_own_history_pct"])
    pd.testing.assert_frame_equal(baseline, original)


def test_comparison_output_is_deterministic_sorted_and_canonical() -> None:
    baseline = _frame(
        _row("C-D", "2024-01-08", 3.0, 2.0, 2.5),
        _row("A-B", "2024-01-01", 4.0, 3.0, 3.5),
    )

    first = add_percentage_comparisons(baseline)
    repeated = add_percentage_comparisons(baseline)
    shuffled = add_percentage_comparisons(baseline.sample(frac=1, random_state=4))

    pd.testing.assert_frame_equal(first, repeated)
    pd.testing.assert_frame_equal(first, shuffled)
    assert tuple(first.columns) == COMPARISON_METRIC_COLUMNS
    assert first["route"].tolist() == ["A-B", "C-D"]


@pytest.mark.parametrize(
    ("transform", "message"),
    [
        (lambda frame: frame.iloc[0:0], "must contain baseline rows"),
        (
            lambda frame: frame.drop(columns="peer_routes_used"),
            "missing Phase 4 columns",
        ),
        (
            lambda frame: frame.assign(history_weeks_used=0),
            "Own-history availability",
        ),
        (
            lambda frame: frame.assign(similar_routes_avg_cost_per_tonne_km=0.0),
            "finite and positive",
        ),
    ],
)
def test_invalid_phase_four_contract_fails(transform: object, message: str) -> None:
    baseline = _frame(_row("A-B", "2024-01-01", 4.0, 3.0, 5.0))

    with pytest.raises(AnalyticsInputError, match=message):
        add_percentage_comparisons(transform(baseline))
