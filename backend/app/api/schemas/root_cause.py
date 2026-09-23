"""Public wire contracts for deterministic operational leads."""

from datetime import date
from typing import Literal

from ...domain.root_cause import EffectDirection, OperationalMetric, SupportLevel
from .common import DataEnvelope, WireModel


class OperationalLeadData(WireModel):
    category: str
    effect: float
    support_level: SupportLevel
    narrative: str


class CategoryContributionData(WireModel):
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
    caveats: tuple[str, ...]


class DecompositionLensData(WireModel):
    lens: Literal["transporter", "material"]
    target_gap: float
    reconstructed_gap: float
    reconstruction_error: float
    contributions: tuple[CategoryContributionData, ...]
    leads: tuple[OperationalLeadData, ...]
    offsets: tuple[OperationalLeadData, ...]


class MetricComparisonData(WireModel):
    metric: OperationalMetric
    unit: str
    current_value: float
    reference_mean: float
    absolute_change: float
    percentage_change: float | None
    highlighted: bool
    interpretation: str


class RootCauseData(WireModel):
    schema_version: Literal["1.0"]
    candidate_key: str
    route: str
    route_type: str
    week_of: date
    canonical_verdict: Literal["unexplained"]
    availability: Literal["available"]
    reference_weeks: tuple[date, ...]
    reference_week_count: int
    support_level: SupportLevel
    current_cost_per_tonne_km: float
    own_history_baseline: float
    target_gap: float
    transporter: DecompositionLensData
    material: DecompositionLensData
    operational_metrics: tuple[MetricComparisonData, ...]
    caveats: tuple[str, ...]


RootCauseResponse = DataEnvelope[RootCauseData]
