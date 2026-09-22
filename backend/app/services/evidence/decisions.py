"""Aggregate pair assessments into one deterministic candidate verdict."""

from collections.abc import Mapping, Sequence

from ...domain.context_notes import CompiledContextNote
from ...domain.evidence import (
    CandidateEvidenceQuery,
    EvidenceAssessment,
    EvidenceDecision,
    EvidenceLevel,
    EvidenceVerdict,
    ReasonTemplateKey,
    ValidatedEvidencePacket,
)
from .errors import EvidenceDecisionError


def decide_evidence(
    candidate: CandidateEvidenceQuery,
    assessments: Sequence[EvidenceAssessment],
) -> EvidenceDecision:
    """Apply verdict partition and deterministic full-evidence selection."""
    ordered = tuple(sorted(assessments, key=lambda item: item.note_id))
    if any(
        item.route != candidate.route or item.week_of != candidate.week_of
        for item in ordered
    ):
        raise EvidenceDecisionError("Assessment keys must match the candidate.")
    if len({item.note_id for item in ordered}) != len(ordered):
        raise EvidenceDecisionError("Assessment note IDs must be unique.")
    full = [item for item in ordered if item.evidence_level == EvidenceLevel.FULL]
    partial = [
        item for item in ordered if item.evidence_level == EvidenceLevel.PARTIAL
    ]
    selected: str | None = None
    if full:
        full.sort(key=_selection_key)
        selected = full[0].note_id
        verdict = EvidenceVerdict.JUSTIFIED
        reason = ReasonTemplateKey.JUSTIFIED
    elif partial:
        verdict = EvidenceVerdict.PARTIALLY_EXPLAINED
        reason = ReasonTemplateKey.PARTIALLY_EXPLAINED
    else:
        verdict = EvidenceVerdict.UNEXPLAINED
        reason = ReasonTemplateKey.UNEXPLAINED
    return EvidenceDecision(
        route=candidate.route,
        week_of=candidate.week_of,
        verdict=verdict,
        selected_note_id=selected,
        supporting_note_ids=tuple(sorted(item.note_id for item in partial)),
        reason_template_key=reason,
        assessed_note_ids=tuple(item.note_id for item in ordered),
    )


def build_evidence_packet(
    candidate: CandidateEvidenceQuery,
    decision: EvidenceDecision,
    notes_by_id: Mapping[str, CompiledContextNote],
) -> ValidatedEvidencePacket:
    """Build the Phase 8 allowlisted packet from accepted evidence only."""
    try:
        selected = (
            notes_by_id[decision.selected_note_id]
            if decision.selected_note_id is not None
            else None
        )
        supporting = tuple(notes_by_id[note_id] for note_id in decision.supporting_note_ids)
    except KeyError as exc:
        raise EvidenceDecisionError("Decision references an unknown compiled note.") from exc
    allowed = tuple(
        sorted(
            ({selected.note_id} if selected else set())
            | {note.note_id for note in supporting}
        )
    )
    return ValidatedEvidencePacket(
        candidate=candidate,
        decision=decision,
        selected_note=selected,
        supporting_notes=supporting,
        allowed_note_ids=allowed,
    )


def _selection_key(item: EvidenceAssessment) -> tuple[object, ...]:
    missing = 2**31
    return (
        -int(item.exact_route_scope),
        -item.overlap_days,
        -int(item.has_numeric_magnitude),
        item.retrieval.fused_rank or missing,
        item.retrieval.dense_rank or missing,
        item.retrieval.sparse_rank or missing,
        item.note_id,
    )
