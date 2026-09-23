"""Liveness and readiness route."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ..dependencies import get_run_coordinator, get_settings, get_snapshot_store
from ..schemas import HealthResponse
from ...core.config import Settings
from ...state.run_coordinator import RunCoordinator
from ...state.snapshot_store import SnapshotStore

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, operation_id="get_health")
def health(
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[SnapshotStore, Depends(get_snapshot_store)],
    coordinator: Annotated[RunCoordinator, Depends(get_run_coordinator)],
) -> HealthResponse:
    snapshot = store.get()
    return HealthResponse(
        ready=snapshot is not None,
        service=settings.api_title,
        version=settings.api_version,
        run_state=coordinator.status().state,
        has_snapshot=snapshot is not None,
        snapshot_id=snapshot.snapshot_id if snapshot else None,
    )
