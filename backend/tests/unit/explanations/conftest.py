"""Small authoritative packet fixtures for Phase 8 tests."""

from datetime import date

import pytest

from backend.app.domain.context_notes import (
    CompiledContextNote,
    CostImpactStatus,
    EventType,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
    TemporalBasis,
)
from backend.app.domain.evidence import (
    CandidateEvidenceQuery,
    EvidenceDecision,
    EvidenceVerdict,
    ReasonTemplateKey,
    ValidatedEvidencePacket,
)


def _candidate(peer: bool) -> CandidateEvidenceQuery:
    return CandidateEvidenceQuery(
        route="A-B",
        route_type="medium",
        week_of=date(2025, 1, 6),
        week_end=date(2025, 1, 12),
        cost_per_tonne_km=1.2345,
        vs_own_history_pct=25.25,
        vs_similar_routes_pct=22.0 if peer else 5.0,
        own_threshold_breached=True,
        peer_threshold_breached=peer,
        query_text="query",
    )


def _note(note_id: str, *, global_scope: bool = False) -> CompiledContextNote:
    return CompiledContextNote(
        note_id=note_id,
        source_date=date(2025, 1, 6),
        source_applies_to="All Routes" if global_scope else "A-B",
        original_text="Freight transport costs increased during the week.",
        scope_type=ScopeType.GLOBAL if global_scope else ScopeType.ROUTE,
        applies_to_routes=() if global_scope else ("A-B",),
        scope_status=ScopeStatus.IN_DATASET,
        effective_from=date(2025, 1, 6),
        effective_to=date(2025, 1, 12),
        temporal_basis=TemporalBasis.EXPLICIT_RANGE,
        event_type=EventType.FUEL_PRICE_CHANGE,
        impact_direction=ImpactDirection.INCREASE,
        cost_impact_status=CostImpactStatus.EXPLICIT_INCREASE,
        affects_transport_cost=True,
        negates_cost_increase=False,
        magnitude_text=None,
        compilation_warnings=(),
    )


@pytest.fixture
def justified_packet() -> ValidatedEvidencePacket:
    candidate = _candidate(True)
    selected = _note("N100")
    decision = EvidenceDecision(
        route=candidate.route,
        week_of=candidate.week_of,
        verdict=EvidenceVerdict.JUSTIFIED,
        selected_note_id="N100",
        supporting_note_ids=(),
        reason_template_key=ReasonTemplateKey.JUSTIFIED,
        assessed_note_ids=("N100", "N999"),
    )
    return ValidatedEvidencePacket(
        candidate=candidate,
        decision=decision,
        selected_note=selected,
        supporting_notes=(),
        allowed_note_ids=("N100",),
    )


@pytest.fixture
def partial_packet() -> ValidatedEvidencePacket:
    candidate = _candidate(True)
    supporting = _note("N200", global_scope=True)
    decision = EvidenceDecision(
        route=candidate.route,
        week_of=candidate.week_of,
        verdict=EvidenceVerdict.PARTIALLY_EXPLAINED,
        selected_note_id=None,
        supporting_note_ids=("N200",),
        reason_template_key=ReasonTemplateKey.PARTIALLY_EXPLAINED,
        assessed_note_ids=("N200", "N999"),
    )
    return ValidatedEvidencePacket(
        candidate=candidate,
        decision=decision,
        selected_note=None,
        supporting_notes=(supporting,),
        allowed_note_ids=("N200",),
    )


@pytest.fixture
def unexplained_packet() -> ValidatedEvidencePacket:
    candidate = _candidate(False)
    decision = EvidenceDecision(
        route=candidate.route,
        week_of=candidate.week_of,
        verdict=EvidenceVerdict.UNEXPLAINED,
        selected_note_id=None,
        supporting_note_ids=(),
        reason_template_key=ReasonTemplateKey.UNEXPLAINED,
        assessed_note_ids=("N999",),
    )
    return ValidatedEvidencePacket(
        candidate=candidate,
        decision=decision,
        selected_note=None,
        supporting_notes=(),
        allowed_note_ids=(),
    )
