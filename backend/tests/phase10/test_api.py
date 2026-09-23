from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import ServiceOverrides, create_app
from backend.app.state.run_coordinator import RunCoordinator
from backend.app.state.snapshot_store import SnapshotStore


def _client(snapshot=None) -> TestClient:
    store = SnapshotStore(snapshot)
    return TestClient(
        create_app(
            Settings(_env_file=None),
            ServiceOverrides(
                snapshot_store=store, run_coordinator=RunCoordinator()
            ),
        ),
        raise_server_exceptions=False,
    )


def test_not_ready_and_validation_errors_use_safe_envelope() -> None:
    with _client() as client:
        not_ready = client.get(
            "/api/analysis/summary", headers={"X-Request-ID": "req-1"}
        )
        invalid = client.get("/api/anomalies?limit=0")
    assert not_ready.status_code == 503
    assert not_ready.json()["error"]["code"] == "analysis_not_ready"
    assert not_ready.headers["X-Request-ID"] == "req-1"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"


def test_snapshot_endpoints_pagination_timeline_export_and_etag(
    snapshot_factory,
) -> None:
    snapshot = snapshot_factory()
    with _client(snapshot) as client:
        health = client.get("/health")
        listing = client.get("/api/anomalies?limit=1")
        detail = client.get("/api/anomalies/R1/2024-01-08")
        timeline = client.get("/api/routes/R1/timeline")
        summary = client.get("/api/analysis/summary")
        metrics = client.get("/api/run-metrics")
        export = client.get("/api/analysis/export.csv")
        unchanged = client.get(
            "/api/analysis/export.csv",
            headers={"If-None-Match": export.headers["ETag"]},
        )
    assert health.json()["ready"] is True
    assert listing.json()["meta"]["pagination"] == {
        "total": 1,
        "limit": 1,
        "offset": 0,
        "has_more": False,
    }
    assert detail.json()["data"]["candidate_key"] == "R1|2024-01-08"
    assert detail.json()["data"]["history_weeks_used"] == 8
    assert detail.json()["data"]["peer_routes_used"] == 2
    assert detail.json()["data"]["decision_code"] == "justified"
    evidence = detail.json()["data"]["evidence"][0]
    assert evidence["original_text"] == "Fuel rates increased for this route."
    assert evidence["gate_results"][0] == {
        "gate": "route",
        "status": "pass",
        "reason_code": None,
        "reason": "The deterministic Evidence Gate passed this check.",
    }
    assert timeline.json()["data"]["points"][0]["candidate"] is True
    assert summary.json()["data"]["candidate_count"] == 1
    assert metrics.json()["data"]["latest_attempt"]["state"] == "idle"
    assert export.content == snapshot.export_csv_path.read_bytes()
    assert unchanged.status_code == 304


def test_monday_rules_exact_routes_and_cors(snapshot_factory) -> None:
    with _client(snapshot_factory()) as client:
        bad_week = client.get("/api/anomalies/R1/2024-01-09")
        wrong_case = client.get("/api/routes/r1/timeline")
        allowed = client.options(
            "/api/anomalies",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert bad_week.status_code == 422
    assert wrong_case.status_code == 404
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_contains_required_unique_operations_and_error_schema() -> None:
    with _client() as client:
        schema = client.get("/openapi.json").json()
    required = {
        "/health",
        "/api/analysis/run",
        "/api/analysis/summary",
        "/api/anomalies",
        "/api/anomalies/{route}/{week_of}",
        "/api/routes/{route}/timeline",
        "/api/evaluation/report",
        "/api/run-metrics",
        "/api/analysis/export.csv",
    }
    assert required <= set(schema["paths"])
    operations = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operations) == len(set(operations))
    assert "ErrorResponse" in schema["components"]["schemas"]
