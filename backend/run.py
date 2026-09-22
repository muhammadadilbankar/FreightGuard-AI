"""Local Uvicorn entry point for the FreightGuard API."""

import uvicorn

from app.core.config import get_settings


def main() -> None:
    """Run the API using configured network and logging settings."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.app_env.lower() == "development",
    )


if __name__ == "__main__":
    main()
