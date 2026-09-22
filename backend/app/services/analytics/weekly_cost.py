"""Deterministic weighted weekly route-cost aggregation."""

import logging
import math

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

from ...core.logging import LOGGER_NAME
from ...schemas.analytics import WeeklyMetricsSummary
from .contracts import (
    ABSOLUTE_TOLERANCE,
    ANALYTICS_GROUP_COLUMNS,
    ANALYTICS_NUMERIC_COLUMNS,
    ANALYTICS_REQUIRED_COLUMNS,
    RELATIVE_TOLERANCE,
    WEEKLY_METRIC_COLUMNS,
)
from .errors import AnalyticsInputError, AnalyticsInvariantError

logger = logging.getLogger(f"{LOGGER_NAME}.analytics")


def calculate_weekly_route_metrics(shipments: pd.DataFrame) -> pd.DataFrame:
    """Calculate unrounded weighted metrics by route, route type, and Monday week."""
    working = _validated_working_copy(shipments)
    working = working.sort_values(
        [*ANALYTICS_GROUP_COLUMNS, "shipment_id"], kind="mergesort"
    ).reset_index(drop=True)
    logger.info("Starting weekly analytics shipments=%d", len(working))

    weekly = (
        working.groupby(
            list(ANALYTICS_GROUP_COLUMNS),
            sort=False,
            dropna=False,
            observed=True,
        )
        .agg(
            shipment_count=("shipment_id", "size"),
            total_freight_cost_inr=("freight_cost_inr", "sum"),
            total_quantity_tonnes=("quantity_tonnes", "sum"),
            total_tonne_km=("tonne_km", "sum"),
        )
        .reset_index()
    )

    _validate_aggregate_denominators(weekly)
    weekly["cost_per_tonne_km"] = (
        weekly["total_freight_cost_inr"] / weekly["total_tonne_km"]
    )
    weekly = (
        weekly.loc[:, WEEKLY_METRIC_COLUMNS]
        .sort_values(list(ANALYTICS_GROUP_COLUMNS), kind="mergesort")
        .reset_index(drop=True)
    )

    validate_weekly_metrics_reconciliation(working, weekly)
    logger.info(
        "Completed weekly analytics groups=%d routes=%d weeks=%d reconciliation=PASS",
        len(weekly),
        weekly["route"].nunique(),
        weekly["week_of"].nunique(),
    )
    return weekly


def validate_weekly_metrics_reconciliation(
    shipments: pd.DataFrame, weekly_metrics: pd.DataFrame
) -> None:
    """Raise when grouped metrics do not reconcile to their shipment inputs."""
    missing = [
        column for column in WEEKLY_METRIC_COLUMNS if column not in weekly_metrics.columns
    ]
    if missing:
        raise AnalyticsInvariantError(
            "Weekly metrics are missing reconciliation columns: "
            + ", ".join(missing)
            + "."
        )
    if weekly_metrics.duplicated(list(ANALYTICS_GROUP_COLUMNS)).any():
        raise AnalyticsInvariantError(
            "Weekly metrics contain duplicate route, route_type, and week_of keys."
        )
    if int(weekly_metrics["shipment_count"].sum()) != len(shipments):
        raise AnalyticsInvariantError(
            "Weekly shipment counts do not reconcile to the shipment input."
        )

    _reconcile_sum(
        weekly_metrics["total_freight_cost_inr"].sum(),
        shipments["freight_cost_inr"].sum(),
        "freight cost",
    )
    _reconcile_sum(
        weekly_metrics["total_quantity_tonnes"].sum(),
        shipments["quantity_tonnes"].sum(),
        "quantity",
    )
    _reconcile_sum(
        weekly_metrics["total_tonne_km"].sum(),
        shipments["tonne_km"].sum(),
        "tonne-kilometres",
    )

    expected_rates = (
        weekly_metrics["total_freight_cost_inr"]
        / weekly_metrics["total_tonne_km"]
    )
    if not _series_close(weekly_metrics["cost_per_tonne_km"], expected_rates).all():
        raise AnalyticsInvariantError(
            "Weekly cost-per-tonne-kilometre values do not reconcile to totals."
        )


def summarize_weekly_metrics(
    shipments: pd.DataFrame, weekly_metrics: pd.DataFrame
) -> WeeklyMetricsSummary:
    """Create the typed summary used by the read-only inspection command."""
    validate_weekly_metrics_reconciliation(shipments, weekly_metrics)
    return WeeklyMetricsSummary(
        validated_shipments=len(shipments),
        weekly_route_groups=len(weekly_metrics),
        directional_routes=int(weekly_metrics["route"].nunique()),
        route_types=int(weekly_metrics["route_type"].nunique()),
        distinct_weeks=int(weekly_metrics["week_of"].nunique()),
        earliest_week_of=weekly_metrics["week_of"].min().date(),
        latest_week_of=weekly_metrics["week_of"].max().date(),
    )


def _validated_working_copy(shipments: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(shipments, pd.DataFrame):
        raise AnalyticsInputError("Analytics input must be a Pandas DataFrame.")

    duplicate_columns = sorted(
        {
            column
            for column in ANALYTICS_REQUIRED_COLUMNS
            if list(shipments.columns).count(column) > 1
        }
    )
    if duplicate_columns:
        raise AnalyticsInputError(
            "Analytics input contains duplicate required columns: "
            + ", ".join(duplicate_columns)
            + "."
        )
    missing_columns = [
        column for column in ANALYTICS_REQUIRED_COLUMNS if column not in shipments.columns
    ]
    if missing_columns:
        raise AnalyticsInputError(
            "Analytics input is missing required columns: "
            + ", ".join(missing_columns)
            + "."
        )
    if shipments.empty:
        raise AnalyticsInputError("Analytics input must contain at least one shipment.")

    working = shipments.loc[:, ANALYTICS_REQUIRED_COLUMNS].copy(deep=True)
    _validate_identifiers_and_group_keys(working)
    _validate_and_normalize_weeks(working)
    _validate_numeric_inputs(working)
    _validate_tonne_km_consistency(working)
    return working


def _validate_identifiers_and_group_keys(frame: pd.DataFrame) -> None:
    if frame["shipment_id"].isna().any():
        raise AnalyticsInputError("shipment_id must not contain null values.")
    identifiers = frame["shipment_id"].map(
        lambda value: value.strip() if isinstance(value, str) else ""
    )
    if identifiers.eq("").any():
        raise AnalyticsInputError("shipment_id must contain non-blank strings.")
    if identifiers.duplicated().any():
        raise AnalyticsInputError("shipment_id values must be unique.")

    for column in ("route", "route_type"):
        if frame[column].isna().any():
            raise AnalyticsInputError(f"{column} must not contain null values.")
        values = frame[column].map(
            lambda value: value.strip() if isinstance(value, str) else ""
        )
        if values.eq("").any():
            raise AnalyticsInputError(f"{column} must contain non-blank strings.")


def _validate_and_normalize_weeks(frame: pd.DataFrame) -> None:
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


def _validate_numeric_inputs(frame: pd.DataFrame) -> None:
    for column in ANALYTICS_NUMERIC_COLUMNS:
        series = frame[column]
        if is_bool_dtype(series.dtype) or not is_numeric_dtype(series.dtype):
            raise AnalyticsInputError(f"{column} must contain numeric values.")
        if series.isna().any() or not series.map(math.isfinite).all():
            raise AnalyticsInputError(f"{column} must contain only finite values.")
        if (series <= 0).any():
            raise AnalyticsInputError(f"{column} must be strictly greater than zero.")


def _validate_tonne_km_consistency(frame: pd.DataFrame) -> None:
    expected = frame["quantity_tonnes"] * frame["distance_km"]
    if not _series_close(frame["tonne_km"], expected).all():
        raise AnalyticsInputError(
            "tonne_km must match quantity_tonnes multiplied by distance_km."
        )


def _validate_aggregate_denominators(weekly: pd.DataFrame) -> None:
    denominator = weekly["total_tonne_km"]
    if denominator.isna().any() or not denominator.map(math.isfinite).all():
        raise AnalyticsInvariantError(
            "Every aggregate total_tonne_km denominator must be finite."
        )
    if (denominator <= 0).any():
        raise AnalyticsInvariantError(
            "Every aggregate total_tonne_km denominator must be positive."
        )


def _series_close(left: pd.Series, right: pd.Series) -> pd.Series:
    difference = (left - right).abs()
    limit = ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * right.abs()
    return difference <= limit


def _reconcile_sum(actual: float, expected: float, label: str) -> None:
    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=ABSOLUTE_TOLERANCE,
    ):
        raise AnalyticsInvariantError(
            f"Weekly {label} totals do not reconcile to the shipment input."
        )
