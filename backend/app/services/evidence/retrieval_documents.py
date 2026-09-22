"""Deterministic searchable representations of compiled notes."""

from collections.abc import Sequence

from ...domain.context_notes import CompiledContextNote, ScopeType
from .errors import EvidenceInputError


def build_retrieval_document(note: CompiledContextNote) -> str:
    """Prefix exact source text with stable typed retrieval metadata."""
    scope = (
        "global"
        if note.scope_type == ScopeType.GLOBAL
        else ", ".join(note.applies_to_routes) or "unknown"
    )
    effective_to = note.effective_to.isoformat() if note.effective_to else "open ended"
    return (
        f"Note {note.note_id}.\n"
        f"Scope: {scope}.\n"
        f"Effective: {note.effective_from.isoformat()} to {effective_to}.\n"
        f"Event: {note.event_type.value}.\n"
        f"Transport cost impact: {note.cost_impact_status.value}.\n"
        f"Direction: {note.impact_direction.value}.\n"
        f"Text: {note.original_text}"
    )


def build_retrieval_documents(
    notes: Sequence[CompiledContextNote],
) -> tuple[tuple[str, str], ...]:
    if not notes:
        raise EvidenceInputError("Retrieval requires at least one compiled note.")
    ordered = tuple(sorted(notes, key=lambda note: note.note_id))
    if len({note.note_id for note in ordered}) != len(ordered):
        raise EvidenceInputError("Compiled note IDs must be unique.")
    return tuple((note.note_id, build_retrieval_document(note)) for note in ordered)
