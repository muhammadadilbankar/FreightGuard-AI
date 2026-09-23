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
        "ready": False,
        "service": "FreightGuard AI API",
        "version": "0.10.0",
        "run_state": "idle",
        "has_snapshot": False,
        "snapshot_id": None,
    }


def test_health_metadata_comes_from_settings() -> None:
    settings = Settings(
        api_title="FreightGuard Test API",
        api_version="9.9.9",
        _env_file=None,
    )
    application = create_app(settings)

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "ready": False,
        "service": "FreightGuard Test API",
        "version": "9.9.9",
        "run_state": "idle",
        "has_snapshot": False,
        "snapshot_id": None,
    }
