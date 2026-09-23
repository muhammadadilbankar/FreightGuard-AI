"""Pure, deterministic projections over one immutable snapshot."""

from __future__ import annotations

from datetime import date

from ..domain.evidence import EvidenceVerdict
from ..state.errors import AnomalyNotFoundError, InvalidQueryError, RouteNotFoundError
from ..state.models import AnalysisSnapshot, AnomalyView, TimelinePoint

SORT_FIELDS = {
    "week_of",
    "route",
    "route_type",
    "cost_per_tonne_km",
    "vs_own_history_pct",
    "vs_similar_routes_pct",
    "verdict",
}


def list_anomalies(
    snapshot: AnalysisSnapshot,
    *,
    route: str | None = None,
    route_type: str | None = None,
    verdict: EvidenceVerdict | None = None,
    trigger: str | None = None,
    week_from: date | None = None,
    week_to: date | None = None,
    min_own_deviation_pct: float | None = None,
    min_peer_deviation_pct: float | None = None,
    sort_by: str = "week_of",
    sort_order: str = "asc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[tuple[AnomalyView, ...], int]:
    if week_from and week_to and week_from > week_to:
        raise InvalidQueryError("week_from must be on or before week_to.")
    if sort_by not in SORT_FIELDS or sort_order not in {"asc", "desc"}:
        raise InvalidQueryError("The requested sort is not supported.")
    items = tuple(
        item
        for item in snapshot.anomalies
        if (route is None or item.route == route)
        and (route_type is None or item.route_type == route_type)
        and (verdict is None or item.verdict == verdict)
        and (trigger is None or item.trigger == trigger)
        and (week_from is None or item.week_of >= week_from)
        and (week_to is None or item.week_of <= week_to)
        and (
            min_own_deviation_pct is None
            or item.vs_own_history_pct >= min_own_deviation_pct
        )
        and (
            min_peer_deviation_pct is None
            or (
                item.vs_similar_routes_pct is not None
                and item.vs_similar_routes_pct >= min_peer_deviation_pct
            )
        )
    )
    ordered = sorted(
        items,
        key=lambda item: (
            item.route,
            item.week_of,
            item.route_type,
            item.candidate_key,
        ),
    )
    available = [item for item in ordered if getattr(item, sort_by) is not None]
    unavailable = [item for item in ordered if getattr(item, sort_by) is None]
    ordered = sorted(
        available,
        key=lambda item: _sort_value(item, sort_by),
        reverse=sort_order == "desc",
    ) + unavailable
    return tuple(ordered[offset : offset + limit]), len(ordered)


def get_anomaly(snapshot: AnalysisSnapshot, route: str, week_of: date) -> AnomalyView:
    match = next(
        (
            item
            for item in snapshot.anomalies
            if item.route == route and item.week_of == week_of
        ),
        None,
    )
    if match is None:
        raise AnomalyNotFoundError("No anomaly exists for that route and week.")
    return match


def get_timeline(snapshot: AnalysisSnapshot, route: str) -> tuple[TimelinePoint, ...]:
    points = snapshot.route_timelines.get(route)
    if points is None:
        raise RouteNotFoundError("No analyzed route matches that identifier.")
    return points


def _sort_value(item: AnomalyView, field: str) -> object:
    value = getattr(item, field)
    if isinstance(value, EvidenceVerdict):
        return value.value
    return value
