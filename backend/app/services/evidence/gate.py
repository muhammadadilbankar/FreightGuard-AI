"""Deterministic hard Evidence Gate for one candidate-note pair."""

from datetime import date
import re

from ...domain.context_notes import (
    CompiledContextNote,
    CostImpactStatus,
    ImpactDirection,
    ScopeStatus,
    ScopeType,
)
from ...domain.evidence import (
    CandidateEvidenceQuery,
    EvidenceAssessment,
    EvidenceCoverage,
    EvidenceLevel,
    EvidencePolicy,
    GateCheck,
    RejectionCode,
    RetrievalHit,
)

_PERCENT_RANGE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:%|percent\b)",
    re.IGNORECASE,
)


def assess_evidence(
    candidate: CandidateEvidenceQuery,
    note: CompiledContextNote,
    retrieval: RetrievalHit,
    policy: EvidencePolicy,
) -> EvidenceAssessment:
    """Apply every hard gate, then determine full/partial explanatory coverage."""
    codes: set[RejectionCode] = set()
    consistent = _compiled_claim_consistent(note)
    if not consistent:
        codes.add(RejectionCode.COMPILED_CLAIM_INCONSISTENT)

    if note.scope_status in {ScopeStatus.IN_DATASET, ScopeStatus.PARTIALLY_IN_DATASET}:
        scope_check = GateCheck.PASS
    else:
        scope_check = GateCheck.FAIL
        codes.add(
            RejectionCode.SCOPE_OUTSIDE_DATASET
            if note.scope_status == ScopeStatus.OUTSIDE_DATASET
            else RejectionCode.SCOPE_UNRESOLVED
        )

    exact_route = (
        note.scope_type == ScopeType.ROUTE
        and candidate.route in note.applies_to_routes
    )
    route_passes = note.scope_type == ScopeType.GLOBAL or exact_route
    route_check = GateCheck.PASS if route_passes else GateCheck.FAIL
    if not route_passes:
        codes.add(RejectionCode.ROUTE_MISMATCH)

    overlap_days = _overlap_days(
        candidate.week_of,
        candidate.week_end,
        note.effective_from,
        note.effective_to,
    )
    date_check = GateCheck.PASS if overlap_days > 0 else GateCheck.FAIL
    if overlap_days == 0:
        codes.add(RejectionCode.DATE_NO_OVERLAP)

    cost_positive = (
        note.cost_impact_status == CostImpactStatus.EXPLICIT_INCREASE
        and note.affects_transport_cost is True
    )
    cost_check = GateCheck.PASS if cost_positive else GateCheck.FAIL
    if not cost_positive:
        codes.add(RejectionCode.COST_IMPACT_NOT_POSITIVE)

    direction_positive = note.impact_direction == ImpactDirection.INCREASE
    direction_check = GateCheck.PASS if direction_positive else GateCheck.FAIL
    if not direction_positive:
        codes.add(RejectionCode.IMPACT_DIRECTION_NOT_INCREASE)

    negation_check = GateCheck.PASS if not note.negates_cost_increase else GateCheck.FAIL
    if note.negates_cost_increase:
        codes.add(RejectionCode.COST_INCREASE_NEGATED)

    hard_passes = all(
        (
            consistent,
            scope_check == GateCheck.PASS,
            route_check == GateCheck.PASS,
            date_check == GateCheck.PASS,
            cost_check == GateCheck.PASS,
            direction_check == GateCheck.PASS,
            negation_check == GateCheck.PASS,
        )
    )
    coverage = EvidenceCoverage.NONE
    level = EvidenceLevel.REJECTED
    has_magnitude = _magnitude_upper_bound(note.magnitude_text) is not None
    if hard_passes:
        if exact_route:
            coverage = EvidenceCoverage.FULL
        elif candidate.peer_threshold_breached:
            coverage = EvidenceCoverage.PARTIAL
            codes.add(RejectionCode.GLOBAL_SCOPE_CANNOT_EXPLAIN_PEER_PREMIUM)
        else:
            upper = _magnitude_upper_bound(note.magnitude_text)
            if (
                upper is not None
                and candidate.vs_own_history_pct
                > upper + policy.global_magnitude_tolerance_percent
            ):
                coverage = EvidenceCoverage.PARTIAL
                codes.add(RejectionCode.GLOBAL_MAGNITUDE_INSUFFICIENT)
            else:
                coverage = EvidenceCoverage.FULL
        level = (
            EvidenceLevel.FULL
            if coverage == EvidenceCoverage.FULL
            else EvidenceLevel.PARTIAL
        )

    return EvidenceAssessment(
        route=candidate.route,
        week_of=candidate.week_of,
        note_id=note.note_id,
        route_check=route_check,
        date_check=date_check,
        scope_check=scope_check,
        direction_check=direction_check,
        cost_impact_check=cost_check,
        negation_check=negation_check,
        explanatory_scope=coverage,
        overlap_days=overlap_days,
        evidence_level=level,
        rejection_codes=tuple(sorted(codes, key=lambda code: code.value)),
        retrieval=retrieval,
        exact_route_scope=exact_route,
        has_numeric_magnitude=has_magnitude,
    )


def _overlap_days(
    candidate_start: date,
    candidate_end: date,
    note_start: date,
    note_end: date | None,
) -> int:
    effective_end = note_end or candidate_end
    start = max(candidate_start, note_start)
    end = min(candidate_end, effective_end)
    return max(0, (end - start).days + 1)


def _compiled_claim_consistent(note: CompiledContextNote) -> bool:
    if note.effective_to is not None and note.effective_to < note.effective_from:
        return False
    if note.scope_type == ScopeType.GLOBAL and note.applies_to_routes:
        return False
    if note.scope_type == ScopeType.ROUTE and not note.applies_to_routes:
        return False
    if note.cost_impact_status == CostImpactStatus.EXPLICIT_INCREASE:
        return (
            note.impact_direction == ImpactDirection.INCREASE
            and note.affects_transport_cost is True
            and not note.negates_cost_increase
        )
    return True


def _magnitude_upper_bound(value: str | None) -> float | None:
    if value is None:
        return None
    match = _PERCENT_RANGE.search(value)
    if match is None:
        return None
    return float(match.group(1) or re.search(r"\d+(?:\.\d+)?", value).group(0))
