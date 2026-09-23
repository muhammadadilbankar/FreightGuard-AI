"""Immutable application snapshot and operational state models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ..domain.evaluation import ArtifactFingerprint, EvaluationReport, FileFingerprint
from ..domain.evidence import EvidenceVerdict


class RunState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    note_id: str
    evidence_level: str
    role: str
    rejection_codes: tuple[str, ...]
    original_text: str
    scope_type: str
    applies_to_routes: tuple[str, ...]
    effective_from: date
    effective_to: date | None
    event_type: str
    impact_direction: str
    affects_transport_cost: bool | None
    magnitude_text: str | None
    gate_results: tuple["EvidenceGateResult", ...]


@dataclass(frozen=True, slots=True)
class EvidenceGateResult:
    gate: str
    status: str
    reason_code: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class AnomalyView:
    candidate_key: str
    route: str
    route_type: str
    week_of: date
    cost_per_tonne_km: float
    own_history_baseline: float | None
    peer_baseline: float | None
    vs_own_history_pct: float
    vs_similar_routes_pct: float | None
    history_weeks_used: int
    peer_routes_used: int
    own_threshold_breached: bool
    peer_threshold_breached: bool
    trigger: str
    verdict: EvidenceVerdict
    flagged: str
    matched_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    decision_code: str
    reason: str
    evidence: tuple[EvidenceSummary, ...]
    explanation_source: str
    fallback_used: bool


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    week_of: date
    route_type: str
    cost_per_tonne_km: float
    own_history_baseline: float | None
    peer_baseline: float | None
    vs_own_history_pct: float | None
    vs_similar_routes_pct: float | None
    history_weeks_used: int
    peer_routes_used: int
    candidate: bool
    verdict: EvidenceVerdict | None


@dataclass(frozen=True, slots=True)
class AnalysisSummary:
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


@dataclass(frozen=True, slots=True)
class RunMetricsView:
    stage_durations_ms: Mapping[str, int]
    total_duration_ms: int
    row_counts: Mapping[str, int]
    retrieval_hit_count: int
    explanation_request_count: int
    hosted_model_call_count: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    cache_hits: int
    cache_misses: int
    fallback_count: int


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    snapshot_id: str
    created_at: datetime
    configuration_fingerprint: str
    input_fingerprints: tuple[FileFingerprint, ...]
    artifact_fingerprints: tuple[ArtifactFingerprint, ...]
    summary: AnalysisSummary
    anomalies: tuple[AnomalyView, ...]
    route_timelines: Mapping[str, tuple[TimelinePoint, ...]]
    evaluation: EvaluationReport | None
    evaluation_report_sha256: str | None
    run_metrics: RunMetricsView
    export_csv_path: Path
    export_csv_sha256: str

    @staticmethod
    def freeze_timelines(
        value: Mapping[str, tuple[TimelinePoint, ...]],
    ) -> Mapping[str, tuple[TimelinePoint, ...]]:
        return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True, slots=True)
class RunStatus:
    state: RunState = RunState.IDLE
    attempt_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latest_snapshot_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    previous_snapshot_available: bool = False


@dataclass(frozen=True, slots=True)
class RunAnalysisCommand:
    explanation_mode: str


@dataclass(frozen=True, slots=True)
class PublishedRunResult:
    attempt_id: str
    snapshot: AnalysisSnapshot
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    replaced_previous_snapshot: bool
