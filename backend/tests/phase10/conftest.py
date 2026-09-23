from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.domain.evidence import EvidenceVerdict
from backend.app.state.models import (
    AnalysisSnapshot,
    AnalysisSummary,
    AnomalyView,
    EvidenceSummary,
    RunMetricsView,
    TimelinePoint,
)


@pytest.fixture
def snapshot_factory(tmp_path: Path):
    def make(snapshot_id: str = "snapshot-a") -> AnalysisSnapshot:
        export = tmp_path / f"{snapshot_id}.csv"
        content = b"route,week_of,flagged\nR1,2024-01-08,Yes\n"
        export.write_bytes(content)
        anomaly = AnomalyView(
            candidate_key="R1|2024-01-08",
            route="R1",
            route_type="Short",
            week_of=date(2024, 1, 8),
            cost_per_tonne_km=2.5,
            own_history_baseline=2.0,
            peer_baseline=2.1,
            vs_own_history_pct=25.0,
            vs_similar_routes_pct=19.05,
            own_threshold_breached=True,
            peer_threshold_breached=False,
            trigger="own_history",
            verdict=EvidenceVerdict.JUSTIFIED,
            flagged="Yes – justified",
            matched_note_id="N1",
            supporting_note_ids=("N1",),
            reason="Supported by [N1].",
            evidence=(EvidenceSummary("N1", "direct", ()),),
            explanation_source="template",
            fallback_used=False,
        )
        point = TimelinePoint(
            week_of=anomaly.week_of,
            route_type=anomaly.route_type,
            cost_per_tonne_km=anomaly.cost_per_tonne_km,
            own_history_baseline=anomaly.own_history_baseline,
            peer_baseline=anomaly.peer_baseline,
            vs_own_history_pct=anomaly.vs_own_history_pct,
            vs_similar_routes_pct=anomaly.vs_similar_routes_pct,
            history_weeks_used=8,
            peer_routes_used=2,
            candidate=True,
            verdict=anomaly.verdict,
        )
        digest = hashlib.sha256(content).hexdigest()
        return AnalysisSnapshot(
            snapshot_id=snapshot_id,
            created_at=datetime.now(UTC),
            configuration_fingerprint="c" * 64,
            input_fingerprints=(),
            artifact_fingerprints=(),
            summary=AnalysisSummary(
                shipment_count=10,
                route_count=1,
                route_type_count=1,
                weekly_record_count=1,
                candidate_count=1,
                justified_count=1,
                partially_explained_count=0,
                unexplained_count=0,
                analysis_from=date(2024, 1, 8),
                analysis_to=date(2024, 1, 8),
                anomaly_threshold_percent=20.0,
                explanation_mode="template",
                evaluation_status="pass",
                final_csv_sha256=digest,
            ),
            anomalies=(anomaly,),
            route_timelines=AnalysisSnapshot.freeze_timelines({"R1": (point,)}),
            evaluation=None,
            evaluation_report_sha256=None,
            run_metrics=RunMetricsView(
                stage_durations_ms={"analytics": 1},
                total_duration_ms=1,
                row_counts={"candidates": 1},
                retrieval_hit_count=1,
                explanation_request_count=1,
                hosted_model_call_count=0,
                input_tokens=None,
                output_tokens=None,
                estimated_cost_usd=Decimal("0"),
                cache_hits=0,
                cache_misses=0,
                fallback_count=0,
            ),
            export_csv_path=export,
            export_csv_sha256=digest,
        )

    return make
