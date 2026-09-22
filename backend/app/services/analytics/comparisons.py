"""Full-precision percentage comparisons over canonical Phase 4 baselines."""

import logging
import math

import pandas as pd
from pandas.api.types import is_bool_dtype, is_integer_dtype, is_numeric_dtype

from ...core.logging import LOGGER_NAME
from .contracts import (
    ANALYTICS_GROUP_COLUMNS,
    BASELINE_METRIC_COLUMNS,
    COMPARISON_METRIC_COLUMNS,
    HISTORY_WINDOW_SIZE,
)
from .errors import AnalyticsInputError, CandidateDetectionError

logger = logging.getLogger(f"{LOGGER_NAME}.comparisons")

OWN_BASELINE = "own_history_avg_cost_per_tonne_km"
HISTORY_COUNT = "history_weeks_used"
PEER_BASELINE = "similar_routes_avg_cost_per_tonne_km"
PEER_COUNT = "peer_routes_used"
OWN_PERCENTAGE = "vs_own_history_pct"
PEER_PERCENTAGE = "vs_similar_routes_pct"


def add_percentage_comparisons(baseline_metrics: pd.DataFrame) -> pd.DataFrame:
    """Append numeric, unrounded deviations without mutating Phase 4 metrics."""
    working = validated_baseline_metrics_copy(baseline_metrics)
    working = working.sort_values(
        list(ANALYTICS_GROUP_COLUMNS), kind="mergesort"
    ).reset_index(drop=True)

    working[OWN_PERCENTAGE] = (
        working["cost_per_tonne_km"] / working[OWN_BASELINE] - 1
    ) * 100
    working[PEER_PERCENTAGE] = (
        working["cost_per_tonne_km"] / working[PEER_BASELINE] - 1
    ) * 100

    for percentage, baseline in (
        (OWN_PERCENTAGE, OWN_BASELINE),
        (PEER_PERCENTAGE, PEER_BASELINE),
    ):
        if not working[percentage].isna().equals(working[baseline].isna()):
            raise CandidateDetectionError(
                f"{percentage} availability must match {baseline}."
            )
        available = working[percentage].dropna()
        if not available.map(math.isfinite).all():
            raise CandidateDetectionError(
                f"Every available {percentage} value must be finite."
            )

    result = working.loc[:, COMPARISON_METRIC_COLUMNS].copy(deep=True)
    logger.info(
        "Calculated percentage comparisons rows=%d own_available=%d "
        "peer_available=%d precision=full",
        len(result),
        int(result[OWN_PERCENTAGE].notna().sum()),
        int(result[PEER_PERCENTAGE].notna().sum()),
    )
    return result


def validated_baseline_metrics_copy(baseline_metrics: pd.DataFrame) -> pd.DataFrame:
    """Validate the Phase 4 boundary without recalculating either baseline."""
    if not isinstance(baseline_metrics, pd.DataFrame):
        raise AnalyticsInputError("Comparison input must be a Pandas DataFrame.")
    duplicate_columns = sorted(
        {
            column
            for column in BASELINE_METRIC_COLUMNS
            if list(baseline_metrics.columns).count(column) > 1
        }
    )
    if duplicate_columns:
        raise AnalyticsInputError(
            "Comparison input contains duplicate Phase 4 columns: "
            + ", ".join(duplicate_columns)
            + "."
        )
    missing = [
        column
        for column in BASELINE_METRIC_COLUMNS
        if column not in baseline_metrics.columns
    ]
    if missing:
        raise AnalyticsInputError(
            "Comparison input is missing Phase 4 columns: " + ", ".join(missing) + "."
        )
    if tuple(baseline_metrics.columns) != BASELINE_METRIC_COLUMNS:
        raise AnalyticsInputError(
            "Comparison input columns must match the canonical Phase 4 order exactly."
        )
    if baseline_metrics.empty:
        raise AnalyticsInputError("Comparison input must contain baseline rows.")

    working = baseline_metrics.loc[:, BASELINE_METRIC_COLUMNS].copy(deep=True)
    if working.duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise AnalyticsInputError(
            "Comparison input must have unique route, route_type, and week_of keys."
        )
    _validate_positive_numeric(working, "cost_per_tonne_km", allow_missing=False)
    _validate_positive_numeric(working, OWN_BASELINE, allow_missing=True)
    _validate_positive_numeric(working, PEER_BASELINE, allow_missing=True)
    _validate_count(working, HISTORY_COUNT, upper=HISTORY_WINDOW_SIZE)
    _validate_count(working, PEER_COUNT)
    if not working[OWN_BASELINE].isna().equals(working[HISTORY_COUNT].eq(0)):
        raise AnalyticsInputError(
            "Own-history availability must match history_weeks_used."
        )
    if not working[PEER_BASELINE].isna().equals(working[PEER_COUNT].eq(0)):
        raise AnalyticsInputError("Peer-baseline availability must match peer_routes_used.")
    return working


def _validate_positive_numeric(
    frame: pd.DataFrame, column: str, *, allow_missing: bool
) -> None:
    series = frame[column]
    if is_bool_dtype(series.dtype) or not is_numeric_dtype(series.dtype):
        raise AnalyticsInputError(f"{column} must contain numeric values.")
    available = series.dropna() if allow_missing else series
    if not allow_missing and series.isna().any():
        raise AnalyticsInputError(f"{column} must not contain missing values.")
    if not available.map(math.isfinite).all() or (available <= 0).any():
        raise AnalyticsInputError(
            f"Every available {column} value must be finite and positive."
        )


def _validate_count(frame: pd.DataFrame, column: str, upper: int | None = None) -> None:
    series = frame[column]
    if is_bool_dtype(series.dtype) or not is_integer_dtype(series.dtype):
        raise AnalyticsInputError(f"{column} must be integer-valued.")
    if (series < 0).any() or (upper is not None and (series > upper).any()):
        limit = f" between zero and {upper}" if upper is not None else " non-negative"
        raise AnalyticsInputError(f"{column} must be{limit}.")
