"""Unit tests for the configurable Phase 5 Boolean candidate rule."""

from decimal import Decimal

import pandas as pd
import pytest

from backend.app.services.analytics import (
    CandidateDetectionError,
    detect_candidate_anomalies,
)
from backend.app.services.analytics.contracts import (
    CANDIDATE_METRIC_COLUMNS,
    COMPARISON_METRIC_COLUMNS,
)


def _comparison_row(
    route: str,
    own_pct: float | None,
    peer_pct: float | None,
) -> dict[str, object]:
    current = 3.0
    own_baseline = None if own_pct is None else current / (1 + own_pct / 100)
    peer_baseline = None if peer_pct is None else current / (1 + peer_pct / 100)
    return {
        "route": route,
        "route_type": "Short",
        "week_of": pd.Timestamp("2024-01-01"),
        "shipment_count": 1,
        "total_freight_cost_inr": 300.0,
        "total_quantity_tonnes": 10.0,
        "total_tonne_km": 100.0,
        "cost_per_tonne_km": current,
        "own_history_avg_cost_per_tonne_km": own_baseline,
        "history_weeks_used": 0 if own_pct is None else 1,
        "similar_routes_avg_cost_per_tonne_km": peer_baseline,
        "peer_routes_used": 0 if peer_pct is None else 1,
        "vs_own_history_pct": own_pct,
        "vs_similar_routes_pct": peer_pct,
    }


def _frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(rows).loc[:, COMPARISON_METRIC_COLUMNS]


@pytest.mark.parametrize(
    ("own", "peer", "rising", "own_breach", "peer_breach", "candidate"),
    [
        (35.0, 21.0, True, True, True, True),
        (9.0, 24.0, True, False, True, True),
        (25.0, -5.0, True, True, False, True),
        (-5.0, 40.0, False, False, True, False),
        (0.0, 30.0, False, False, True, False),
        (20.0, 1.0, True, True, False, True),
        (1.0, 20.0, True, False, True, True),
        (None, 50.0, False, False, True, False),
        (25.0, None, True, True, False, True),
    ],
)
def test_complete_rule_matrix(
    own: float | None,
    peer: float | None,
    rising: bool,
    own_breach: bool,
    peer_breach: bool,
    candidate: bool,
) -> None:
    result = detect_candidate_anomalies(
        _frame(_comparison_row("A-B", own, peer)), 20.0
    ).iloc[0]

    assert result["is_rising"] == rising
    assert result["own_threshold_breached"] == own_breach
    assert result["peer_threshold_breached"] == peer_breach
    assert result["candidate_anomaly"] == candidate


@pytest.mark.parametrize("threshold", [-1, float("nan"), float("inf"), -float("inf"), "20"])
def test_invalid_threshold_fails(threshold: object) -> None:
    comparison = _frame(_comparison_row("A-B", 25.0, 25.0))

    with pytest.raises(CandidateDetectionError, match="threshold"):
        detect_candidate_anomalies(comparison, threshold)


@pytest.mark.parametrize("threshold", [0, Decimal("20.0"), 20.0])
def test_valid_numeric_thresholds_are_accepted(threshold: object) -> None:
    result = detect_candidate_anomalies(
        _frame(_comparison_row("A-B", 25.0, -5.0)), threshold
    )

    assert bool(result.loc[0, "candidate_anomaly"])


def test_candidate_decision_uses_full_precision_before_display_rounding() -> None:
    comparisons = _frame(
        _comparison_row("Below", 19.96, -5.0),
        _comparison_row("Equal", 20.0, -5.0),
        _comparison_row("Above", 20.0000001, -5.0),
    )

    result = detect_candidate_anomalies(comparisons, 20.0).set_index("route")

    assert not bool(result.loc["Below", "candidate_anomaly"])
    assert bool(result.loc["Equal", "candidate_anomaly"])
    assert bool(result.loc["Above", "candidate_anomaly"])
    assert f"{result.loc['Below', 'vs_own_history_pct']:+.1f}%" == "+20.0%"


def test_detection_is_deterministic_sorted_complete_and_immutable() -> None:
    comparisons = _frame(
        _comparison_row("C-D", 5.0, 25.0),
        _comparison_row("A-B", 25.0, 5.0),
    )
    original = comparisons.copy(deep=True)

    first = detect_candidate_anomalies(comparisons, 20.0)
    repeated = detect_candidate_anomalies(comparisons, 20.0)
    shuffled = detect_candidate_anomalies(
        comparisons.sample(frac=1, random_state=3), 20.0
    )

    pd.testing.assert_frame_equal(first, repeated)
    pd.testing.assert_frame_equal(first, shuffled)
    pd.testing.assert_frame_equal(comparisons, original)
    assert tuple(first.columns) == CANDIDATE_METRIC_COLUMNS
    assert not first[[
        "is_rising",
        "own_threshold_breached",
        "peer_threshold_breached",
        "candidate_anomaly",
    ]].isna().any().any()
