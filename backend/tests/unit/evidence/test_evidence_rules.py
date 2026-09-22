"""Query, fusion, recall, gate, and decision rule tests."""

from datetime import date

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
    EvidenceLevel,
    EvidencePolicy,
    EvidenceVerdict,
    RejectionCode,
    RetrievalConfig,
    RetrievalHit,
)
from backend.app.services.evidence import (
    assess_evidence,
    decide_evidence,
    fuse_rankings,
    structured_recall,
    union_retrieval_and_recall,
)


def candidate(*, peer: bool = False) -> CandidateEvidenceQuery:
    return CandidateEvidenceQuery(
        route="A-B",
        route_type="medium",
        week_of=date(2025, 1, 6),
        week_end=date(2025, 1, 12),
        cost_per_tonne_km=1.25,
        vs_own_history_pct=25.123456789,
        vs_similar_routes_pct=22.5 if peer else 1.0,
        own_threshold_breached=True,
        peer_threshold_breached=peer,
        query_text="stable query",
    )


def note(
    note_id: str = "N100",
    *,
    scope: ScopeType = ScopeType.ROUTE,
    routes: tuple[str, ...] = ("A-B",),
    start: date = date(2025, 1, 6),
    end: date | None = date(2025, 1, 12),
    status: CostImpactStatus = CostImpactStatus.EXPLICIT_INCREASE,
    magnitude: str | None = "25-30%",
) -> CompiledContextNote:
    positive = status == CostImpactStatus.EXPLICIT_INCREASE
    unknown = status == CostImpactStatus.NOT_STATED
    return CompiledContextNote(
        note_id=note_id,
        source_date=start,
        source_applies_to="All routes" if scope == ScopeType.GLOBAL else ", ".join(routes),
        original_text="Freight transport costs increased by 25-30%.",
        scope_type=scope,
        applies_to_routes=() if scope == ScopeType.GLOBAL else routes,
        scope_status=ScopeStatus.IN_DATASET,
        effective_from=start,
        effective_to=end,
        temporal_basis=TemporalBasis.EXPLICIT_RANGE,
        event_type=EventType.FUEL_PRICE_CHANGE,
        impact_direction=(
            ImpactDirection.INCREASE
            if positive
            else ImpactDirection.UNKNOWN
            if unknown
            else ImpactDirection.NO_CHANGE
        ),
        cost_impact_status=status,
        affects_transport_cost=True if positive else None if unknown else False,
        negates_cost_increase=not positive and not unknown,
        magnitude_text=magnitude,
        compilation_warnings=(),
    )


def hit(note_id: str, rank: int = 1) -> RetrievalHit:
    return RetrievalHit(note_id=note_id, fused_rank=rank, fused_score=0.1)


def test_rrf_uses_rank_not_raw_score_and_is_stable() -> None:
    sparse = (
        RetrievalHit(note_id="N2", sparse_rank=1, sparse_score=0.1),
        RetrievalHit(note_id="N1", sparse_rank=2, sparse_score=999.0),
    )
    dense = (
        RetrievalHit(note_id="N1", dense_rank=1, dense_score=-5.0),
        RetrievalHit(note_id="N2", dense_rank=2, dense_score=500.0),
    )
    config = RetrievalConfig(top_k=2, rrf_k=60, sparse_weight=1, dense_weight=1)
    fused = fuse_rankings(sparse, dense, config)
    assert [item.note_id for item in fused] == ["N1", "N2"]
    assert fused[0].fused_score == fused[1].fused_score


def test_structured_recall_handles_global_route_overlap_and_no_impact() -> None:
    notes = (
        note("GLOBAL", scope=ScopeType.GLOBAL, routes=()),
        note("EXACT", status=CostImpactStatus.EXPLICIT_NO_RATE_CHANGE),
        note("WRONG", routes=("B-A",)),
        note("LATE", start=date(2025, 1, 13), end=None),
    )
    assert structured_recall(candidate(), tuple(reversed(notes))) == ("EXACT", "GLOBAL")
    union = union_retrieval_and_recall((hit("WRONG"),), ("EXACT",))
    assert [item.note_id for item in union] == ["EXACT", "WRONG"]
    assert union[0].included_by_structured_recall is True


def test_gate_accepts_exact_route_and_rejects_wrong_route_or_date() -> None:
    policy = EvidencePolicy()
    full = assess_evidence(candidate(), note(), hit("N100"), policy)
    wrong = assess_evidence(
        candidate(), note("WRONG", routes=("B-A",)), hit("WRONG"), policy
    )
    late = assess_evidence(
        candidate(),
        note("LATE", start=date(2025, 1, 13), end=None),
        hit("LATE"),
        policy,
    )
    assert full.evidence_level == EvidenceLevel.FULL
    assert RejectionCode.ROUTE_MISMATCH in wrong.rejection_codes
    assert RejectionCode.DATE_NO_OVERLAP in late.rejection_codes


def test_gate_one_day_overlap_passes_and_no_impact_unknown_reject() -> None:
    policy = EvidencePolicy()
    one_day = assess_evidence(
        candidate(), note(end=date(2025, 1, 6)), hit("N100"), policy
    )
    no_change = assess_evidence(
        candidate(),
        note("NO", status=CostImpactStatus.EXPLICIT_NO_RATE_CHANGE),
        hit("NO"),
        policy,
    )
    unknown = assess_evidence(
        candidate(),
        note("UNKNOWN", status=CostImpactStatus.NOT_STATED),
        hit("UNKNOWN"),
        policy,
    )
    assert one_day.overlap_days == 1
    assert one_day.evidence_level == EvidenceLevel.FULL
    assert no_change.evidence_level == EvidenceLevel.REJECTED
    assert unknown.evidence_level == EvidenceLevel.REJECTED


def test_global_policy_is_full_for_own_and_partial_for_peer() -> None:
    global_note = note("G", scope=ScopeType.GLOBAL, routes=())
    policy = EvidencePolicy(global_magnitude_tolerance_percent=2)
    own = assess_evidence(candidate(), global_note, hit("G"), policy)
    peer = assess_evidence(candidate(peer=True), global_note, hit("G"), policy)
    too_small = assess_evidence(
        candidate(),
        note("SMALL", scope=ScopeType.GLOBAL, routes=(), magnitude="10%"),
        hit("SMALL"),
        policy,
    )
    assert own.evidence_level == EvidenceLevel.FULL
    assert peer.evidence_level == EvidenceLevel.PARTIAL
    assert RejectionCode.GLOBAL_SCOPE_CANNOT_EXPLAIN_PEER_PREMIUM in peer.rejection_codes
    assert too_small.evidence_level == EvidenceLevel.PARTIAL


def test_decision_partition_and_full_selection_are_deterministic() -> None:
    policy = EvidencePolicy()
    query = candidate(peer=True)
    partial = assess_evidence(
        query, note("P", scope=ScopeType.GLOBAL, routes=()), hit("P", 1), policy
    )
    full_b = assess_evidence(query, note("B"), hit("B", 1), policy)
    full_a = assess_evidence(query, note("A"), hit("A", 2), policy)
    decision = decide_evidence(query, (partial, full_b, full_a))
    assert decision.verdict == EvidenceVerdict.JUSTIFIED
    assert decision.selected_note_id == "B"
    assert decision.supporting_note_ids == ("P",)
    partial_only = decide_evidence(query, (partial,))
    assert partial_only.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED
    assert partial_only.selected_note_id is None


def test_rejected_notes_cannot_become_support() -> None:
    query = candidate()
    rejected = assess_evidence(
        query,
        note("NO", status=CostImpactStatus.EXPLICIT_NO_RATE_CHANGE),
        hit("NO"),
        EvidencePolicy(),
    )
    decision = decide_evidence(query, (rejected,))
    assert decision.verdict == EvidenceVerdict.UNEXPLAINED
    assert decision.supporting_note_ids == ()
