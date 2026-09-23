"""Exact Phase 4 previous-observation reference-window selection."""

from datetime import date

import pandas as pd

from ..analytics.contracts import HISTORY_WINDOW_SIZE


def resolve_reference_weeks(
    weekly: pd.DataFrame, *, route: str, route_type: str, week_of: date
) -> tuple[date, ...]:
    """Return the prior at most eight observed route weeks, sorted ascending."""
    weeks = pd.to_datetime(
        weekly.loc[
            (weekly["route"] == route)
            & (weekly["route_type"] == route_type)
            & (pd.to_datetime(weekly["week_of"]).dt.date < week_of),
            "week_of",
        ]
    ).drop_duplicates()
    selected = sorted(value.date() for value in weeks)[-HISTORY_WINDOW_SIZE:]
    return tuple(selected)
