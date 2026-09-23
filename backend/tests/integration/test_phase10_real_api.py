"""Real template-mode API publication against the supplied challenge data."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_real_api_run_publishes_phase9_gated_snapshot() -> None:
    settings = Settings(_env_file=None)
    report = settings.evaluation_output_root / "evaluation_report.json"
    if not report.exists():
        pytest.skip("Run backend.scripts.evaluate_pipeline before this integration test.")
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        run = client.post(
            "/api/analysis/run", json={"explanation_mode": "template"}
        )
        assert run.status_code == 200, run.text
        payload = run.json()["data"]
        assert payload["shipment_count"] == 2940
        assert payload["weekly_record_count"] == 728
        assert payload["candidate_count"] == 19
        assert (
            payload["justified_count"],
            payload["partially_explained_count"],
            payload["unexplained_count"],
        ) == (3, 12, 4)
        summary = client.get("/api/analysis/summary")
        anomalies = client.get("/api/anomalies?limit=20")
        route = anomalies.json()["data"]["items"][0]["route"]
        timeline = client.get(f"/api/routes/{route}/timeline")
        evaluation = client.get("/api/evaluation/report?include_checks=false")
        metrics = client.get("/api/run-metrics")
        export = client.get("/api/analysis/export.csv")
        assert summary.status_code == 200
        assert summary.json()["meta"]["snapshot_id"] == payload["snapshot_id"]
        assert anomalies.json()["meta"]["pagination"]["total"] == 19
        assert len(timeline.json()["data"]["points"]) == 104
        assert evaluation.json()["data"]["report"]["overall_status"] == "pass"
        assert evaluation.json()["data"]["report"]["checks"] == []
        assert metrics.json()["data"]["hosted_model_call_count"] == 0
        assert export.status_code == 200
        assert export.content == Path(
            client.app.state.snapshot_store.require().export_csv_path
        ).read_bytes()
