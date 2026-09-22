"""Exact route/time structured-recall safety net."""

from collections.abc import Sequence

from ...domain.context_notes import CompiledContextNote, ScopeType
from ...domain.evidence import CandidateEvidenceQuery, RetrievalHit


def structured_recall(
    candidate: CandidateEvidenceQuery,
    notes: Sequence[CompiledContextNote],
) -> tuple[str, ...]:
    """Return every exact/global note whose inclusive interval overlaps the week."""
    recalled: list[str] = []
    for note in notes:
        route_applies = note.scope_type == ScopeType.GLOBAL or (
            candidate.route in note.applies_to_routes
        )
        date_applies = note.effective_from <= candidate.week_end and (
            note.effective_to is None or note.effective_to >= candidate.week_of
        )
        if route_applies and date_applies:
            recalled.append(note.note_id)
    return tuple(sorted(set(recalled)))


def union_retrieval_and_recall(
    fused_hits: Sequence[RetrievalHit], recalled_note_ids: Sequence[str]
) -> tuple[RetrievalHit, ...]:
    """Preserve retrieval metadata and mark/add structured recall candidates."""
    by_note = {hit.note_id: hit for hit in fused_hits}
    for note_id in recalled_note_ids:
        existing = by_note.get(note_id, RetrievalHit(note_id=note_id))
        by_note[note_id] = existing.model_copy(
            update={"included_by_structured_recall": True}
        )
    return tuple(by_note[note_id] for note_id in sorted(by_note))
