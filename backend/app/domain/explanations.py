"""Immutable contracts for grounded explanation generation."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .context_notes import (
    CostImpactStatus,
    EventType,
    ImpactDirection,
    ScopeType,
)
from .evidence import EvidenceVerdict


class GenerationMode(str, Enum):
    TEMPLATE = "template"
    LIVE = "live"
    REPLAY = "replay"


class ExplanationSource(str, Enum):
    MODEL = "model"
    CACHE = "cache"
    FALLBACK = "fallback"
    TEMPLATE = "template"


class ValidationStatus(str, Enum):
    ACCEPTED = "accepted"
    FALLBACK = "fallback"
    NOT_APPLICABLE = "not_applicable"


class ExplanationFailureCode(str, Enum):
    PROVIDER_DISABLED = "provider_disabled"
    CREDENTIALS_MISSING = "credentials_missing"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_REFUSAL = "provider_refusal"
    PROVIDER_PROTOCOL_ERROR = "provider_protocol_error"
    STRUCTURED_OUTPUT_MISSING = "structured_output_missing"
    SCHEMA_VALIDATION_FAILED = "schema_validation_failed"
    IDENTITY_MISMATCH = "identity_mismatch"
    VERDICT_MISMATCH = "verdict_mismatch"
    UNAUTHORIZED_NOTE_ID = "unauthorized_note_id"
    REQUIRED_NOTE_ID_MISSING = "required_note_id_missing"
    INVALID_CITATION_SET = "invalid_citation_set"
    UNSUPPORTED_NUMERIC_CLAIM = "unsupported_numeric_claim"
    VERDICT_LANGUAGE_CONFLICT = "verdict_language_conflict"
    REASON_EMPTY = "reason_empty"
    REASON_LENGTH_VIOLATION = "reason_length_violation"
    REASON_FORMAT_VIOLATION = "reason_format_violation"
    INTERNAL_LANGUAGE_LEAKAGE = "internal_language_leakage"
    CACHE_ENTRY_INVALID = "cache_entry_invalid"


class ExplanationEvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note_id: str
    role: Literal["selected", "supporting"]
    scope_type: ScopeType
    effective_from: date
    effective_to: date | None
    event_type: EventType
    impact_direction: ImpactDirection
    cost_impact_status: CostImpactStatus
    magnitude_text: str | None
    original_text: str


class GroundedExplanationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    prompt_version: str
    route: str
    route_type: str
    week_of: date
    week_end: date
    cost_per_tonne_km_display: str
    vs_own_history_display: str
    vs_similar_routes_display: str | None
    verdict: EvidenceVerdict
    flagged: Literal["Yes", "No (justified)"]
    selected_note_id: str | None
    allowed_note_ids: tuple[str, ...]
    evidence: tuple[ExplanationEvidenceItem, ...]


class GeneratedExplanation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    week_of: date
    verdict: EvidenceVerdict
    cited_note_ids: tuple[str, ...]
    reason: str


class ExplanationPrompt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_version: str
    instructions: str
    canonical_payload: str


class ProviderIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str
    revision: str | None = None


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    structured_output: bool
    configurable_temperature: bool
    usage_reporting: bool


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None
    total_tokens: int = 0

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        values = (self.input_tokens, self.cached_input_tokens, self.output_tokens)
        if any(value < 0 for value in values):
            raise ValueError("token counts must be non-negative")
        if self.reasoning_tokens is not None and self.reasoning_tokens < 0:
            raise ValueError("reasoning tokens must be non-negative")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached input tokens cannot exceed input tokens")
        minimum_total = self.input_tokens + self.output_tokens
        if self.total_tokens < minimum_total:
            raise ValueError("total tokens cannot be below input plus output tokens")
        return self


class ProviderGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    parsed: GeneratedExplanation | None
    refusal: str | None = None
    usage: TokenUsage = TokenUsage()
    provider_request_id: str | None = None
    latency_ms: int = 0

    @field_validator("latency_ms")
    @classmethod
    def latency_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("latency must be non-negative")
        return value


class ExplanationValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted: bool
    reason: str | None
    cited_note_ids: tuple[str, ...]
    failure_codes: tuple[ExplanationFailureCode, ...]

    @field_validator("failure_codes")
    @classmethod
    def codes_are_sorted(
        cls, value: tuple[ExplanationFailureCode, ...]
    ) -> tuple[ExplanationFailureCode, ...]:
        expected = tuple(sorted(set(value), key=lambda item: item.value))
        if value != expected:
            raise ValueError("failure codes must be unique and sorted")
        return value


class FinalExplanationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route: str
    week_of: date
    verdict: EvidenceVerdict
    selected_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    allowed_note_ids: tuple[str, ...]
    reason: str
    cited_note_ids: tuple[str, ...]
    explanation_source: ExplanationSource
    provider: str | None
    model: str | None
    prompt_version: str
    cache_key: str
    cache_hit: bool
    provider_attempts: int
    validation_status: ValidationStatus
    failure_codes: tuple[ExplanationFailureCode, ...]
    usage: TokenUsage
    original_generation_usage: TokenUsage | None = None
    estimated_cost_usd: Decimal | None
    pricing_snapshot_date: date | None
    provider_request_id: str | None = None
    latency_ms: int = 0


class ExplanationCacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    cache_key: str
    provider_identity: ProviderIdentity
    prompt_version: str
    request_sha256: str
    schema_fingerprint: str
    generated: GeneratedExplanation
    usage: TokenUsage


class ExplanationSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: GenerationMode
    prompt_version: str
    max_attempts: int = 2
    max_concurrency: int = 3
    cache_enabled: bool = True
    input_cost_per_1m_usd: Decimal | None = None
    cached_input_cost_per_1m_usd: Decimal | None = None
    output_cost_per_1m_usd: Decimal | None = None
    pricing_snapshot_date: date | None = None

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        if not 1 <= self.max_attempts <= 5 or not 1 <= self.max_concurrency <= 16:
            raise ValueError("generation bounds are invalid")
        rates = (
            self.input_cost_per_1m_usd,
            self.cached_input_cost_per_1m_usd,
            self.output_cost_per_1m_usd,
        )
        if any(rate is not None and (not rate.is_finite() or rate < 0) for rate in rates):
            raise ValueError("pricing rates must be finite and non-negative")
        if any(rate is not None for rate in rates) and self.pricing_snapshot_date is None:
            raise ValueError("pricing rates require a snapshot date")
        return self


class ExplanationAuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    route: str
    week_of: date
    verdict: EvidenceVerdict
    selected_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    allowed_note_ids: tuple[str, ...]
    explanation_source: ExplanationSource
    provider: str | None
    model: str | None
    prompt_version: str
    cache_key: str
    cache_hit: bool
    provider_attempts: int
    validation_status: ValidationStatus
    failure_codes: tuple[ExplanationFailureCode, ...]
    cited_note_ids: tuple[str, ...]
    usage: TokenUsage
    estimated_cost_usd: Decimal | None
    pricing_snapshot_date: date | None
    provider_request_id: str | None
    latency_ms: int
    reason_sha256: str


EXPLANATION_AUDIT_FIELDS = tuple(ExplanationAuditRecord.model_fields)
