"""Health, run, and analysis summary wire contracts."""

from datetime import date, datetime
from typing import Literal

from .common import DataEnvelope, WireModel
from ...state.models import RunState


class HealthResponse(WireModel):
    status: Literal["ok"] = "ok"
    ready: bool
    service: str
    version: str
    run_state: RunState
    has_snapshot: bool
    snapshot_id: str | None = None


class RunAnalysisRequest(WireModel):
    explanation_mode: Literal["template", "replay", "live"] = "template"


class RunAnalysisData(WireModel):
    attempt_id: str
    snapshot_id: str
    run_state: Literal["succeeded"] = "succeeded"
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    shipment_count: int
    weekly_record_count: int
    candidate_count: int
    justified_count: int
    partially_explained_count: int
    unexplained_count: int
    evaluation_status: str
    final_csv_sha256: str
    replaced_previous_snapshot: bool


class AnalysisSummaryData(WireModel):
    shipment_count: int
    route_count: int
    route_type_count: int
    weekly_record_count: int
    candidate_count: int
    justified_count: int
    partially_explained_count: int
    unexplained_count: int
    analysis_from: date
    analysis_to: date
    anomaly_threshold_percent: float
    explanation_mode: str
    evaluation_status: str
    final_csv_sha256: str
    operational_root_causes_available: int
    run_state: RunState


RunAnalysisResponse = DataEnvelope[RunAnalysisData]
AnalysisSummaryResponse = DataEnvelope[AnalysisSummaryData]
