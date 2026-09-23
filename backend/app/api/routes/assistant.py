"""Natural-language investigation endpoint over the active snapshot."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ...domain.assistant import AssistantRequest, AssistantResponseEnvelope
from ...services.assistant import InvestigationAssistantService
from ...state.snapshot_store import SnapshotStore
from ..dependencies import get_assistant_service, get_snapshot_store
from .common import ERROR_RESPONSES

router = APIRouter(tags=["assistant"])


@router.post(
    "/assistant/query",
    response_model=AssistantResponseEnvelope,
    responses=ERROR_RESPONSES,
    operation_id="query_investigation_assistant",
)
def query_assistant(
    body: AssistantRequest,
    request: Request,
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    service: Annotated[
        InvestigationAssistantService, Depends(get_assistant_service)
    ],
) -> AssistantResponseEnvelope:
    snapshot = store.require()
    return service.query(
        body,
        snapshot,
        request_id=request.state.request_id,
    )
