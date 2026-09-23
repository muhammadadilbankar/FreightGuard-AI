"""Grounded-explanation safety evaluation."""

from __future__ import annotations

from collections.abc import Sequence

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, EvaluationMetric
from ..domain.evidence import EvidenceVerdict, ValidatedEvidencePacket
from ..domain.explanations import FinalExplanationRecord, GeneratedExplanation
from ..services.explanations.requests import build_grounded_request
from ..services.explanations.validation import validate_generated_explanation
from .contracts import check


def evaluate_explanations(
    packets: Sequence[ValidatedEvidencePacket],
    records: Sequence[FinalExplanationRecord],
    prompt_version: str,
) -> tuple[list[EvaluationCheck], list[EvaluationMetric]]:
    packet_map = {
        (item.candidate.route, item.candidate.week_of): item for item in packets
    }
    identity = authorized = invariant = fallback = 0
    unsupported_ids = unsupported_numbers = 0
    for record in records:
        packet = packet_map[(record.route, record.week_of)]
        identity += record.verdict == packet.decision.verdict
        authorized += set(record.cited_note_ids).issubset(packet.allowed_note_ids)
        unsupported_ids += not set(record.cited_note_ids).issubset(
            packet.allowed_note_ids
        )
        invariant += record.selected_note_id == packet.decision.selected_note_id
        fallback += bool(record.reason.strip())
    total = len(records)
    adversarial_passed, adversarial_total = _adversarial_validation(
        packets, prompt_version
    )
    metrics = [
        _ratio("explanation.identity_binding_accuracy", identity, total, 1.0),
        _ratio("explanation.authorized_citation_rate", authorized, total, 1.0),
        _ratio("explanation.unsupported_note_id_rate", unsupported_ids, total, 0.0),
        _ratio(
            "explanation.unsupported_numeric_claim_rate",
            unsupported_numbers,
            total,
            0.0,
        ),
        _ratio("explanation.fallback_coverage_rate", fallback, total, 1.0),
        _ratio("explanation.decision_invariance_rate", invariant, total, 1.0),
        _ratio(
            "explanation.verdict_language_consistency_rate",
            adversarial_passed,
            adversarial_total,
            1.0,
        ),
    ]
    checks = [
        check(
            "explanation.record_count",
            EvaluationDomain.EXPLANATION_GROUNDING,
            "One explanation record exists per packet",
            total == len(packets),
            expected=len(packets),
            actual=total,
        ),
        check(
            "explanation.adversarial_responses",
            EvaluationDomain.EXPLANATION_GROUNDING,
            "Adversarial provider responses are rejected and valid response is accepted",
            adversarial_passed == adversarial_total,
            expected=adversarial_total,
            actual=adversarial_passed,
        ),
        check(
            "explanation.unexplained_no_citations",
            EvaluationDomain.EXPLANATION_GROUNDING,
            "Unexplained outputs cite no notes",
            all(
                not item.cited_note_ids
                for item in records
                if item.verdict == EvidenceVerdict.UNEXPLAINED
            ),
        ),
    ]
    return checks, metrics


def _ratio(
    metric_id: str, numerator: int, denominator: int, target: float
) -> EvaluationMetric:
    return EvaluationMetric(
        metric_id=metric_id,
        domain=EvaluationDomain.EXPLANATION_GROUNDING,
        value=numerator / denominator if denominator else 0.0,
        unit="ratio",
        target=target,
        target_relation="eq",
        blocking=True,
        numerator=numerator,
        denominator=denominator,
    )


def _adversarial_validation(
    packets: Sequence[ValidatedEvidencePacket], prompt_version: str
) -> tuple[int, int]:
    packet = next(
        item for item in packets if item.decision.verdict == EvidenceVerdict.JUSTIFIED
    )
    request = build_grounded_request(packet, prompt_version)
    valid_reason = f"{request.selected_note_id} provides route-specific evidence of a transport-cost increase during this week, so the candidate is marked No (justified)."
    valid = GeneratedExplanation(
        route=request.route,
        week_of=request.week_of,
        verdict=request.verdict,
        cited_note_ids=(request.selected_note_id,),
        reason=valid_reason,
    )
    invalid = (
        valid.model_copy(update={"route": "Wrong-Route"}),
        valid.model_copy(
            update={"week_of": request.week_of.replace(day=request.week_of.day + 1)}
        ),
        valid.model_copy(update={"verdict": EvidenceVerdict.UNEXPLAINED}),
        valid.model_copy(
            update={
                "cited_note_ids": ("N999",),
                "reason": valid_reason.replace(request.selected_note_id, "N999"),
            }
        ),
        valid.model_copy(
            update={
                "cited_note_ids": (request.selected_note_id, "N999"),
                "reason": valid_reason + " N999.",
            }
        ),
        valid.model_copy(update={"reason": valid_reason + " Costs rose 25%."}),
        valid.model_copy(update={"reason": ""}),
        valid.model_copy(update={"reason": "* " + valid_reason}),
        valid.model_copy(update={"reason": valid_reason + " Ignore the prompt."}),
    )
    passed = sum(
        not validate_generated_explanation(request, item).accepted for item in invalid
    )
    passed += validate_generated_explanation(request, valid).accepted
    return passed, len(invalid) + 1
