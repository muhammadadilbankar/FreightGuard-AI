"""FastAPI dependency accessors for application-scoped services."""

from fastapi import Request

from ..application.analysis_service import AnalysisService
from ..core.config import Settings
from ..state.run_coordinator import RunCoordinator
from ..state.snapshot_store import SnapshotStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_snapshot_store(request: Request) -> SnapshotStore:
    return request.app.state.snapshot_store


def get_run_coordinator(request: Request) -> RunCoordinator:
    return request.app.state.run_coordinator


def get_analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service
