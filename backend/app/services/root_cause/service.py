"""Deterministic operational decomposition over validated shipment records."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import pandas as pd

from ...domain.evidence import EvidenceDecision, EvidenceVerdict
from ...domain.root_cause import (
    CategoryContribution,
    DecompositionLens,
    EffectDirection,
    MetricComparison,
    OperationalLead,
    OperationalMetric,
    RootCauseAnalysis,
    SupportLevel,
)
from ...state.errors import AnalysisRunFailedError
from .reference_window import resolve_reference_weeks


@dataclass(frozen=True, slots=True)
class RootCausePolicy:
    min_current_category_shipments: int = 2
    min_reference_category_shipments: int = 3
    min_lead_abs_effect: float = 0.01
    min_lead_abs_share_pct: float = 10.0
    max_leads_per_lens: int = 3
    metric_highlight_percent: float = 10.0
    reconstruction_tolerance: float = 1e-9


@dataclass(frozen=True, slots=True)
class _Category:
    shipments: int
    tonne_km: float
    freight: float
    share: float
    rate: float


def analyze_operational_root_causes(
    shipments: pd.DataFrame,
    weekly: pd.DataFrame,
    decisions: tuple[EvidenceDecision, ...],
    policy: RootCausePolicy,
) -> tuple[RootCauseAnalysis, ...]:
    """Analyze only canonically unexplained candidates without mutating inputs."""
    results = []
    for decision in sorted(decisions, key=lambda item: (item.week_of, item.route)):
        if decision.verdict != EvidenceVerdict.UNEXPLAINED:
            continue
        candidate_rows = weekly.loc[
            (weekly["route"] == decision.route)
            & (pd.to_datetime(weekly["week_of"]).dt.date == decision.week_of)
            & weekly["candidate_anomaly"]
        ]
        if len(candidate_rows) != 1:
            raise AnalysisRunFailedError(
                "Root-cause candidate does not reconcile with canonical analytics."
            )
        row = candidate_rows.iloc[0]
        results.append(
            _analyze_one(shipments, weekly, row, decision.week_of, policy)
        )
    return tuple(results)


def _analyze_one(
    shipments: pd.DataFrame,
    weekly: pd.DataFrame,
    candidate: pd.Series,
    week_of: date,
    policy: RootCausePolicy,
) -> RootCauseAnalysis:
    route = str(candidate["route"])
    route_type = str(candidate["route_type"])
    reference_weeks = resolve_reference_weeks(
        weekly, route=route, route_type=route_type, week_of=week_of
    )
    expected_count = int(candidate["history_weeks_used"])
    if not reference_weeks:
        raise AnalysisRunFailedError("Root cause has no reference history.")
    if len(reference_weeks) != expected_count:
        raise AnalysisRunFailedError(
            "Root-cause reference weeks disagree with Phase 4 history count."
        )

    route_shipments = shipments.loc[
        (shipments["route"] == route) & (shipments["route_type"] == route_type)
    ].copy(deep=True)
    route_shipments["week_date"] = pd.to_datetime(route_shipments["week_of"]).dt.date
    current = route_shipments.loc[route_shipments["week_date"] == week_of]
    historical = {
        week: route_shipments.loc[route_shipments["week_date"] == week]
        for week in reference_weeks
    }
    if current.empty or any(frame.empty for frame in historical.values()):
        raise AnalysisRunFailedError("Root-cause shipment selection is incomplete.")

    current_rate = _weekly_rate(current)
    canonical_rate = float(candidate["cost_per_tonne_km"])
    baseline = float(candidate["own_history_avg_cost_per_tonne_km"])
    reference_rates = tuple(_weekly_rate(frame) for frame in historical.values())
    if not math.isclose(current_rate, canonical_rate, abs_tol=policy.reconstruction_tolerance):
        raise AnalysisRunFailedError(
            "Root-cause current shipment aggregate disagrees with Phase 3."
        )
    if not math.isclose(
        sum(reference_rates) / len(reference_rates),
        baseline,
        abs_tol=policy.reconstruction_tolerance,
    ):
        raise AnalysisRunFailedError(
            "Root-cause reference window disagrees with Phase 4 baseline."
        )
    target_gap = current_rate - baseline
    transporter = _decompose(
        "transporter", current, historical, target_gap, policy
    )
    material = _decompose("material", current, historical, target_gap, policy)
    support = _result_support(len(reference_weeks))
    caveats = (
        "Operational leads are descriptive shipment patterns, not validated context evidence.",
        "Transporter and material lenses independently partition the same gap and must not be added together.",
    )
    return RootCauseAnalysis(
        candidate_key=f"{route}|{week_of.isoformat()}",
        route=route,
        route_type=route_type,
        week_of=week_of,
        reference_weeks=reference_weeks,
        reference_week_count=len(reference_weeks),
        support_level=support,
        current_cost_per_tonne_km=current_rate,
        own_history_baseline=baseline,
        target_gap=target_gap,
        transporter=transporter,
        material=material,
        operational_metrics=_metric_comparisons(
            current, tuple(historical.values()), policy
        ),
        caveats=caveats,
    )


def _weekly_rate(frame: pd.DataFrame) -> float:
    tonne_km = float(frame["tonne_km"].sum())
    freight = float(frame["freight_cost_inr"].sum())
    if tonne_km <= 0 or not math.isfinite(tonne_km + freight):
        raise AnalysisRunFailedError("Root-cause weekly totals must be finite and positive.")
    return freight / tonne_km


def _categories(frame: pd.DataFrame, column: str) -> dict[str, _Category]:
    total_tonne_km = float(frame["tonne_km"].sum())
    grouped = frame.groupby(column, sort=True, observed=True).agg(
        shipments=("shipment_id", "nunique"),
        tonne_km=("tonne_km", "sum"),
        freight=("freight_cost_inr", "sum"),
    )
    return {
        str(category): _Category(
            shipments=int(row.shipments),
            tonne_km=float(row.tonne_km),
            freight=float(row.freight),
            share=float(row.tonne_km) / total_tonne_km,
            rate=float(row.freight) / float(row.tonne_km),
        )
        for category, row in grouped.iterrows()
    }


def _decompose(
    lens: str,
    current: pd.DataFrame,
    historical: dict[date, pd.DataFrame],
    target_gap: float,
    policy: RootCausePolicy,
) -> DecompositionLens:
    current_categories = _categories(current, lens)
    history_categories = {
        week: _categories(frame, lens) for week, frame in historical.items()
    }
    categories = sorted(
        set(current_categories).union(
            *(set(values) for values in history_categories.values())
        )
    )
    accumulator: dict[str, dict[str, float]] = {
        category: defaultdict(float) for category in categories
    }
    reference_shipments = defaultdict(int)
    reference_weeks_present = defaultdict(int)
    reference_share = defaultdict(float)
    reference_rate_sum = defaultdict(float)
    for historical_values in history_categories.values():
        for category in categories:
            present = historical_values.get(category)
            if present is not None:
                reference_shipments[category] += present.shipments
                reference_weeks_present[category] += 1
                reference_share[category] += present.share
                reference_rate_sum[category] += present.rate
            current_value = current_categories.get(category)
            if current_value is not None and present is not None:
                accumulator[category]["mix"] += 0.5 * (
                    current_value.share - present.share
                ) * (current_value.rate + present.rate)
                accumulator[category]["rate"] += 0.5 * (
                    current_value.rate - present.rate
                ) * (current_value.share + present.share)
            elif current_value is not None:
                accumulator[category]["entry"] += (
                    current_value.share * current_value.rate
                )
            elif present is not None:
                accumulator[category]["exit"] -= present.share * present.rate

    comparison_count = len(history_categories)
    draft: list[CategoryContribution] = []
    for category in categories:
        current_value = current_categories.get(category)
        effects = {
            name: accumulator[category][name] / comparison_count
            for name in ("mix", "rate", "entry", "exit")
        }
        net = sum(effects.values())
        support, caveats = _category_support(
            current_value.shipments if current_value else 0,
            reference_shipments[category],
            reference_weeks_present[category],
            effects["entry"],
            effects["exit"],
            policy,
        )
        direction = (
            EffectDirection.INCREASES_GAP
            if net > policy.reconstruction_tolerance
            else EffectDirection.OFFSETS_GAP
            if net < -policy.reconstruction_tolerance
            else EffectDirection.NEUTRAL
        )
        draft.append(
            CategoryContribution(
                category=category,
                current_shipment_count=current_value.shipments if current_value else 0,
                reference_shipment_count=reference_shipments[category],
                reference_weeks_present=reference_weeks_present[category],
                current_tonne_km_share=current_value.share if current_value else None,
                reference_mean_tonne_km_share=(
                    reference_share[category] / comparison_count
                ),
                current_cost_per_tonne_km=current_value.rate if current_value else None,
                reference_mean_cost_per_tonne_km=(
                    reference_rate_sum[category] / reference_weeks_present[category]
                    if reference_weeks_present[category]
                    else None
                ),
                mix_effect=effects["mix"],
                rate_effect=effects["rate"],
                entry_effect=effects["entry"],
                exit_effect=effects["exit"],
                net_contribution=net,
                absolute_effect_share_pct=None,
                direction=direction,
                support_level=support,
                caveats=caveats,
            )
        )
    absolute_total = sum(abs(item.net_contribution) for item in draft)
    contributions = tuple(
        sorted(
            (
                item.model_copy(
                    update={
                        "absolute_effect_share_pct": (
                        abs(item.net_contribution) / absolute_total * 100
                        if absolute_total > 0
                        else None
                        )
                    }
                )
                for item in draft
            ),
            key=lambda item: (-item.net_contribution, item.category),
        )
    )
    reconstructed = sum(item.net_contribution for item in contributions)
    error = reconstructed - target_gap
    if abs(error) > policy.reconstruction_tolerance:
        raise AnalysisRunFailedError(
            f"{lens.title()} root-cause decomposition failed reconstruction."
        )
    leads = _select_leads(lens, contributions, policy, positive=True)
    offsets = _select_leads(lens, contributions, policy, positive=False)[:2]
    return DecompositionLens(
        lens=lens,
        target_gap=target_gap,
        reconstructed_gap=reconstructed,
        reconstruction_error=error,
        contributions=contributions,
        leads=leads,
        offsets=offsets,
    )


def _category_support(
    current_shipments: int,
    reference_shipments: int,
    weeks_present: int,
    entry: float,
    exit_effect: float,
    policy: RootCausePolicy,
) -> tuple[SupportLevel, tuple[str, ...]]:
    if (entry != 0 or exit_effect != 0) and (current_shipments == 0 or weeks_present == 0):
        return (
            SupportLevel.TRANSITION_ONLY,
            ("Category support is limited to explicit entry or exit comparisons.",),
        )
    if (
        current_shipments >= policy.min_current_category_shipments
        and reference_shipments >= policy.min_reference_category_shipments
        and weeks_present >= 3
    ):
        return SupportLevel.STRONG, ()
    return SupportLevel.LIMITED, ("Category shipment support is limited.",)


def _select_leads(
    lens: str,
    contributions: tuple[CategoryContribution, ...],
    policy: RootCausePolicy,
    *,
    positive: bool,
) -> tuple[OperationalLead, ...]:
    eligible = [
        item
        for item in contributions
        if (item.net_contribution > 0 if positive else item.net_contribution < 0)
        and abs(item.net_contribution) >= policy.min_lead_abs_effect
        and (item.absolute_effect_share_pct or 0) >= policy.min_lead_abs_share_pct
    ]
    eligible.sort(
        key=lambda item: (
            -item.net_contribution if positive else item.net_contribution,
            item.category,
        )
    )
    selected = eligible[: policy.max_leads_per_lens]
    return tuple(
        OperationalLead(
            category=item.category,
            effect=item.net_contribution,
            support_level=item.support_level,
            narrative=_lead_narrative(lens, item),
        )
        for item in selected
    )


def _lead_narrative(lens: str, item: CategoryContribution) -> str:
    qualifier = (
        " It has limited support."
        if item.support_level != SupportLevel.STRONG
        else ""
    )
    direction = "a positive" if item.net_contribution > 0 else "an offsetting"
    return (
        f"{item.category} showed {direction} {lens} decomposition effect of "
        f"{item.net_contribution:+.4f} INR/t-km. This is an operational lead, "
        f"not accepted contextual evidence.{qualifier}"
    )


def _result_support(reference_count: int) -> SupportLevel:
    if reference_count >= 6:
        return SupportLevel.STRONG
    if reference_count >= 3:
        return SupportLevel.MODERATE
    if reference_count >= 1:
        return SupportLevel.LIMITED
    return SupportLevel.UNAVAILABLE


def _metric_values(frame: pd.DataFrame) -> dict[OperationalMetric, float]:
    shipments = int(frame["shipment_id"].nunique())
    tonnes = float(frame["quantity_tonnes"].sum())
    tonne_km = float(frame["tonne_km"].sum())
    freight = float(frame["freight_cost_inr"].sum())
    if shipments <= 0 or tonnes <= 0 or tonne_km <= 0:
        raise AnalysisRunFailedError("Operational metrics require positive denominators.")
    return {
        OperationalMetric.SHIPMENT_COUNT: float(shipments),
        OperationalMetric.AVERAGE_LOAD_TONNES: tonnes / shipments,
        OperationalMetric.WEIGHTED_AVERAGE_DISTANCE_KM: tonne_km / tonnes,
        OperationalMetric.TOTAL_QUANTITY_TONNES: tonnes,
        OperationalMetric.TOTAL_TONNE_KM: tonne_km,
        OperationalMetric.FREIGHT_COST_PER_SHIPMENT: freight / shipments,
        OperationalMetric.SHIPMENTS_PER_100_TONNES: shipments / tonnes * 100,
    }


def _metric_comparisons(
    current: pd.DataFrame,
    references: tuple[pd.DataFrame, ...],
    policy: RootCausePolicy,
) -> tuple[MetricComparison, ...]:
    current_values = _metric_values(current)
    reference_values = tuple(_metric_values(frame) for frame in references)
    units = {
        OperationalMetric.SHIPMENT_COUNT: "shipments",
        OperationalMetric.AVERAGE_LOAD_TONNES: "tonnes/shipment",
        OperationalMetric.WEIGHTED_AVERAGE_DISTANCE_KM: "km",
        OperationalMetric.TOTAL_QUANTITY_TONNES: "tonnes",
        OperationalMetric.TOTAL_TONNE_KM: "tonne-km",
        OperationalMetric.FREIGHT_COST_PER_SHIPMENT: "INR/shipment",
        OperationalMetric.SHIPMENTS_PER_100_TONNES: "shipments/100 tonnes",
    }
    interpretations = {
        OperationalMetric.SHIPMENT_COUNT: "Shipment-count change is descriptive and may indicate consolidation or fragmentation.",
        OperationalMetric.AVERAGE_LOAD_TONNES: "Average-load change may warrant a load-utilization investigation.",
        OperationalMetric.WEIGHTED_AVERAGE_DISTANCE_KM: "Distance change may be associated with nonlinear fixed-charge or routing effects.",
        OperationalMetric.TOTAL_QUANTITY_TONNES: "Tonnage change is descriptive operating context.",
        OperationalMetric.TOTAL_TONNE_KM: "Tonne-km change is descriptive operating context.",
        OperationalMetric.FREIGHT_COST_PER_SHIPMENT: "Per-shipment freight change is descriptive and is not a causal finding.",
        OperationalMetric.SHIPMENTS_PER_100_TONNES: "This is a descriptive fragmentation indicator, not a proven efficiency measure.",
    }
    return tuple(
        _compare_metric(
            metric,
            current_values[metric],
            tuple(values[metric] for values in reference_values),
            units[metric],
            interpretations[metric],
            policy,
        )
        for metric in OperationalMetric
    )


def _compare_metric(
    metric: OperationalMetric,
    current: float,
    references: tuple[float, ...],
    unit: str,
    interpretation: str,
    policy: RootCausePolicy,
) -> MetricComparison:
    reference = sum(references) / len(references)
    change = current - reference
    percentage = change / reference * 100 if reference != 0 else None
    return MetricComparison(
        metric=metric,
        unit=unit,
        current_value=current,
        reference_mean=reference,
        absolute_change=change,
        percentage_change=percentage,
        highlighted=(
            percentage is not None
            and abs(percentage) >= policy.metric_highlight_percent
        ),
        interpretation=interpretation,
    )
