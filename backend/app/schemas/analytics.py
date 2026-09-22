"""Typed summaries exposed by the weekly analytics inspection boundary."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WeeklyMetricsSummary(BaseModel):
    """Concise audit summary for a completed weekly aggregation."""

    model_config = ConfigDict(frozen=True)

    validated_shipments: int
    weekly_route_groups: int
    directional_routes: int
    route_types: int
    distinct_weeks: int
    earliest_week_of: date
    latest_week_of: date
    reconciliation: Literal["PASS"] = "PASS"
