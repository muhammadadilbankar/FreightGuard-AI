"""Analysis execution, summary, and exact-export routes."""

import hashlib
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ..dependencies import get_analysis_service, get_run_coordinator, get_snapshot_store
from ..schemas import (
    AnalysisSummaryData,
    AnalysisSummaryResponse,
    DataEnvelope,
    ResponseMeta,
    RunAnalysisData,
    RunAnalysisRequest,
    RunAnalysisResponse,
)
from ...application.analysis_service import AnalysisService
from ...state.errors import ExportNotAvailableError
from ...state.models import RunAnalysisCommand
from ...state.run_coordinator import RunCoordinator
from ...state.snapshot_store import SnapshotStore
from .common import ERROR_RESPONSES

router = APIRouter(tags=["analysis"])


@router.post("/analysis/run", response_model=RunAnalysisResponse, responses=ERROR_RESPONSES, operation_id="run_analysis")
async def run_analysis(
    body: RunAnalysisRequest,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> RunAnalysisResponse:
    result = await service.run(RunAnalysisCommand(body.explanation_mode))
    summary = result.snapshot.summary
    return DataEnvelope(
        data=RunAnalysisData(
            attempt_id=result.attempt_id,
            snapshot_id=result.snapshot.snapshot_id,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=result.duration_ms,
            shipment_count=summary.shipment_count,
            weekly_record_count=summary.weekly_record_count,
            candidate_count=summary.candidate_count,
            justified_count=summary.justified_count,
            partially_explained_count=summary.partially_explained_count,
            unexplained_count=summary.unexplained_count,
            evaluation_status=summary.evaluation_status,
            final_csv_sha256=summary.final_csv_sha256,
            replaced_previous_snapshot=result.replaced_previous_snapshot,
        ),
        meta=ResponseMeta(snapshot_id=result.snapshot.snapshot_id),
    )


@router.get("/analysis/summary", response_model=AnalysisSummaryResponse, responses=ERROR_RESPONSES, operation_id="get_analysis_summary")
def analysis_summary(
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    coordinator: Annotated[RunCoordinator, Depends(get_run_coordinator)],
) -> AnalysisSummaryResponse:
    snapshot = store.require()
    data = AnalysisSummaryData(
        **asdict(snapshot.summary), run_state=coordinator.status().state
    )
    return DataEnvelope(data=data, meta=ResponseMeta(snapshot_id=snapshot.snapshot_id))


@router.get("/analysis/export.csv", responses={200: {"content": {"text/csv": {}}}, **ERROR_RESPONSES}, operation_id="export_analysis_csv")
def export_csv(
    request: Request,
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
) -> Response:
    snapshot = store.require()
    try:
        content = snapshot.export_csv_path.read_bytes()
    except OSError as exc:
        raise ExportNotAvailableError(
            "The validated CSV artifact is unavailable."
        ) from exc
    if hashlib.sha256(content).hexdigest() != snapshot.export_csv_sha256:
        raise ExportNotAvailableError(
            "The validated CSV artifact failed its integrity check."
        )
    etag = f'"{snapshot.export_csv_sha256}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "ETag": etag,
            "Content-Disposition": f'attachment; filename="freightguard-analysis-{snapshot.snapshot_id}.csv"',
        },
    )
