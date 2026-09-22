"""Strict deterministic post-generation grounding validation."""

import re
import unicodedata

from ...domain.evidence import EvidenceVerdict
from ...domain.explanations import (
    ExplanationFailureCode,
    ExplanationValidationResult,
    GeneratedExplanation,
    GroundedExplanationRequest,
)

_NOTE_ID = re.compile(r"\bN\d+\b", re.IGNORECASE)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER = re.compile(r"(?<![A-Za-z])(?:INR\s*)?[+-]?\d+(?:\.\d+)?(?:\s*(?:%|percent|km|kilomet(?:er|re)s?))?", re.IGNORECASE)
_MARKDOWN = re.compile(r"(^|\s)(?:#{1,6}\s|[-*+]\s|```|\|[^\n]*\|)")
_PARTIAL_CONFLICTS = (
    "fully explained", "fully justified", "candidate cleared",
    "no longer flagged", "normal cost",
)
_JUSTIFIED_CONFLICTS = ("no evidence", "remains unexplained", "remains flagged")
_INTERNAL_TERMS = (
    "llm", "embedding score", "rrf", "prompt", "system message",
    "evidence gate failed", "retrieval top-k",
)


def validate_generated_explanation(
    request: GroundedExplanationRequest,
    generated: GeneratedExplanation,
    *,
    minimum_length: int = 40,
    maximum_length: int = 400,
) -> ExplanationValidationResult:
    codes: set[ExplanationFailureCode] = set()
    if generated.route != request.route or generated.week_of != request.week_of:
        codes.add(ExplanationFailureCode.IDENTITY_MISMATCH)
    if generated.verdict != request.verdict:
        codes.add(ExplanationFailureCode.VERDICT_MISMATCH)

    cited = generated.cited_note_ids
    if len(set(cited)) != len(cited):
        codes.add(ExplanationFailureCode.INVALID_CITATION_SET)
    allowed = set(request.allowed_note_ids)
    prose_ids = {item.upper() for item in _NOTE_ID.findall(generated.reason)}
    if any(item not in allowed for item in cited) or any(item not in allowed for item in prose_ids):
        codes.add(ExplanationFailureCode.UNAUTHORIZED_NOTE_ID)
    if request.verdict == EvidenceVerdict.JUSTIFIED:
        expected = (request.selected_note_id,) if request.selected_note_id else ()
        if cited != expected or not request.selected_note_id or request.selected_note_id not in prose_ids:
            codes.add(ExplanationFailureCode.REQUIRED_NOTE_ID_MISSING)
    elif request.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED:
        support = {item.note_id for item in request.evidence if item.role == "supporting"}
        if not cited or any(item not in support for item in cited) or not (prose_ids & set(cited)):
            codes.add(ExplanationFailureCode.INVALID_CITATION_SET)
    elif cited or prose_ids:
        codes.add(ExplanationFailureCode.INVALID_CITATION_SET)

    reason = generated.reason.strip()
    lowered = reason.casefold()
    if not reason:
        codes.add(ExplanationFailureCode.REASON_EMPTY)
    if len(reason) < minimum_length or len(reason) > maximum_length:
        codes.add(ExplanationFailureCode.REASON_LENGTH_VIOLATION)
    if (
        reason != generated.reason
        or "\n" in reason
        or "\r" in reason
        or _MARKDOWN.search(reason)
        or any(unicodedata.category(char) == "Cc" for char in reason)
        or reason.startswith(("{", "["))
    ):
        codes.add(ExplanationFailureCode.REASON_FORMAT_VIOLATION)
    conflicts = (
        _PARTIAL_CONFLICTS
        if request.verdict == EvidenceVerdict.PARTIALLY_EXPLAINED
        else _JUSTIFIED_CONFLICTS
        if request.verdict == EvidenceVerdict.JUSTIFIED
        else ()
    )
    if any(phrase in lowered for phrase in conflicts) or "proved caus" in lowered:
        codes.add(ExplanationFailureCode.VERDICT_LANGUAGE_CONFLICT)
    if any(term in lowered for term in _INTERNAL_TERMS):
        codes.add(ExplanationFailureCode.INTERNAL_LANGUAGE_LEAKAGE)
    if _unsupported_numbers(request, reason):
        codes.add(ExplanationFailureCode.UNSUPPORTED_NUMERIC_CLAIM)

    failures = tuple(sorted(codes, key=lambda item: item.value))
    return ExplanationValidationResult(
        accepted=not failures,
        reason=reason if not failures else None,
        cited_note_ids=cited if not failures else (),
        failure_codes=failures,
    )


def _unsupported_numbers(request: GroundedExplanationRequest, reason: str) -> bool:
    def numeric_claims(value: str) -> set[str]:
        without_ids = _NOTE_ID.sub("", value)
        without_dates = _DATE.sub("", without_ids)
        return {_normalize_number(item.group(0)) for item in _NUMBER.finditer(without_dates)}

    approved_dates = {
        request.week_of.isoformat(),
        request.week_end.isoformat(),
        *(item.effective_from.isoformat() for item in request.evidence),
        *(item.effective_to.isoformat() for item in request.evidence if item.effective_to),
    }
    if any(item not in approved_dates for item in _DATE.findall(reason)):
        return True
    approved_text = " ".join(
        filter(
            None,
            (
                request.cost_per_tonne_km_display,
                request.vs_own_history_display,
                request.vs_similar_routes_display,
                *(item.magnitude_text for item in request.evidence),
            ),
        )
    )
    approved = numeric_claims(approved_text)
    return not numeric_claims(reason).issubset(approved)


def _normalize_number(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold().replace("percent", "%").lstrip("+")
