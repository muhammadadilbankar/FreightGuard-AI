"""Shared isolated test fixtures."""

import pytest

from backend.app.core.config import get_settings


@pytest.fixture(autouse=True)
def isolate_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent cached settings or a developer `.env` from leaking between tests."""
    safe_environment = {
        "APP_NAME": "FreightGuard AI API",
        "APP_ENV": "development",
        "APP_VERSION": "0.1.0",
        "HOST": "127.0.0.1",
        "PORT": "8000",
        "LOG_LEVEL": "INFO",
        "INPUT_DATA_DIR": "backend/data/input",
        "OUTPUT_DATA_DIR": "backend/data/output",
        "ANOMALY_THRESHOLD_PERCENT": "20.0",
    }
    for name, value in safe_environment.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
