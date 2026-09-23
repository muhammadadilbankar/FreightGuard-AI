"""Filtered anomaly and route timeline read endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_settings, get_snapshot_store
from ..schemas import (
    AnomalyData,
    AnomalyDetailResponse,
    AnomalyListData,
    AnomalyListResponse,
    DataEnvelope,
    PaginationMeta,
    ResponseMeta,
    RouteTimelineData,
    RouteTimelineResponse,
    RootCauseData,
    RootCauseResponse,
    TimelinePointData,
)
from ...application.snapshot_queries import (
    get_anomaly,
    get_root_cause,
    get_timeline,
    list_anomalies,
)
from ...core.config import Settings
from ...domain.evidence import EvidenceVerdict
from ...state.errors import InvalidQueryError
from ...state.snapshot_store import SnapshotStore
from .common import ERROR_RESPONSES, validate_monday, validate_weeks

router = APIRouter(tags=["anomalies"])


@router.get(
    "/anomalies/{route}/{week_of}/root-cause",
    response_model=RootCauseResponse,
    responses=ERROR_RESPONSES,
    operation_id="get_anomaly_root_cause",
)
def anomaly_root_cause(
    route: str,
    week_of: date,
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
) -> RootCauseResponse:
    validate_monday(week_of)
    snapshot = store.require()
    result = get_root_cause(snapshot, route, week_of)
    return DataEnvelope(
        data=RootCauseData.model_validate(result),
        meta=ResponseMeta(snapshot_id=snapshot.snapshot_id),
    )


@router.get("/anomalies", response_model=AnomalyListResponse, responses=ERROR_RESPONSES, operation_id="list_anomalies")
def anomalies(
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    route: str | None = None,
    route_type: str | None = None,
    verdict: EvidenceVerdict | None = None,
    trigger: Literal["own_history", "peer", "both"] | None = None,
    week_from: date | None = None,
    week_to: date | None = None,
    min_own_deviation_pct: float | None = None,
    min_peer_deviation_pct: float | None = None,
    sort_by: Literal[
        "week_of", "route", "route_type", "cost_per_tonne_km",
        "vs_own_history_pct", "vs_similar_routes_pct", "verdict"
    ] = "week_of",
    sort_order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnomalyListResponse:
    validate_weeks(week_from, week_to)
    page_size = limit or settings.api_default_page_size
    if page_size > settings.api_max_page_size:
        raise InvalidQueryError("limit exceeds the configured maximum.")
    snapshot = store.require()
    items, total = list_anomalies(
        snapshot, route=route, route_type=route_type, verdict=verdict,
        trigger=trigger, week_from=week_from, week_to=week_to,
        min_own_deviation_pct=min_own_deviation_pct,
        min_peer_deviation_pct=min_peer_deviation_pct,
        sort_by=sort_by, sort_order=sort_order, limit=page_size, offset=offset,
    )
    return DataEnvelope(
        data=AnomalyListData(
            items=tuple(AnomalyData.model_validate(item) for item in items)
        ),
        meta=ResponseMeta(
            snapshot_id=snapshot.snapshot_id,
            pagination=PaginationMeta(
                total=total, limit=page_size, offset=offset,
                has_more=offset + page_size < total,
            ),
        ),
    )


@router.get("/anomalies/{route}/{week_of}", response_model=AnomalyDetailResponse, responses=ERROR_RESPONSES, operation_id="get_anomaly")
def anomaly_detail(
    route: str,
    week_of: date,
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
) -> AnomalyDetailResponse:
    validate_monday(week_of)
    snapshot = store.require()
    item = get_anomaly(snapshot, route, week_of)
    return DataEnvelope(
        data=AnomalyData.model_validate(item),
        meta=ResponseMeta(snapshot_id=snapshot.snapshot_id),
    )


@router.get("/routes/{route}/timeline", response_model=RouteTimelineResponse, responses=ERROR_RESPONSES, operation_id="get_route_timeline", tags=["routes"])
def route_timeline(
    route: str,
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    week_from: date | None = None,
    week_to: date | None = None,
) -> RouteTimelineResponse:
    validate_weeks(week_from, week_to)
    snapshot = store.require()
    points = tuple(
        point
        for point in get_timeline(snapshot, route)
        if (week_from is None or point.week_of >= week_from)
        and (week_to is None or point.week_of <= week_to)
    )
    return DataEnvelope(
        data=RouteTimelineData(
            route=route,
            points=tuple(TimelinePointData.model_validate(point) for point in points),
        ),
        meta=ResponseMeta(snapshot_id=snapshot.snapshot_id),
    )
