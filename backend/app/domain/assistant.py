"""Immutable contracts for the snapshot-grounded investigation assistant."""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .evidence import EvidenceVerdict


class AssistantModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AssistantMode(str, Enum):
    TEMPLATE = "template"
    REPLAY = "replay"
    LIVE = "live"


class AssistantIntent(str, Enum):
    EXPLAIN_ANOMALY = "explain_anomaly"
    LIST_ANOMALIES = "list_anomalies"
    RANK_ANOMALIES = "rank_anomalies"
    ROUTE_TREND = "route_trend"
    EVIDENCE_REVIEW = "evidence_review"
    REJECTED_EVIDENCE = "rejected_evidence"
    OPERATIONAL_LEADS = "operational_leads"
    ANALYSIS_SUMMARY = "analysis_summary"
    EVALUATION_STATUS = "evaluation_status"
    RUN_METRICS = "run_metrics"
    HELP = "help"
    UNSUPPORTED = "unsupported"


class AssistantTool(str, Enum):
    GET_SUMMARY = "get_summary"
    LIST_ANOMALIES = "list_anomalies"
    GET_ANOMALY_DETAIL = "get_anomaly_detail"
    GET_ROUTE_TIMELINE = "get_route_timeline"
    GET_EVIDENCE_REVIEW = "get_evidence_review"
    LIST_REJECTED_EVIDENCE = "list_rejected_evidence"
    GET_OPERATIONAL_LEADS = "get_operational_leads"
    GET_EVALUATION_STATUS = "get_evaluation_status"
    GET_RUN_METRICS = "get_run_metrics"


class AssistantStatus(str, Enum):
    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class AssistantSortField(str, Enum):
    WEEK_OF = "week_of"
    COST_PER_TONNE_KM = "cost_per_tonne_km"
    VS_OWN_HISTORY_PCT = "vs_own_history_pct"
    VS_SIMILAR_ROUTES_PCT = "vs_similar_routes_pct"


class AnswerTemplate(str, Enum):
    ANOMALY = "anomaly"
    ANOMALY_LIST = "anomaly_list"
    ROUTE_TREND = "route_trend"
    EVIDENCE = "evidence"
    REJECTED_EVIDENCE = "rejected_evidence"
    OPERATIONAL = "operational"
    SUMMARY = "summary"
    STATUS = "status"
    HELP = "help"
    LIMITATION = "limitation"


class CitationType(str, Enum):
    ANOMALY = "anomaly"
    ROUTE_WEEK = "route_week"
    CONTEXT_NOTE = "context_note"
    EVIDENCE_DECISION = "evidence_decision"
    ROOT_CAUSE = "root_cause"
    EVALUATION_CHECK = "evaluation_check"
    RUN_METRICS = "run_metrics"
    ANALYSIS_SUMMARY = "analysis_summary"


class FactType(str, Enum):
    ANOMALY = "anomaly"
    ROUTE_WEEK = "route_week"
    EVIDENCE = "evidence"
    ROOT_CAUSE = "root_cause"
    SUMMARY = "summary"
    EVALUATION = "evaluation"
    METRICS = "metrics"


class QueryFilters(AssistantModel):
    route: str | None = Field(default=None, max_length=200)
    route_type: str | None = Field(default=None, max_length=50)
    verdict: EvidenceVerdict | None = None
    trigger: Literal["own_history", "peer", "both"] | None = None
    week_from: date | None = None
    week_to: date | None = None
    min_own_deviation_pct: float | None = None
    min_peer_deviation_pct: float | None = None
    week_of: date | None = None
    note_id: str | None = Field(default=None, max_length=100)
    rejection_code: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_filters(self) -> Self:
        if self.week_from and self.week_to and self.week_from > self.week_to:
            raise ValueError("week_from must not follow week_to")
        for value in (self.min_own_deviation_pct, self.min_peer_deviation_pct):
            if value is not None and not math.isfinite(value):
                raise ValueError("filter numerics must be finite")
        return self


class QueryStep(AssistantModel):
    tool: AssistantTool
    filters: QueryFilters = QueryFilters()
    sort_by: AssistantSortField | None = None
    sort_order: SortDirection | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ClarificationOption(AssistantModel):
    option_id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=300)


class ClarificationRequest(AssistantModel):
    question: str = Field(min_length=1, max_length=500)
    options: tuple[ClarificationOption, ...] = Field(default=(), max_length=5)


class AssistantConversationContext(AssistantModel):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str = Field(min_length=1, max_length=100)
    last_intent: AssistantIntent | None = None
    route: str | None = Field(default=None, max_length=200)
    week_of: date | None = None
    week_from: date | None = None
    week_to: date | None = None
    candidate_keys: tuple[str, ...] = Field(default=(), max_length=10)
    note_id: str | None = Field(default=None, max_length=100)


class AssistantQueryPlan(AssistantModel):
    schema_version: Literal["1.0"] = "1.0"
    planner_version: str = Field(min_length=1, max_length=100)
    intent: AssistantIntent
    steps: tuple[QueryStep, ...] = Field(default=(), max_length=3)
    answer_template: AnswerTemplate
    requires_clarification: bool = False
    clarification: ClarificationRequest | None = None
    unsupported_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def outcome_matches_steps(self) -> Self:
        if self.requires_clarification != (self.clarification is not None):
            raise ValueError("clarification flag and payload must agree")
        if (self.requires_clarification or self.intent == AssistantIntent.UNSUPPORTED) and self.steps:
            raise ValueError("clarification and unsupported plans cannot execute tools")
        return self


class AssistantRequest(AssistantModel):
    question: str = Field(min_length=1, max_length=800)
    mode: AssistantMode | None = None
    context: AssistantConversationContext | None = None

    @field_validator("question")
    @classmethod
    def question_is_safe_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("question must not be blank")
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise ValueError("question contains control characters")
        return normalized


class VerifiedFact(AssistantModel):
    fact_id: str
    fact_type: FactType
    canonical_value: Any
    display_text: str
    citation_ids: tuple[str, ...]


class ToolExecutionResult(AssistantModel):
    tool: AssistantTool
    records: tuple[Any, ...]
    total_count: int
    truncated: bool = False


class FactRegistry(AssistantModel):
    facts: tuple[VerifiedFact, ...] = ()

    @field_validator("facts")
    @classmethod
    def unique_ids(cls, value: tuple[VerifiedFact, ...]) -> tuple[VerifiedFact, ...]:
        if len({item.fact_id for item in value}) != len(value):
            raise ValueError("fact IDs must be unique")
        return value


class Citation(AssistantModel):
    citation_id: str
    citation_type: CitationType
    label: str
    route: str | None = None
    week_of: date | None = None
    candidate_key: str | None = None
    note_id: str | None = None
    check_id: str | None = None
    snapshot_id: str
    navigation_target: str | None = None


class GroundedClaim(AssistantModel):
    claim_id: str
    text: str
    citation_ids: tuple[str, ...]


class TableColumn(AssistantModel):
    key: str
    label: str


class ResultTable(AssistantModel):
    caption: str
    columns: tuple[TableColumn, ...]
    rows: tuple[tuple[Any, ...], ...]
    citation_column_index: int | None = None

    @model_validator(mode="after")
    def rectangular(self) -> Self:
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("table rows must match column count")
        return self


class NavigationAction(AssistantModel):
    label: str
    action: Literal[
        "open_anomaly",
        "open_route_timeline",
        "open_evidence",
        "open_root_cause",
        "apply_anomaly_filters",
        "open_evaluation",
    ]
    params: dict[str, str]


class AssistantUsage(AssistantModel):
    provider_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None


class AssistantResponseData(AssistantModel):
    status: AssistantStatus
    title: str
    claims: tuple[GroundedClaim, ...] = ()
    table: ResultTable | None = None
    clarification: ClarificationRequest | None = None
    limitations: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()
    actions: tuple[NavigationAction, ...] = ()
    context: AssistantConversationContext

    @model_validator(mode="after")
    def response_shape(self) -> Self:
        if self.status == AssistantStatus.ANSWERED and self.clarification is not None:
            raise ValueError("answered responses cannot contain clarification")
        if self.status == AssistantStatus.NEEDS_CLARIFICATION and self.clarification is None:
            raise ValueError("clarification response requires options or a question")
        citation_ids = {item.citation_id for item in self.citations}
        if any(not set(claim.citation_ids) <= citation_ids for claim in self.claims):
            raise ValueError("claim references an unknown citation")
        return self


class AssistantResponseMeta(AssistantModel):
    schema_version: Literal["1.0"] = "1.0"
    snapshot_id: str
    grounded: Literal[True] = True
    planner_mode: AssistantMode
    planner_source: Literal["deterministic", "cache", "provider", "policy"]
    planner_version: str
    cache_hit: bool = False
    latency_ms: int = Field(ge=0)
    tool_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    request_id: str
    usage: AssistantUsage = AssistantUsage()


class AssistantResponseEnvelope(AssistantModel):
    data: AssistantResponseData
    meta: AssistantResponseMeta
