"""Tests for event, impact, negation, and magnitude compilation."""

import pytest

from backend.app.domain.context_notes import (
    CostImpactStatus,
    EventType,
    ImpactDirection,
)
from backend.app.services.context import compile_impact_claim


@pytest.mark.parametrize(
    ("text", "event"),
    [
        ("Flooding caused higher trip costs.", EventType.WEATHER_DISRUPTION),
        ("A festival surcharge applied by transporters.", EventType.FESTIVAL_DEMAND),
        ("Diesel prices rose, pushing up transportation costs.", EventType.FUEL_PRICE_CHANGE),
    ],
)
def test_explicit_increases_require_cost_language(text: str, event: EventType) -> None:
    result = compile_impact_claim(text)

    assert result.event_type == event
    assert result.cost_impact_status == CostImpactStatus.EXPLICIT_INCREASE
    assert result.impact_direction == ImpactDirection.INCREASE
    assert result.affects_transport_cost is True
    assert result.negates_cost_increase is False


def test_generic_increase_without_cost_context_is_not_positive_evidence() -> None:
    result = compile_impact_claim("Festival traffic increased sharply this week.")

    assert result.cost_impact_status == CostImpactStatus.NOT_STATED
    assert result.affects_transport_cost is None
    assert "transport_cost_impact_not_stated" in result.warnings


@pytest.mark.parametrize(
    ("text", "status", "event"),
    [
        (
            "Highway maintenance caused delays; costs were not significantly affected.",
            CostImpactStatus.EXPLICIT_NO_MATERIAL_IMPACT,
            EventType.ROAD_MAINTENANCE,
        ),
        (
            "A compliance mandate added work without a rate change.",
            CostImpactStatus.EXPLICIT_NO_RATE_CHANGE,
            EventType.REGULATORY_COMPLIANCE,
        ),
        (
            "Freight capacity remained stable with no major disruptions.",
            CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS,
            EventType.CAPACITY_OR_DEMAND_CONDITION,
        ),
        (
            "The route returned to normal after flood repairs.",
            CostImpactStatus.NORMAL_OR_STABLE_OPERATIONS,
            EventType.RECOVERY_OR_NORMALIZATION,
        ),
    ],
)
def test_negation_and_stability_precede_positive_keywords(
    text: str, status: CostImpactStatus, event: EventType
) -> None:
    result = compile_impact_claim(text)

    assert result.event_type == event
    assert result.cost_impact_status == status
    assert result.impact_direction == ImpactDirection.NO_CHANGE
    assert result.affects_transport_cost is False
    assert result.negates_cost_increase is True


def test_road_improvement_does_not_infer_cost_decrease() -> None:
    result = compile_impact_claim(
        "Improved road conditions followed after resurfacing was completed."
    )

    assert result.event_type == EventType.ROAD_IMPROVEMENT
    assert result.cost_impact_status == CostImpactStatus.NOT_STATED
    assert result.impact_direction == ImpactDirection.UNKNOWN
    assert result.affects_transport_cost is None


def test_explicit_cost_decrease_is_typed_as_affecting_cost() -> None:
    result = compile_impact_claim("Freight rates decreased after the change.")

    assert result.cost_impact_status == CostImpactStatus.EXPLICIT_DECREASE
    assert result.impact_direction == ImpactDirection.DECREASE
    assert result.affects_transport_cost is True


def test_conflicting_supported_cost_claims_become_unknown() -> None:
    result = compile_impact_claim(
        "Transport costs rose, but there was no change in freight rates."
    )

    assert result.cost_impact_status == CostImpactStatus.UNKNOWN
    assert result.impact_direction == ImpactDirection.UNKNOWN
    assert result.affects_transport_cost is None
    assert result.warnings == ("conflicting_cost_claims", "event_type_unknown")


@pytest.mark.parametrize(
    ("text", "magnitude"),
    [
        ("Transport costs rose by roughly 5-7%.", "roughly 5-7%"),
        ("Freight rates increased about 6 percent.", "about 6 percent"),
        ("A freight surcharge of INR 2 per kilometre applied.", "INR 2 per kilometre"),
        ("Transport delays lasted for about a week.", None),
        ("Minor delays affected trucks.", None),
    ],
)
def test_cost_magnitude_extraction(text: str, magnitude: str | None) -> None:
    assert compile_impact_claim(text).magnitude_text == magnitude


def test_multiple_cost_magnitudes_are_not_guessed() -> None:
    result = compile_impact_claim("Transport costs rose 5% before rising 8%.")

    assert result.magnitude_text is None
    assert "conflicting_cost_magnitudes" in result.warnings


def test_case_punctuation_and_word_boundaries() -> None:
    assert (
        compile_impact_claim("TRANSPORT COSTS ROSE.").cost_impact_status
        == CostImpactStatus.EXPLICIT_INCREASE
    )
    assert (
        compile_impact_claim("A costume rate rose.").cost_impact_status
        == CostImpactStatus.NOT_STATED
    )
