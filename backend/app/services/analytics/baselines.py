"""Leak-free route-history and self-excluding peer baseline calculations."""

import logging
import math

import pandas as pd
from pandas.api.types import is_bool_dtype, is_integer_dtype, is_numeric_dtype

from ...core.logging import LOGGER_NAME
from ...schemas.analytics import BaselineSummary
from ..ingestion.contracts import ALLOWED_ROUTE_TYPES
from .contracts import (
    ABSOLUTE_TOLERANCE,
    ANALYTICS_GROUP_COLUMNS,
    BASELINE_METRIC_COLUMNS,
    HISTORY_PARTITION_COLUMNS,
    HISTORY_WINDOW_SIZE,
    PEER_GROUP_COLUMNS,
    RELATIVE_TOLERANCE,
    WEEKLY_METRIC_COLUMNS,
)
from .errors import AnalyticsInputError, AnalyticsInvariantError

logger = logging.getLogger(f"{LOGGER_NAME}.baselines")

OWN_HISTORY_COLUMN = "own_history_avg_cost_per_tonne_km"
HISTORY_COUNT_COLUMN = "history_weeks_used"
PEER_BASELINE_COLUMN = "similar_routes_avg_cost_per_tonne_km"
PEER_COUNT_COLUMN = "peer_routes_used"


def add_comparison_baselines(weekly_metrics: pd.DataFrame) -> pd.DataFrame:
    """Append unrounded prior-history and self-excluding peer comparisons."""
    working = _validated_weekly_copy(weekly_metrics)
    working = working.sort_values(
        list(ANALYTICS_GROUP_COLUMNS), kind="mergesort"
    ).reset_index(drop=True)
    logger.info("Starting baseline analytics weekly_rows=%d", len(working))

    working[OWN_HISTORY_COLUMN] = _calculate_history_baseline(working)
    working[HISTORY_COUNT_COLUMN] = (
        working.groupby(
            list(HISTORY_PARTITION_COLUMNS), sort=False, observed=True
        )
        .cumcount()
        .clip(upper=HISTORY_WINDOW_SIZE)
        .astype("int64")
    )

    peer_groups = working.groupby(
        list(PEER_GROUP_COLUMNS), sort=False, observed=True
    )["cost_per_tonne_km"]
    peer_group_sum = peer_groups.transform("sum")
    peer_group_size = peer_groups.transform("size").astype("int64")
    working[PEER_COUNT_COLUMN] = (peer_group_size - 1).astype("int64")
    working[PEER_BASELINE_COLUMN] = (
        peer_group_sum - working["cost_per_tonne_km"]
    ) / working[PEER_COUNT_COLUMN]
    working.loc[working[PEER_COUNT_COLUMN] == 0, PEER_BASELINE_COLUMN] = float(
        "nan"
    )

    enriched = working.loc[:, BASELINE_METRIC_COLUMNS].copy(deep=True)
    validate_baseline_reconciliation(weekly_metrics, enriched)
    logger.info(
        "Completed baseline analytics rows=%d history_available=%d "
        "history_unavailable=%d peer_available=%d peer_unavailable=%d "
        "history_count_min=%d history_count_max=%d peer_count_min=%d "
        "peer_count_max=%d invariants=PASS",
        len(enriched),
        int(enriched[OWN_HISTORY_COLUMN].notna().sum()),
        int(enriched[OWN_HISTORY_COLUMN].isna().sum()),
        int(enriched[PEER_BASELINE_COLUMN].notna().sum()),
        int(enriched[PEER_BASELINE_COLUMN].isna().sum()),
        int(enriched[HISTORY_COUNT_COLUMN].min()),
        int(enriched[HISTORY_COUNT_COLUMN].max()),
        int(enriched[PEER_COUNT_COLUMN].min()),
        int(enriched[PEER_COUNT_COLUMN].max()),
    )
    return enriched


def validate_baseline_reconciliation(
    weekly_metrics: pd.DataFrame, enriched_metrics: pd.DataFrame
) -> None:
    """Verify row, key, value, availability, window, and peer invariants."""
    if tuple(enriched_metrics.columns) != BASELINE_METRIC_COLUMNS:
        raise AnalyticsInvariantError(
            "Baseline metrics do not use the canonical Phase 4 column order."
        )
    if len(enriched_metrics) != len(weekly_metrics):
        raise AnalyticsInvariantError(
            "Baseline row count does not preserve every Phase 3 weekly row."
        )

    expected = _validated_weekly_copy(weekly_metrics)
    expected = expected.sort_values(
        list(ANALYTICS_GROUP_COLUMNS), kind="mergesort"
    ).reset_index(drop=True)
    if not enriched_metrics.loc[:, WEEKLY_METRIC_COLUMNS].equals(expected):
        raise AnalyticsInvariantError(
            "Baseline enrichment changed a canonical Phase 3 key or value."
        )
    if enriched_metrics.duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise AnalyticsInvariantError(
            "Baseline metrics contain duplicate route, route_type, and week_of keys."
        )

    history_counts = enriched_metrics[HISTORY_COUNT_COLUMN]
    if not is_integer_dtype(history_counts.dtype):
        raise AnalyticsInvariantError("history_weeks_used must be integer-valued.")
    if not history_counts.between(0, HISTORY_WINDOW_SIZE).all():
        raise AnalyticsInvariantError(
            "history_weeks_used must remain between zero and eight."
        )
    expected_history_counts = (
        expected.groupby(
            list(HISTORY_PARTITION_COLUMNS), sort=False, observed=True
        )
        .cumcount()
        .clip(upper=HISTORY_WINDOW_SIZE)
        .astype("int64")
    )
    if not history_counts.equals(expected_history_counts):
        raise AnalyticsInvariantError(
            "history_weeks_used does not match prior available observations."
        )
    history_missing = enriched_metrics[OWN_HISTORY_COLUMN].isna()
    if not history_missing.equals(history_counts.eq(0)):
        raise AnalyticsInvariantError(
            "Own-history availability must match history_weeks_used."
        )
    expected_history = _calculate_history_baseline(expected)
    if not _series_equal_with_missing(
        enriched_metrics[OWN_HISTORY_COLUMN], expected_history
    ):
        raise AnalyticsInvariantError(
            "Own-history baselines do not match the shifted eight-observation window."
        )

    peer_counts = enriched_metrics[PEER_COUNT_COLUMN]
    if not is_integer_dtype(peer_counts.dtype):
        raise AnalyticsInvariantError("peer_routes_used must be integer-valued.")
    if (peer_counts < 0).any():
        raise AnalyticsInvariantError("peer_routes_used must not be negative.")
    expected_peer_counts = (
        expected.groupby(list(PEER_GROUP_COLUMNS), observed=True)["route"]
        .transform("size")
        .sub(1)
        .astype("int64")
    )
    if not peer_counts.equals(expected_peer_counts):
        raise AnalyticsInvariantError(
            "peer_routes_used must equal the same-week route-type group size minus one."
        )
    peer_missing = enriched_metrics[PEER_BASELINE_COLUMN].isna()
    if not peer_missing.equals(peer_counts.eq(0)):
        raise AnalyticsInvariantError(
            "Peer-baseline availability must match peer_routes_used."
        )

    peer_group_sum = expected.groupby(
        list(PEER_GROUP_COLUMNS), observed=True
    )["cost_per_tonne_km"].transform("sum")
    expected_peer = (
        peer_group_sum - expected["cost_per_tonne_km"]
    ) / expected_peer_counts
    expected_peer = expected_peer.mask(expected_peer_counts == 0)
    if not _series_equal_with_missing(
        enriched_metrics[PEER_BASELINE_COLUMN], expected_peer
    ):
        raise AnalyticsInvariantError(
            "Peer baselines must exclude the current route and average peers equally."
        )

    for column in (OWN_HISTORY_COLUMN, PEER_BASELINE_COLUMN):
        available = enriched_metrics[column].dropna()
        if not available.map(math.isfinite).all() or (available <= 0).any():
            raise AnalyticsInvariantError(
                f"Every available {column} value must be finite and positive."
            )


def summarize_baselines(enriched_metrics: pd.DataFrame) -> BaselineSummary:
    """Create the typed audit summary used by the baseline inspection command."""
    required = set(BASELINE_METRIC_COLUMNS)
    if not required.issubset(enriched_metrics.columns):
        raise AnalyticsInputError(
            "Baseline summary requires the canonical Phase 4 metrics columns."
        )
    own_available = int(enriched_metrics[OWN_HISTORY_COLUMN].notna().sum())
    peer_available = int(enriched_metrics[PEER_BASELINE_COLUMN].notna().sum())
    return BaselineSummary(
        weekly_route_groups=len(enriched_metrics),
        own_history_available=own_available,
        own_history_unavailable=len(enriched_metrics) - own_available,
        full_history_rows=int(
            enriched_metrics[HISTORY_COUNT_COLUMN].eq(HISTORY_WINDOW_SIZE).sum()
        ),
        peer_baselines_available=peer_available,
        peer_baselines_unavailable=len(enriched_metrics) - peer_available,
        minimum_peers_used=int(enriched_metrics[PEER_COUNT_COLUMN].min()),
        maximum_peers_used=int(enriched_metrics[PEER_COUNT_COLUMN].max()),
    )


def _validated_weekly_copy(weekly_metrics: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(weekly_metrics, pd.DataFrame):
        raise AnalyticsInputError("Baseline input must be a Pandas DataFrame.")
    duplicate_columns = sorted(
        {
            column
            for column in WEEKLY_METRIC_COLUMNS
            if list(weekly_metrics.columns).count(column) > 1
        }
    )
    if duplicate_columns:
        raise AnalyticsInputError(
            "Baseline input contains duplicate Phase 3 columns: "
            + ", ".join(duplicate_columns)
            + "."
        )
    missing_columns = [
        column for column in WEEKLY_METRIC_COLUMNS if column not in weekly_metrics.columns
    ]
    if missing_columns:
        raise AnalyticsInputError(
            "Baseline input is missing Phase 3 columns: "
            + ", ".join(missing_columns)
            + "."
        )
    if tuple(weekly_metrics.columns) != WEEKLY_METRIC_COLUMNS:
        raise AnalyticsInputError(
            "Baseline input columns must match the canonical Phase 3 order exactly."
        )
    if weekly_metrics.empty:
        raise AnalyticsInputError("Baseline input must contain weekly metrics rows.")

    working = weekly_metrics.loc[:, WEEKLY_METRIC_COLUMNS].copy(deep=True)
    for column in ("route", "route_type"):
        if working[column].isna().any():
            raise AnalyticsInputError(f"{column} must not contain null values.")
        values = working[column].map(
            lambda value: value.strip() if isinstance(value, str) else ""
        )
        if values.eq("").any():
            raise AnalyticsInputError(f"{column} must contain non-blank strings.")
    if not working["route_type"].isin(ALLOWED_ROUTE_TYPES).all():
        raise AnalyticsInputError(
            "route_type must contain only Short, Medium, or Long."
        )

    _validate_weeks(working)
    if working.duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise AnalyticsInputError(
            "Baseline input must have unique route, route_type, and week_of keys."
        )
    _validate_phase_three_audit_values(working)
    return working


def _validate_weeks(frame: pd.DataFrame) -> None:
    try:
        parsed = pd.to_datetime(frame["week_of"], errors="coerce")
    except (TypeError, ValueError) as exc:
        raise AnalyticsInputError("week_of must contain valid date-like values.") from exc
    if parsed.isna().any():
        raise AnalyticsInputError("week_of must contain valid date-like values.")
    try:
        timezone = parsed.dt.tz
        normalized = parsed.dt.normalize()
        weekdays = parsed.dt.weekday
    except AttributeError as exc:
        raise AnalyticsInputError(
            "week_of must use one consistent date-like representation."
        ) from exc
    if timezone is not None:
        raise AnalyticsInputError("week_of must be timezone-naive.")
    if (parsed != normalized).any():
        raise AnalyticsInputError("week_of must contain normalized dates at midnight.")
    if (weekdays != 0).any():
        raise AnalyticsInputError("Every week_of value must be a Monday.")
    frame["week_of"] = parsed


def _validate_phase_three_audit_values(frame: pd.DataFrame) -> None:
    if (
        is_bool_dtype(frame["shipment_count"].dtype)
        or not is_integer_dtype(frame["shipment_count"].dtype)
        or (frame["shipment_count"] <= 0).any()
    ):
        raise AnalyticsInputError("shipment_count must contain positive integers.")
    for column in (
        "total_freight_cost_inr",
        "total_quantity_tonnes",
        "total_tonne_km",
        "cost_per_tonne_km",
    ):
        series = frame[column]
        if is_bool_dtype(series.dtype) or not is_numeric_dtype(series.dtype):
            raise AnalyticsInputError(f"{column} must contain numeric values.")
        if series.isna().any() or not series.map(math.isfinite).all():
            raise AnalyticsInputError(f"{column} must contain only finite values.")
        if (series <= 0).any():
            raise AnalyticsInputError(f"{column} must be strictly greater than zero.")

    expected_rate = frame["total_freight_cost_inr"] / frame["total_tonne_km"]
    if not _series_close(frame["cost_per_tonne_km"], expected_rate).all():
        raise AnalyticsInputError(
            "cost_per_tonne_km must reconcile to Phase 3 freight and tonne-km totals."
        )


def _calculate_history_baseline(frame: pd.DataFrame) -> pd.Series:
    return frame.groupby(
        list(HISTORY_PARTITION_COLUMNS), sort=False, observed=True
    )["cost_per_tonne_km"].transform(
        lambda values: values.shift(1).rolling(
            window=HISTORY_WINDOW_SIZE, min_periods=1
        ).mean()
    )


def _series_close(left: pd.Series, right: pd.Series) -> pd.Series:
    difference = (left - right).abs()
    limit = ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * right.abs()
    return difference <= limit


def _series_equal_with_missing(left: pd.Series, right: pd.Series) -> bool:
    missing_matches = left.isna().equals(right.isna())
    available = left.notna() & right.notna()
    return missing_matches and bool(_series_close(left[available], right[available]).all())
