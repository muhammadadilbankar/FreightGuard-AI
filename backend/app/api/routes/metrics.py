"""Safe latest-snapshot and latest-attempt metrics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import get_run_coordinator, get_snapshot_store
from ..schemas import (
    DataEnvelope,
    LatestAttemptData,
    ResponseMeta,
    RunMetricsData,
    RunMetricsResponse,
)
from ...state.run_coordinator import RunCoordinator
from ...state.snapshot_store import SnapshotStore
from .common import ERROR_RESPONSES

router = APIRouter(tags=["metrics"])


@router.get("/run-metrics", response_model=RunMetricsResponse, responses=ERROR_RESPONSES, operation_id="get_run_metrics")
def run_metrics(
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    coordinator: Annotated[RunCoordinator, Depends(get_run_coordinator)],
) -> RunMetricsResponse:
    snapshot = store.require()
    metrics = snapshot.run_metrics
    data = RunMetricsData(
        total_duration_ms=metrics.total_duration_ms,
        retrieval_hit_count=metrics.retrieval_hit_count,
        explanation_request_count=metrics.explanation_request_count,
        hosted_model_call_count=metrics.hosted_model_call_count,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        estimated_cost_usd=metrics.estimated_cost_usd,
        cache_hits=metrics.cache_hits,
        cache_misses=metrics.cache_misses,
        fallback_count=metrics.fallback_count,
        stage_durations_ms=dict(metrics.stage_durations_ms),
        row_counts=dict(metrics.row_counts),
        input_fingerprints=snapshot.input_fingerprints,
        configuration_fingerprint=snapshot.configuration_fingerprint,
        artifact_fingerprints=snapshot.artifact_fingerprints,
        latest_attempt=LatestAttemptData.model_validate(coordinator.status()),
    )
    return DataEnvelope(
        data=data, meta=ResponseMeta(snapshot_id=snapshot.snapshot_id)
    )
