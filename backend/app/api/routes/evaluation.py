"""Evaluation report endpoint served from the active snapshot."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import get_snapshot_store
from ..schemas import (
    DataEnvelope,
    EvaluationReportData,
    EvaluationReportResponse,
    ResponseMeta,
)
from ...state.errors import EvaluationNotAvailableError
from ...state.snapshot_store import SnapshotStore
from .common import ERROR_RESPONSES

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/report", response_model=EvaluationReportResponse, responses=ERROR_RESPONSES, operation_id="get_evaluation_report")
def evaluation_report(
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    include_checks: bool = True,
) -> EvaluationReportResponse:
    snapshot = store.require()
    if snapshot.evaluation is None or snapshot.evaluation_report_sha256 is None:
        raise EvaluationNotAvailableError(
            "The active snapshot has no evaluation report."
        )
    report = (
        snapshot.evaluation
        if include_checks
        else snapshot.evaluation.model_copy(update={"checks": ()})
    )
    return DataEnvelope(
        data=EvaluationReportData(
            report=report, report_sha256=snapshot.evaluation_report_sha256
        ),
        meta=ResponseMeta(snapshot_id=snapshot.snapshot_id),
    )
