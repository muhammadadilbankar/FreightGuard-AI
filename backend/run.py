"""Local Uvicorn entry point for the FreightGuard API."""

import uvicorn

from app.core.config import get_settings


def main() -> None:
    """Run the API using configured network and logging settings."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.api_log_level.lower(),
        reload=False,
        workers=settings.api_workers,
    )


if __name__ == "__main__":
    main()
