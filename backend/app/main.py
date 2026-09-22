"""FastAPI application bootstrap."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from .api.health import router as health_router
from .core.config import Settings, get_settings
from .core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a configured FastAPI application without external dependencies."""
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(app_settings.log_level)
        yield

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.include_router(health_router)
    return application


app = create_app()
