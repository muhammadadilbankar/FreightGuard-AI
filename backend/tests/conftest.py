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
        "EXPLANATION_MODE": "template",
        "EXPLANATION_PROVIDER": "openai",
        "EXPLANATION_MODEL": "",
        "EXPLANATION_PROMPT_VERSION": "fg-explanation-v1",
        "EXPLANATION_TEMPERATURE": "0",
        "EXPLANATION_TEMPERATURE_SUPPORTED": "false",
        "EXPLANATION_MAX_OUTPUT_TOKENS": "220",
        "EXPLANATION_TIMEOUT_SECONDS": "30",
        "EXPLANATION_MAX_ATTEMPTS": "2",
        "EXPLANATION_MAX_CONCURRENCY": "3",
        "EXPLANATION_CACHE_ENABLED": "true",
        "EXPLANATION_CACHE_PATH": "backend/data/output/explanation_cache.jsonl",
        "MODEL_INPUT_COST_PER_1M_USD": "",
        "MODEL_CACHED_INPUT_COST_PER_1M_USD": "",
        "MODEL_OUTPUT_COST_PER_1M_USD": "",
        "MODEL_PRICING_SNAPSHOT_DATE": "",
        "OPENAI_API_KEY": "",
    }
    for name, value in safe_environment.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
