"""Immutable typed contracts for compiled context-note claims."""

from datetime import date
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ScopeType(str, Enum):
    GLOBAL = "global"
    ROUTE = "route"
    UNKNOWN = "unknown"


class ScopeStatus(str, Enum):
    IN_DATASET = "in_dataset"
    OUTSIDE_DATASET = "outside_dataset"
    PARTIALLY_IN_DATASET = "partially_in_dataset"
    UNRESOLVED = "unresolved"


class TemporalBasis(str, Enum):
    EXPLICIT_RANGE = "explicit_range"
    CALENDAR_WEEK = "calendar_week"
    APPROXIMATE_WEEK = "approximate_week"
    CALENDAR_QUARTER = "calendar_quarter"
    OPEN_ENDED_START = "open_ended_start"
    STATE_AFTER_COMPLETION = "state_after_completion"
    SOURCE_DATE_FALLBACK = "source_date_fallback"
    UNRESOLVED = "unresolved"


class ImpactDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NO_CHANGE = "no_change"
    UNKNOWN = "unknown"


class CostImpactStatus(str, Enum):
    EXPLICIT_INCREASE = "explicit_increase"
    EXPLICIT_DECREASE = "explicit_decrease"
    EXPLICIT_NO_MATERIAL_IMPACT = "explicit_no_material_impact"
    EXPLICIT_NO_RATE_CHANGE = "explicit_no_rate_change"
    NORMAL_OR_STABLE_OPERATIONS = "normal_or_stable_operations"
    NOT_STATED = "not_stated"
    UNKNOWN = "unknown"


class EventType(str, Enum):
    WEATHER_DISRUPTION = "weather_disruption"
    FESTIVAL_DEMAND = "festival_demand"
    FUEL_PRICE_CHANGE = "fuel_price_change"
    TOLL_OR_INFRASTRUCTURE = "toll_or_infrastructure"
    ROAD_MAINTENANCE = "road_maintenance"
    CAPACITY_OR_DEMAND_CONDITION = "capacity_or_demand_condition"
    ROAD_IMPROVEMENT = "road_improvement"
    NORMAL_OPERATIONS = "normal_operations"
    RECOVERY_OR_NORMALIZATION = "recovery_or_normalization"
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    OTHER = "other"
    UNKNOWN = "unknown"


class ContextNoteInput(BaseModel):
    """Canonical Phase 2 note represented at the compiler boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    note_id: str
    date: date
    applies_to: str
    note: str


class RouteScope(BaseModel):
    """Compiled route applicability plus stable warnings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_type: ScopeType
    applies_to_routes: tuple[str, ...]
    scope_status: ScopeStatus
    warnings: tuple[str, ...] = ()


class EffectiveInterval(BaseModel):
    """Inclusive effective interval and the deterministic rule that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_from: date
    effective_to: date | None
    temporal_basis: TemporalBasis
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        if (
            self.temporal_basis == TemporalBasis.UNRESOLVED
            and "temporal_phrase_ambiguous" not in self.warnings
        ):
            raise ValueError("unresolved temporal basis requires a warning")
        return self


class ImpactClaim(BaseModel):
    """Compiled event and transport-cost meaning plus stable warnings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: EventType
    impact_direction: ImpactDirection
    cost_impact_status: CostImpactStatus
    affects_transport_cost: bool | None
    negates_cost_increase: bool
    magnitude_text: str | None
    warnings: tuple[str, ...] = ()


class CompiledContextNote(BaseModel):
    """Versioned, immutable, traceable structured context-note claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    note_id: str
    source_date: date
    source_applies_to: str
    original_text: str
    scope_type: ScopeType
    applies_to_routes: tuple[str, ...]
    scope_status: ScopeStatus
    effective_from: date
    effective_to: date | None
    temporal_basis: TemporalBasis
    event_type: EventType
    impact_direction: ImpactDirection
    cost_impact_status: CostImpactStatus
    affects_transport_cost: bool | None
    negates_cost_increase: bool
    magnitude_text: str | None
    compilation_warnings: tuple[str, ...]

    @field_validator("compilation_warnings")
    @classmethod
    def warnings_are_unique_and_sorted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("compilation_warnings must be unique and sorted")
        return value

    @model_validator(mode="after")
    def validate_cross_field_contract(self) -> Self:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        routes = self.applies_to_routes
        if routes != tuple(sorted(set(routes))):
            raise ValueError("applies_to_routes must be unique and sorted")
        if self.scope_type == ScopeType.GLOBAL and routes:
            raise ValueError("global scope cannot contain explicit routes")
        if self.scope_type == ScopeType.ROUTE and not routes:
            raise ValueError("route scope requires at least one route")
        if (
            self.temporal_basis == TemporalBasis.UNRESOLVED
            and "temporal_phrase_ambiguous" not in self.compilation_warnings
        ):
            raise ValueError("unresolved temporal basis requires a warning")

        status = self.cost_impact_status
        if status == CostImpactStatus.EXPLICIT_INCREASE:
            self._require_impact(ImpactDirection.INCREASE, True, False)
        elif status == CostImpactStatus.EXPLICIT_DECREASE:
            self._require_impact(ImpactDirection.DECREASE, True, False)
        elif status in {
            CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT,
            CostImpactStatus.EXPLICIT_NO_RATE_CHANGE,
            CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS,
        }:
            self._require_impact(ImpactDirection.NO_CHANGE, False, True)
        elif status in {CostImpactStatus.NOT_STATED, CostImpactStatus.UNKNOWN}:
            self._require_impact(ImpactDirection.UNKNOWN, None, False)
        return self

    def _require_impact(
        self,
        direction: ImpactDirection,
        affects_cost: bool | None,
        negates_increase: bool,
    ) -> None:
        if (
            self.impact_direction != direction
            or self.affects_transport_cost is not affects_cost
            or self.negates_cost_increase is not negates_increase
        ):
            raise ValueError(
                f"{self.cost_impact_status.value} has inconsistent impact fields"
            )


COMPILED_NOTE_FIELDS = tuple(CompiledContextNote.model_fields)
