"""Health endpoint and application smoke tests."""

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_default_health_response_matches_public_contract() -> None:
    application = create_app(Settings(_env_file=None))

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "FreightGuard AI API",
        "version": "0.1.0",
        "environment": "development",
    }


def test_health_metadata_comes_from_settings() -> None:
    settings = Settings(
        app_name="FreightGuard Test API",
        app_version="9.9.9",
        app_env="test",
        _env_file=None,
    )
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "FreightGuard Test API",
        "version": "9.9.9",
        "environment": "test",
    }
