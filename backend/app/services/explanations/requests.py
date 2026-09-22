"""Grounded request construction from Phase 7 validated packets only."""

from ...domain.evidence import EvidenceVerdict, ValidatedEvidencePacket
from ...domain.explanations import (
    ExplanationEvidenceItem,
    GroundedExplanationRequest,
)
from .errors import ExplanationInputError


def build_grounded_request(
    packet: ValidatedEvidencePacket, prompt_version: str
) -> GroundedExplanationRequest:
    """Revalidate packet authority and expose only accepted evidence."""
    _validate_packet(packet)
    evidence = []
    if packet.selected_note is not None:
        evidence.append(_evidence_item(packet.selected_note, "selected"))
    evidence.extend(_evidence_item(note, "supporting") for note in packet.supporting_notes)
    evidence.sort(key=lambda item: (item.role != "selected", item.note_id))
    candidate = packet.candidate
    peer_display = (
        None
        if candidate.vs_similar_routes_pct is None
        else f"{candidate.vs_similar_routes_pct:+.1f}% vs similar-length routes this week"
    )
    return GroundedExplanationRequest(
        prompt_version=prompt_version,
        route=candidate.route,
        route_type=candidate.route_type,
        week_of=candidate.week_of,
        week_end=candidate.week_end,
        cost_per_tonne_km_display=f"{candidate.cost_per_tonne_km:.2f}",
        vs_own_history_display=(
            f"{candidate.vs_own_history_pct:+.1f}% vs this route's past average"
        ),
        vs_similar_routes_display=peer_display,
        verdict=packet.decision.verdict,
        flagged=(
            "No (justified)"
            if packet.decision.verdict == EvidenceVerdict.JUSTIFIED
            else "Yes"
        ),
        selected_note_id=packet.decision.selected_note_id,
        allowed_note_ids=packet.allowed_note_ids,
        evidence=tuple(evidence),
    )


def _evidence_item(note, role: str) -> ExplanationEvidenceItem:
    return ExplanationEvidenceItem(
        note_id=note.note_id,
        role=role,
        scope_type=note.scope_type,
        effective_from=note.effective_from,
        effective_to=note.effective_to,
        event_type=note.event_type,
        impact_direction=note.impact_direction,
        cost_impact_status=note.cost_impact_status,
        magnitude_text=note.magnitude_text,
        original_text=note.original_text,
    )


def _validate_packet(packet: ValidatedEvidencePacket) -> None:
    decision = packet.decision
    candidate = packet.candidate
    if (decision.route, decision.week_of) != (candidate.route, candidate.week_of):
        raise ExplanationInputError("Packet decision identity does not match candidate.")
    selected_id = decision.selected_note_id
    support_ids = tuple(note.note_id for note in packet.supporting_notes)
    if decision.verdict == EvidenceVerdict.JUSTIFIED:
        if (
            selected_id is None
            or packet.selected_note is None
            or packet.selected_note.note_id != selected_id
            or selected_id not in packet.allowed_note_ids
        ):
            raise ExplanationInputError("Justified packet lacks its selected evidence.")
    elif decision.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED:
        if selected_id is not None or packet.selected_note is not None or not support_ids:
            raise ExplanationInputError("Partial packet evidence shape is invalid.")
    elif selected_id is not None or packet.selected_note is not None or support_ids or packet.allowed_note_ids:
        raise ExplanationInputError("Unexplained packet must contain no accepted evidence.")
    if tuple(sorted(set(support_ids))) != decision.supporting_note_ids:
        raise ExplanationInputError("Packet supporting evidence does not match decision.")
    if any(note_id not in packet.allowed_note_ids for note_id in support_ids):
        raise ExplanationInputError("Supporting evidence is outside the packet allowlist.")
