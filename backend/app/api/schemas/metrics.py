"""Safe operational metrics wire contracts."""

from datetime import datetime
from decimal import Decimal

from ...domain.evaluation import ArtifactFingerprint, FileFingerprint
from ...state.models import RunState
from .common import DataEnvelope, WireModel


class LatestAttemptData(WireModel):
    state: RunState
    attempt_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    latest_snapshot_id: str | None
    failure_code: str | None
    failure_message: str | None
    previous_snapshot_available: bool


class RunMetricsData(WireModel):
    stage_durations_ms: dict[str, int]
    total_duration_ms: int
    row_counts: dict[str, int]
    retrieval_hit_count: int
    explanation_request_count: int
    hosted_model_call_count: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    cache_hits: int
    cache_misses: int
    fallback_count: int
    input_fingerprints: tuple[FileFingerprint, ...]
    configuration_fingerprint: str
    artifact_fingerprints: tuple[ArtifactFingerprint, ...]
    latest_attempt: LatestAttemptData


RunMetricsResponse = DataEnvelope[RunMetricsData]
