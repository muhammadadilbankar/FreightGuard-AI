"""Adversarial grounding validator coverage."""

from datetime import date

import pytest

from backend.app.domain.evidence import EvidenceVerdict
from backend.app.domain.explanations import ExplanationFailureCode, GeneratedExplanation
from backend.app.services.explanations import build_grounded_request, validate_generated_explanation


def generated(request, reason, *, cited=None, route=None, week=None, verdict=None):
    return GeneratedExplanation(
        route=route or request.route,
        week_of=week or request.week_of,
        verdict=verdict or request.verdict,
        cited_note_ids=request.allowed_note_ids if cited is None else cited,
        reason=reason,
    )


def test_valid_grounded_justified_response(justified_packet) -> None:
    request = build_grounded_request(justified_packet, "fg-explanation-v1")
    result = validate_generated_explanation(
        request,
        generated(request, "N100 documents a route-specific transport-cost increase for this week."),
    )
    assert result.accepted


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"route": "B-A"}, ExplanationFailureCode.IDENTITY_MISMATCH),
        ({"week": date(2025, 1, 13)}, ExplanationFailureCode.IDENTITY_MISMATCH),
        ({"verdict": EvidenceVerdict.UNEXPLAINED}, ExplanationFailureCode.VERDICT_MISMATCH),
        ({"cited": ("N999",)}, ExplanationFailureCode.UNAUTHORIZED_NOTE_ID),
    ],
)
def test_identity_verdict_and_citation_violations(justified_packet, overrides, code) -> None:
    request = build_grounded_request(justified_packet, "fg-explanation-v1")
    response = generated(
        request,
        "N100 documents a route-specific transport-cost increase for this week.",
        **overrides,
    )
    assert code in validate_generated_explanation(request, response).failure_codes


@pytest.mark.parametrize(
    "reason",
    [
        "N100 shows transport costs increased 99% during this week.",
        "N100 shows an INR 500 increase during this week.",
        "N100 documents an increase beginning 2026-09-01.",
    ],
)
def test_invented_numeric_claims_are_rejected(justified_packet, reason) -> None:
    request = build_grounded_request(justified_packet, "fg-explanation-v1")
    result = validate_generated_explanation(request, generated(request, reason))
    assert ExplanationFailureCode.UNSUPPORTED_NUMERIC_CLAIM in result.failure_codes


@pytest.mark.parametrize(
    ("reason", "code"),
    [
        ("N100 documents an increase.\n- Cleared.", ExplanationFailureCode.REASON_FORMAT_VIOLATION),
        ("N100 was accepted by the LLM prompt and embedding score.", ExplanationFailureCode.INTERNAL_LANGUAGE_LEAKAGE),
        ("N100", ExplanationFailureCode.REASON_LENGTH_VIOLATION),
    ],
)
def test_format_and_internal_language_are_rejected(justified_packet, reason, code) -> None:
    request = build_grounded_request(justified_packet, "fg-explanation-v1")
    assert code in validate_generated_explanation(request, generated(request, reason)).failure_codes


def test_partial_cannot_claim_clearance(partial_packet) -> None:
    request = build_grounded_request(partial_packet, "fg-explanation-v1")
    response = generated(
        request,
        "N200 fully justified the increase and the candidate is cleared from review.",
    )
    result = validate_generated_explanation(request, response)
    assert ExplanationFailureCode.VERDICT_LANGUAGE_CONFLICT in result.failure_codes
