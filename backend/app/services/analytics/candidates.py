"""Deterministic candidate-anomaly rule over full-precision comparisons."""

import logging
import math
from decimal import Decimal
from numbers import Real

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from ...core.logging import LOGGER_NAME
from .contracts import (
    ANALYTICS_GROUP_COLUMNS,
    CANDIDATE_METRIC_COLUMNS,
    CANDIDATE_RULE_COLUMNS,
    COMPARISON_METRIC_COLUMNS,
)
from .errors import AnalyticsInputError, CandidateDetectionError

logger = logging.getLogger(f"{LOGGER_NAME}.candidates")

OWN_PERCENTAGE = "vs_own_history_pct"
PEER_PERCENTAGE = "vs_similar_routes_pct"


def detect_candidate_anomalies(
    comparison_metrics: pd.DataFrame, threshold_percent: float
) -> pd.DataFrame:
    """Append complete Boolean rule components using an injected threshold."""
    threshold = _validated_threshold(threshold_percent)
    working = _validated_comparison_copy(comparison_metrics)
    working = working.sort_values(
        list(ANALYTICS_GROUP_COLUMNS), kind="mergesort"
    ).reset_index(drop=True)

    own_available = working[OWN_PERCENTAGE].notna()
    peer_available = working[PEER_PERCENTAGE].notna()
    working["is_rising"] = own_available & working[OWN_PERCENTAGE].gt(0)
    working["own_threshold_breached"] = own_available & working[
        OWN_PERCENTAGE
    ].ge(threshold)
    working["peer_threshold_breached"] = peer_available & working[
        PEER_PERCENTAGE
    ].ge(threshold)
    working["candidate_anomaly"] = working["is_rising"] & (
        working["own_threshold_breached"]
        | working["peer_threshold_breached"]
    )

    for column in CANDIDATE_RULE_COLUMNS:
        working[column] = working[column].astype(bool)
        if working[column].isna().any() or not is_bool_dtype(working[column].dtype):
            raise CandidateDetectionError(
                f"{column} must contain non-null Boolean decisions."
            )

    expected = working["is_rising"] & (
        working["own_threshold_breached"]
        | working["peer_threshold_breached"]
    )
    if not working["candidate_anomaly"].equals(expected):
        raise CandidateDetectionError("Candidate decisions do not match the rule.")
    candidates = working["candidate_anomaly"]
    if (candidates & ~working[OWN_PERCENTAGE].gt(0)).any():
        raise CandidateDetectionError(
            "Every candidate must have a positive own-history deviation."
        )
    if working.loc[candidates].duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise CandidateDetectionError("Candidate metric keys must remain unique.")

    result = working.loc[:, CANDIDATE_METRIC_COLUMNS].copy(deep=True)
    logger.info(
        "Applied candidate rule rows=%d threshold=%.10g own_breaches=%d "
        "peer_breaches=%d candidates=%d",
        len(result),
        threshold,
        int(result["own_threshold_breached"].sum()),
        int(result["peer_threshold_breached"].sum()),
        int(result["candidate_anomaly"].sum()),
    )
    return result


def _validated_threshold(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (Real, Decimal)):
        raise CandidateDetectionError("Candidate threshold must be numeric.")
    threshold = float(value)
    if not math.isfinite(threshold) or threshold < 0:
        raise CandidateDetectionError(
            "Candidate threshold must be finite and non-negative."
        )
    return threshold


def _validated_comparison_copy(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise AnalyticsInputError("Candidate input must be a Pandas DataFrame.")
    if tuple(frame.columns) != COMPARISON_METRIC_COLUMNS:
        raise AnalyticsInputError(
            "Candidate input columns must match the canonical comparison order exactly."
        )
    if frame.empty:
        raise AnalyticsInputError("Candidate input must contain comparison rows.")
    working = frame.loc[:, COMPARISON_METRIC_COLUMNS].copy(deep=True)
    if working.duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise AnalyticsInputError(
            "Candidate input must have unique route, route_type, and week_of keys."
        )
    for percentage, baseline in (
        (OWN_PERCENTAGE, "own_history_avg_cost_per_tonne_km"),
        (PEER_PERCENTAGE, "similar_routes_avg_cost_per_tonne_km"),
    ):
        series = working[percentage]
        if is_bool_dtype(series.dtype):
            raise AnalyticsInputError(f"{percentage} must contain numeric values.")
        if not is_numeric_dtype(series.dtype):
            if series.isna().all():
                working[percentage] = series.astype("float64")
                series = working[percentage]
            else:
                raise AnalyticsInputError(
                    f"{percentage} must contain numeric values."
                )
        if not series.isna().equals(working[baseline].isna()):
            raise AnalyticsInputError(
                f"{percentage} availability must match {baseline}."
            )
        if not series.dropna().map(math.isfinite).all():
            raise AnalyticsInputError(
                f"Every available {percentage} value must be finite."
            )
    return working
