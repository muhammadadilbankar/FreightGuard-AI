"""Anomaly and timeline wire contracts."""

from datetime import date
from typing import Literal

from ...domain.evidence import EvidenceVerdict
from .common import DataEnvelope, WireModel


class EvidenceGateResultData(WireModel):
    gate: Literal["route", "date", "direction", "cost_impact", "scope"]
    status: Literal["pass", "fail", "not_applicable"]
    reason_code: str | None
    reason: str


class EvidenceSummaryData(WireModel):
    note_id: str
    evidence_level: str
    role: Literal["primary", "supporting", "rejected"]
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
    gate_results: tuple[EvidenceGateResultData, ...]


class AnomalyData(WireModel):
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
    trigger: Literal["own_history", "peer", "both"]
    verdict: EvidenceVerdict
    flagged: str
    matched_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    decision_code: str
    reason: str
    evidence: tuple[EvidenceSummaryData, ...]
    explanation_source: str
    fallback_used: bool
    operational_root_cause_available: bool


class AnomalyListData(WireModel):
    items: tuple[AnomalyData, ...]


class TimelinePointData(WireModel):
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


class RouteTimelineData(WireModel):
    route: str
    points: tuple[TimelinePointData, ...]


AnomalyListResponse = DataEnvelope[AnomalyListData]
AnomalyDetailResponse = DataEnvelope[AnomalyData]
RouteTimelineResponse = DataEnvelope[RouteTimelineData]
