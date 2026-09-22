"""Immutable contracts for retrieval, evidence gating, and reviewed decisions."""

from datetime import date
from enum import Enum
import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .context_notes import CompiledContextNote


class GateCheck(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class EvidenceCoverage(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class EvidenceLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    REJECTED = "rejected"


class EvidenceVerdict(str, Enum):
    JUSTIFIED = "justified"
    PARTIALLY_EXPLAINED = "partially_explained"
    UNEXPLAINED = "unexplained"


class RejectionCode(str, Enum):
    SCOPE_OUTSIDE_DATASET = "scope_outside_dataset"
    SCOPE_UNRESOLVED = "scope_unresolved"
    ROUTE_MISMATCH = "route_mismatch"
    DATE_NO_OVERLAP = "date_no_overlap"
    COST_IMPACT_NOT_POSITIVE = "cost_impact_not_positive"
    IMPACT_DIRECTION_NOT_INCREASE = "impact_direction_not_increase"
    COST_INCREASE_NEGATED = "cost_increase_negated"
    GLOBAL_SCOPE_CANNOT_EXPLAIN_PEER_PREMIUM = (
        "global_scope_cannot_explain_peer_premium"
    )
    GLOBAL_MAGNITUDE_INSUFFICIENT = "global_magnitude_insufficient"
    COMPILED_CLAIM_INCONSISTENT = "compiled_claim_inconsistent"


class ReasonTemplateKey(str, Enum):
    JUSTIFIED = "justified"
    PARTIALLY_EXPLAINED = "partially_explained"
    UNEXPLAINED = "unexplained"


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    top_k: int
    rrf_k: int
    sparse_weight: float
    dense_weight: float

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        if self.top_k < 1 or self.rrf_k < 1:
            raise ValueError("top_k and rrf_k must be positive")
        weights = (self.sparse_weight, self.dense_weight)
        if any(not math.isfinite(value) or value < 0 for value in weights):
            raise ValueError("retrieval weights must be finite and non-negative")
        if not any(value > 0 for value in weights):
            raise ValueError("at least one retrieval weight must be positive")
        return self


class EvidencePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    global_magnitude_tolerance_percent: float = 2.0

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        value = self.global_magnitude_tolerance_percent
        if not math.isfinite(value) or value < 0:
            raise ValueError("global magnitude tolerance must be finite and non-negative")
        return self


class CandidateEvidenceQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    route_type: str
    week_of: date
    week_end: date
    cost_per_tonne_km: float
    vs_own_history_pct: float
    vs_similar_routes_pct: float | None
    own_threshold_breached: bool
    peer_threshold_breached: bool
    query_text: str

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if (self.week_end - self.week_of).days != 6:
            raise ValueError("candidate week must span exactly seven inclusive days")
        values = (self.cost_per_tonne_km, self.vs_own_history_pct)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("candidate numeric fields must be finite")
        if self.vs_similar_routes_pct is not None and not math.isfinite(
            self.vs_similar_routes_pct
        ):
            raise ValueError("peer deviation must be finite when available")
        return self


class RetrievalHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note_id: str
    sparse_rank: int | None = None
    sparse_score: float | None = None
    dense_rank: int | None = None
    dense_score: float | None = None
    fused_rank: int | None = None
    fused_score: float | None = None
    included_by_structured_recall: bool = False

    @field_validator("sparse_rank", "dense_rank", "fused_rank")
    @classmethod
    def ranks_are_one_based(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("retrieval ranks must be one-based")
        return value

    @field_validator("sparse_score", "dense_score", "fused_score")
    @classmethod
    def scores_are_finite_and_stable(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("retrieval scores must be finite")
        return None if value is None else round(float(value), 12)


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    week_of: date
    note_id: str
    route_check: GateCheck
    date_check: GateCheck
    scope_check: GateCheck
    direction_check: GateCheck
    cost_impact_check: GateCheck
    negation_check: GateCheck
    explanatory_scope: EvidenceCoverage
    overlap_days: int
    evidence_level: EvidenceLevel
    rejection_codes: tuple[RejectionCode, ...]
    retrieval: RetrievalHit
    exact_route_scope: bool
    has_numeric_magnitude: bool

    @field_validator("rejection_codes")
    @classmethod
    def codes_are_unique_and_sorted(
        cls, value: tuple[RejectionCode, ...]
    ) -> tuple[RejectionCode, ...]:
        if value != tuple(sorted(set(value), key=lambda item: item.value)):
            raise ValueError("rejection codes must be unique and sorted")
        return value


class EvidenceDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    week_of: date
    verdict: EvidenceVerdict
    selected_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    reason_template_key: ReasonTemplateKey
    assessed_note_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.supporting_note_ids != tuple(sorted(set(self.supporting_note_ids))):
            raise ValueError("supporting note IDs must be unique and sorted")
        if self.assessed_note_ids != tuple(sorted(set(self.assessed_note_ids))):
            raise ValueError("assessed note IDs must be unique and sorted")
        if self.verdict == EvidenceVerdict.JUSTIFIED:
            if self.selected_note_id is None:
                raise ValueError("justified decisions require a selected note")
        elif self.selected_note_id is not None:
            raise ValueError("non-justified decisions cannot select a note")
        return self


class ValidatedEvidencePacket(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: CandidateEvidenceQuery
    decision: EvidenceDecision
    selected_note: CompiledContextNote | None
    supporting_notes: tuple[CompiledContextNote, ...]
    allowed_note_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_allowlist(self) -> Self:
        expected = set(note.note_id for note in self.supporting_notes)
        if self.selected_note is not None:
            expected.add(self.selected_note.note_id)
        if self.allowed_note_ids != tuple(sorted(expected)):
            raise ValueError("allowed note IDs must equal accepted evidence notes")
        return self


class CandidateEvidenceAudit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    route: str
    week_of: date
    query_text: str
    verdict: EvidenceVerdict
    selected_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    assessments: tuple[EvidenceAssessment, ...]


class EvidenceReviewResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    queries: tuple[CandidateEvidenceQuery, ...]
    packets: tuple[ValidatedEvidencePacket, ...]
    audits: tuple[CandidateEvidenceAudit, ...]
    sparse_rankings: dict[tuple[str, date], tuple[RetrievalHit, ...]]
    dense_rankings: dict[tuple[str, date], tuple[RetrievalHit, ...]]
    fused_rankings: dict[tuple[str, date], tuple[RetrievalHit, ...]]


EVIDENCE_AUDIT_FIELDS = tuple(CandidateEvidenceAudit.model_fields)
