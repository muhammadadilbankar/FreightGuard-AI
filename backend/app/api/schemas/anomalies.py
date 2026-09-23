"""Anomaly and timeline wire contracts."""

from datetime import date
from typing import Literal

from ...domain.evidence import EvidenceVerdict
from .common import DataEnvelope, WireModel


class EvidenceSummaryData(WireModel):
    note_id: str
    evidence_level: str
    rejection_codes: tuple[str, ...]


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
    own_threshold_breached: bool
    peer_threshold_breached: bool
    trigger: Literal["own_history", "peer", "both"]
    verdict: EvidenceVerdict
    flagged: str
    matched_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    reason: str
    evidence: tuple[EvidenceSummaryData, ...]
    explanation_source: str
    fallback_used: bool


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
