"""Deterministic verdict-aware explanation templates."""

from ...domain.evidence import EvidenceVerdict
from ...domain.explanations import GroundedExplanationRequest
from .errors import ExplanationInputError


def render_fallback_explanation(request: GroundedExplanationRequest) -> str:
    if request.verdict == EvidenceVerdict.JUSTIFIED:
        if request.selected_note_id is None:
            raise ExplanationInputError("Justified fallback requires selected evidence.")
        return (
            f"{request.selected_note_id} provides route-specific evidence of a "
            "transport-cost increase during this week, so the candidate is marked "
            "No (justified)."
        )
    if request.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED:
        if not request.allowed_note_ids:
            raise ExplanationInputError("Partial fallback requires supporting evidence.")
        return (
            f"{request.allowed_note_ids[0]} may explain part of the own-history rise, "
            "but its all-routes scope does not explain this route's premium over "
            "same-week peers; the candidate remains flagged."
        )
    return (
        "No validated context note explains the increase for this route and week, "
        "so the candidate remains flagged for review."
    )
