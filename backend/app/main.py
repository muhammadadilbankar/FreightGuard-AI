"""Import-safe FastAPI application factory for the Phase 10 service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.error_handlers import install_error_handlers
from .api.middleware import RequestContextMiddleware
from .api.routes import api_router, health_router
from .application.analysis_service import AnalysisService
from .core.config import Settings, get_settings
from .core.logging import configure_logging
from .state.models import RunAnalysisCommand
from .state.run_coordinator import RunCoordinator
from .state.snapshot_store import SnapshotStore

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ServiceOverrides:
    snapshot_store: SnapshotStore | None = None
    run_coordinator: RunCoordinator | None = None
    analysis_service: AnalysisService | None = None


def create_app(
    settings: Settings | None = None,
    service_overrides: ServiceOverrides | None = None,
) -> FastAPI:
    """Create one process-local service container without running the pipeline."""
    app_settings = settings or get_settings()
    supplied = service_overrides or ServiceOverrides()
    store = supplied.snapshot_store or SnapshotStore()
    coordinator = supplied.run_coordinator or RunCoordinator()
    service = supplied.analysis_service or AnalysisService(
        app_settings, store, coordinator
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(app_settings.api_log_level)
        if app_settings.api_auto_run_on_startup:
            try:
                await service.run(RunAnalysisCommand(app_settings.explanation_mode))
            except Exception:
                LOGGER.exception("Automatic startup analysis failed safely.")
        yield

    application = FastAPI(
        title=app_settings.api_title,
        description=app_settings.api_description,
        version=app_settings.api_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.snapshot_store = store
    application.state.run_coordinator = coordinator
    application.state.analysis_service = service
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.api_allowed_origins),
        allow_credentials=app_settings.api_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "ETag", "Content-Disposition"],
    )
    application.add_middleware(
        RequestContextMiddleware,
        max_request_bytes=app_settings.api_max_request_bytes,
    )
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(api_router, prefix=app_settings.api_prefix)
    return application


app = create_app()
