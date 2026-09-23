"""Run the single-worker Phase 10 API with explicit configured bounds."""

import uvicorn

from backend.app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "backend.app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=1,
        log_level=settings.api_log_level.lower(),
    )


if __name__ == "__main__":
    main()
