"""Ordered deterministic event, cost-impact, negation, and magnitude rules."""

import re

from ...domain.context_notes import (
    CostImpactStatus,
    EventType,
    ImpactClaim,
    ImpactDirection,
)
from .errors import ImpactCompilationError

_EVENT_RULES = (
    (EventType.RECOVERY_OR_NORMALIZATION, re.compile(r"\breturned\s+to\s+normal\b", re.I)),
    (EventType.FESTIVAL_DEMAND, re.compile(r"\bfestival\b", re.I)),
    (EventType.FUEL_PRICE_CHANGE, re.compile(r"\b(?:diesel|petrol|fuel)\s+prices?\b", re.I)),
    (EventType.REGULATORY_COMPLIANCE, re.compile(r"\b(?:mandate|compliance)\b", re.I)),
    (EventType.ROAD_IMPROVEMENT, re.compile(r"\b(?:improved\s+road\s+conditions|resurfacing)\b", re.I)),
    (EventType.ROAD_MAINTENANCE, re.compile(r"\b(?:road|highway)\s+maintenance\b", re.I)),
    (EventType.WEATHER_DISRUPTION, re.compile(r"\b(?:flood(?:ing|-related)?|cyclone|storm|heavy\s+rain)\b", re.I)),
    (EventType.TOLL_OR_INFRASTRUCTURE, re.compile(r"\b(?:toll\s+plaza|toll|infrastructure)\b", re.I)),
    (EventType.NORMAL_OPERATIONS, re.compile(r"\b(?:no\s+significant\s+disruptions|movement\s+remained\s+normal|normal\s+operations)\b", re.I)),
    (EventType.CAPACITY_OR_DEMAND_CONDITION, re.compile(r"\b(?:freight\s+capacity|truck\s+availability|demand)\b", re.I)),
)

_NO_RATE_CHANGE = re.compile(
    r"\b(?:without\s+a\s+rate\s+change|no\s+change\s+in\s+freight\s+rates|"
    r"absorbed\s+by\s+transporters)\b",
    re.IGNORECASE,
)
_NO_MATERIAL_IMPACT = re.compile(
    r"\b(?:costs?\s+(?:were\s+)?not\s+significantly\s+affected|"
    r"no\s+material\s+impact\s+on\s+(?:transport|freight)\s+costs?)\b",
    re.IGNORECASE,
)
_NORMAL_OR_STABLE = re.compile(
    r"\b(?:remained\s+stable|no\s+major\s+disruptions|"
    r"no\s+significant\s+disruptions|remained\s+normal|"
    r"returned\s+to\s+normal|normal\s+operations)\b",
    re.IGNORECASE,
)
_COST_DECREASE = re.compile(
    r"\b(?:(?:transport(?:ation)?|freight|trip)\s+(?:costs?|rates?)\s+"
    r"(?:fell|decreased|declined)|(?:reduced|lower)\s+(?:transport(?:ation)?|freight|trip)\s+(?:costs?|rates?))\b",
    re.IGNORECASE,
)
_COST_INCREASE = re.compile(
    r"\b(?:higher\s+trip\s+costs?|pushing\s+up\s+transportation\s+costs?|"
    r"(?:temporary\s+)?surcharge\s+applied\s+by\s+transporters|"
    r"freight\s+rates?\s+(?:increased|rose)|"
    r"transport(?:ation)?\s+costs?\s+(?:increased|rose))\b",
    re.IGNORECASE,
)
_COST_CONTEXT = re.compile(
    r"\b(?:transport(?:ation)?|freight|trip)\s+(?:costs?|rates?)\b|"
    r"\bsurcharge\b|\b(?:diesel|petrol|fuel)\s+prices?\b",
    re.IGNORECASE,
)
_PERCENT_MAGNITUDE = re.compile(
    r"(?:(?:roughly|about|approximately)\s+)?\d+(?:\.\d+)?\s*"
    r"(?:-\s*\d+(?:\.\d+)?)?\s*(?:%|percent\b)",
    re.IGNORECASE,
)
_CURRENCY_MAGNITUDE = re.compile(
    r"(?:INR|₹)\s*\d+(?:\.\d+)?\s+per\s+(?:kilometre|kilometer|km)\b",
    re.IGNORECASE,
)


def compile_impact_claim(original_text: str) -> ImpactClaim:
    """Compile event meaning separately from authoritative cost-impact meaning."""
    if not isinstance(original_text, str) or not original_text.strip():
        raise ImpactCompilationError("original_text must contain non-blank text.")

    event_type = _classify_event(original_text)
    warnings: set[str] = set()
    no_rate = bool(_NO_RATE_CHANGE.search(original_text))
    no_material = bool(_NO_MATERIAL_IMPACT.search(original_text))
    stable = bool(_NORMAL_OR_STABLE.search(original_text))
    decrease = bool(_COST_DECREASE.search(original_text))
    increase = bool(_COST_INCREASE.search(original_text))

    # Explicit contradictory cost claims are retained as uncertainty, never guessed.
    if (no_rate or no_material) and (increase or decrease):
        status = CostImpactStatus.UNKNOWN
        direction = ImpactDirection.UNKNOWN
        affects: bool | None = None
        negates = False
        warnings.add("conflicting_cost_claims")
    elif no_rate:
        status = CostImpactStatus.EXPLICIT_NO_RATE_CHANGE
        direction = ImpactDirection.NO_CHANGE
        affects = False
        negates = True
    elif no_material:
        status = CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT
        direction = ImpactDirection.NO_CHANGE
        affects = False
        negates = True
    elif stable:
        status = CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS
        direction = ImpactDirection.NO_CHANGE
        affects = False
        negates = True
    elif decrease and increase:
        status = CostImpactStatus.UNKNOWN
        direction = ImpactDirection.UNKNOWN
        affects = None
        negates = False
        warnings.add("conflicting_cost_claims")
    elif decrease:
        status = CostImpactStatus.EXPLICIT_DECREASE
        direction = ImpactDirection.DECREASE
        affects = True
        negates = False
    elif increase:
        status = CostImpactStatus.EXPLICIT_INCREASE
        direction = ImpactDirection.INCREASE
        affects = True
        negates = False
    else:
        status = CostImpactStatus.NOT_STATED
        direction = ImpactDirection.UNKNOWN
        affects = None
        negates = False
        warnings.add("transport_cost_impact_not_stated")

    magnitude, magnitude_warnings = _extract_magnitude(original_text)
    warnings.update(magnitude_warnings)
    if event_type == EventType.UNKNOWN:
        warnings.add("event_type_unknown")
    return ImpactClaim(
        event_type=event_type,
        impact_direction=direction,
        cost_impact_status=status,
        affects_transport_cost=affects,
        negates_cost_increase=negates,
        magnitude_text=magnitude,
        warnings=tuple(sorted(warnings)),
    )


def _classify_event(text: str) -> EventType:
    for event_type, pattern in _EVENT_RULES:
        if pattern.search(text):
            return event_type
    if re.search(r"\b(?:delay|disruption|closure|construction)\b", text, re.I):
        return EventType.OTHER
    return EventType.UNKNOWN


def _extract_magnitude(text: str) -> tuple[str | None, tuple[str, ...]]:
    if _COST_CONTEXT.search(text) is None:
        return None, ()
    matches = [
        match.group(0).strip()
        for pattern in (_PERCENT_MAGNITUDE, _CURRENCY_MAGNITUDE)
        for match in pattern.finditer(text)
    ]
    unique = tuple(dict.fromkeys(matches))
    if len(unique) > 1:
        return None, ("conflicting_cost_magnitudes",)
    return (unique[0] if unique else None), ()
