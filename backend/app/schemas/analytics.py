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


class BaselineSummary(BaseModel):
    """Concise audit summary for completed history and peer baselines."""

    model_config = ConfigDict(frozen=True)

    weekly_route_groups: int
    own_history_available: int
    own_history_unavailable: int
    full_history_rows: int
    peer_baselines_available: int
    peer_baselines_unavailable: int
    minimum_peers_used: int
    maximum_peers_used: int
    no_look_ahead_checks: Literal["PASS"] = "PASS"
    self_exclusion_checks: Literal["PASS"] = "PASS"
