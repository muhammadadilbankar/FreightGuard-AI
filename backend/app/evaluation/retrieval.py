"""Hybrid and structured-recall metrics."""

from __future__ import annotations

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, EvaluationMetric
from ..domain.evidence import EvidenceReviewResult
from ..services.evidence.metrics import evaluate_retrieval as discovery_metrics
from .contracts import check


def evaluate_retrieval(
    result: EvidenceReviewResult,
) -> tuple[list[EvaluationCheck], list[EvaluationMetric]]:
    relevance = {}
    for packet in result.packets:
        key = (packet.candidate.route, packet.candidate.week_of)
        if packet.decision.selected_note_id:
            relevance[key] = frozenset({packet.decision.selected_note_id})
        elif packet.decision.supporting_note_ids:
            relevance[key] = frozenset(packet.decision.supporting_note_ids)
    hybrid = discovery_metrics(result.fused_rankings, relevance)
    assessed = {
        (audit.route, audit.week_of): {item.note_id for item in audit.assessments}
        for audit in result.audits
    }
    covered = sum(
        bool(relevant & assessed.get(key, set())) for key, relevant in relevance.items()
    )
    structured_union = covered / len(relevance) if relevance else 0.0
    finite = all(
        hit.fused_score is None or abs(hit.fused_score) < float("inf")
        for hits in result.fused_rankings.values()
        for hit in hits
    )
    metrics = [
        EvaluationMetric(
            metric_id="retrieval.hybrid_recall_at_1",
            domain=EvaluationDomain.RETRIEVAL_QUALITY,
            value=hybrid.recall_at_1,
            unit="ratio",
            target=1.0,
            target_relation="informational",
        ),
        EvaluationMetric(
            metric_id="retrieval.hybrid_recall_at_3",
            domain=EvaluationDomain.RETRIEVAL_QUALITY,
            value=hybrid.recall_at_3,
            unit="ratio",
            target=1.0,
            target_relation="informational",
        ),
        EvaluationMetric(
            metric_id="retrieval.hybrid_recall_at_5",
            domain=EvaluationDomain.RETRIEVAL_QUALITY,
            value=hybrid.recall_at_5,
            unit="ratio",
            target=1.0,
            target_relation="informational",
        ),
        EvaluationMetric(
            metric_id="retrieval.hybrid_mean_reciprocal_rank",
            domain=EvaluationDomain.RETRIEVAL_QUALITY,
            value=hybrid.mean_reciprocal_rank,
            unit="ratio",
            target=None,
            target_relation="informational",
        ),
        EvaluationMetric(
            metric_id="retrieval.structured_union_recall",
            domain=EvaluationDomain.RETRIEVAL_QUALITY,
            value=structured_union,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=covered,
            denominator=len(relevance),
        ),
    ]
    checks = [
        check(
            "retrieval.labelled_set_nonempty",
            EvaluationDomain.RETRIEVAL_QUALITY,
            "Labelled supplied discovery set is non-empty",
            bool(relevance),
            expected=15,
            actual=len(relevance),
        ),
        check(
            "retrieval.scores_finite",
            EvaluationDomain.RETRIEVAL_QUALITY,
            "Hybrid retrieval scores are finite",
            finite,
        ),
        check(
            "retrieval.every_accepted_reaches_gate",
            EvaluationDomain.RETRIEVAL_QUALITY,
            "Every selected/supporting supplied note reaches the Evidence Gate",
            structured_union == 1.0,
            expected=1.0,
            actual=structured_union,
        ),
    ]
    return checks, metrics
