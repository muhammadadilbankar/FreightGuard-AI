"""Immutable contracts for deterministic operational investigation leads."""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class RootCauseAvailability(str, Enum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class SupportLevel(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    LIMITED = "limited"
    TRANSITION_ONLY = "transition_only"
    UNAVAILABLE = "unavailable"


class EffectDirection(str, Enum):
    INCREASES_GAP = "increases_gap"
    OFFSETS_GAP = "offsets_gap"
    NEUTRAL = "neutral"


class OperationalMetric(str, Enum):
    SHIPMENT_COUNT = "shipment_count"
    AVERAGE_LOAD_TONNES = "average_load_tonnes"
    WEIGHTED_AVERAGE_DISTANCE_KM = "weighted_average_distance_km"
    TOTAL_QUANTITY_TONNES = "total_quantity_tonnes"
    TOTAL_TONNE_KM = "total_tonne_km"
    FREIGHT_COST_PER_SHIPMENT = "freight_cost_per_shipment"
    SHIPMENTS_PER_100_TONNES = "shipments_per_100_tonnes"


class RootCauseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def finite_floats(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Root-cause values must be finite.")
        return value


class OperationalLead(RootCauseModel):
    category: str
    effect: float
    support_level: SupportLevel
    narrative: str


class CategoryContribution(RootCauseModel):
    category: str
    current_shipment_count: int
    reference_shipment_count: int
    reference_weeks_present: int
    current_tonne_km_share: float | None
    reference_mean_tonne_km_share: float | None
    current_cost_per_tonne_km: float | None
    reference_mean_cost_per_tonne_km: float | None
    mix_effect: float
    rate_effect: float
    entry_effect: float
    exit_effect: float
    net_contribution: float
    absolute_effect_share_pct: float | None
    direction: EffectDirection
    support_level: SupportLevel
    caveats: tuple[str, ...] = ()

    @model_validator(mode="after")
    def effects_reconcile(self) -> Self:
        calculated = (
            self.mix_effect + self.rate_effect + self.entry_effect + self.exit_effect
        )
        if not math.isclose(calculated, self.net_contribution, abs_tol=1e-12):
            raise ValueError("Category effects do not reconcile to net contribution.")
        return self


class DecompositionLens(RootCauseModel):
    lens: Literal["transporter", "material"]
    target_gap: float
    reconstructed_gap: float
    reconstruction_error: float
    contributions: tuple[CategoryContribution, ...]
    leads: tuple[OperationalLead, ...] = ()
    offsets: tuple[OperationalLead, ...] = ()

    @model_validator(mode="after")
    def lens_reconciles(self) -> Self:
        if len({item.category for item in self.contributions}) != len(
            self.contributions
        ):
            raise ValueError("Contribution categories must be unique.")
        if not math.isclose(
            sum(item.net_contribution for item in self.contributions),
            self.reconstructed_gap,
            abs_tol=1e-12,
        ):
            raise ValueError("Lens contributions do not reconcile.")
        if not math.isclose(
            self.reconstructed_gap - self.target_gap,
            self.reconstruction_error,
            abs_tol=1e-12,
        ):
            raise ValueError("Lens reconstruction error is inconsistent.")
        return self


class MetricComparison(RootCauseModel):
    metric: OperationalMetric
    unit: str
    current_value: float
    reference_mean: float
    absolute_change: float
    percentage_change: float | None
    highlighted: bool
    interpretation: str


class RootCauseAnalysis(RootCauseModel):
    schema_version: Literal["1.0"] = "1.0"
    candidate_key: str
    route: str
    route_type: str
    week_of: date
    canonical_verdict: Literal["unexplained"] = "unexplained"
    availability: Literal[RootCauseAvailability.AVAILABLE] = (
        RootCauseAvailability.AVAILABLE
    )
    reference_weeks: tuple[date, ...]
    reference_week_count: int
    support_level: SupportLevel
    current_cost_per_tonne_km: float
    own_history_baseline: float
    target_gap: float
    transporter: DecompositionLens
    material: DecompositionLens
    operational_metrics: tuple[MetricComparison, ...]
    caveats: tuple[str, ...]

    @model_validator(mode="after")
    def analysis_invariants(self) -> Self:
        if self.reference_week_count != len(self.reference_weeks):
            raise ValueError("Reference week count is inconsistent.")
        if tuple(sorted(self.reference_weeks)) != self.reference_weeks:
            raise ValueError("Reference weeks must be sorted.")
        if any(week >= self.week_of for week in self.reference_weeks):
            raise ValueError("Reference weeks must be strictly historical.")
        expected_gap = self.current_cost_per_tonne_km - self.own_history_baseline
        if not math.isclose(expected_gap, self.target_gap, abs_tol=1e-12):
            raise ValueError("Target gap must equal current rate minus own baseline.")
        return self
