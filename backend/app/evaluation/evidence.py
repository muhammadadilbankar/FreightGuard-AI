"""Supplied and adversarial Evidence Gate metrics."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..domain.evaluation import EvaluationCheck, EvaluationDomain, EvaluationMetric
from ..domain.evidence import EvidenceLevel, EvidenceReviewResult, EvidenceVerdict
from .contracts import check


def evaluate_evidence_gate(
    result: EvidenceReviewResult, fixture_path: Path
) -> tuple[list[EvaluationCheck], list[EvaluationMetric]]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected = {(item["route"], item["week_of"]): item for item in fixture}
    actual = {
        (packet.decision.route, packet.decision.week_of.isoformat()): packet.decision
        for packet in result.packets
    }
    correct = sum(
        key in actual
        and actual[key].verdict.value == item["verdict"]
        and actual[key].selected_note_id == item["selected_note_id"]
        and list(actual[key].supporting_note_ids) == item["supporting_note_ids"]
        for key, item in expected.items()
    )
    counts = Counter(item.verdict for item in actual.values())
    expected_not_justified = sum(item["verdict"] != "justified" for item in fixture)
    false_clearances = sum(
        item["verdict"] != "justified"
        and actual[key].verdict == EvidenceVerdict.JUSTIFIED
        for key, item in expected.items()
        if key in actual
    )
    unsafe_ids = {"N004", "N005", "N006", "N007", "N008", "N009", "N010"}
    unsafe_total = unsafe_accepted = 0
    for audit in result.audits:
        for assessment in audit.assessments:
            if assessment.note_id in unsafe_ids:
                unsafe_total += 1
                unsafe_accepted += assessment.evidence_level != EvidenceLevel.REJECTED
    accuracy = correct / len(fixture)
    false_rate = (
        false_clearances / expected_not_justified if expected_not_justified else 0.0
    )
    unsafe_rate = unsafe_accepted / unsafe_total if unsafe_total else 0.0
    predicted_full = sum(
        item.verdict == EvidenceVerdict.JUSTIFIED for item in actual.values()
    )
    expected_full = sum(item["verdict"] == "justified" for item in fixture)
    correct_full = sum(
        item["verdict"] == "justified"
        and key in actual
        and actual[key].verdict == EvidenceVerdict.JUSTIFIED
        for key, item in expected.items()
    )
    predicted_accepted = sum(
        item.verdict != EvidenceVerdict.UNEXPLAINED for item in actual.values()
    )
    expected_accepted = sum(item["verdict"] != "unexplained" for item in fixture)
    correct_accepted = sum(
        item["verdict"] != "unexplained"
        and key in actual
        and actual[key].verdict != EvidenceVerdict.UNEXPLAINED
        for key, item in expected.items()
    )
    metrics = [
        EvaluationMetric(
            metric_id="evidence.verdict_accuracy",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=accuracy,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct,
            denominator=len(fixture),
        ),
        EvaluationMetric(
            metric_id="evidence.false_clearance_rate",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=false_rate,
            unit="ratio",
            target=0.0,
            target_relation="eq",
            blocking=True,
            numerator=false_clearances,
            denominator=expected_not_justified,
        ),
        EvaluationMetric(
            metric_id="evidence.unsafe_evidence_acceptance_rate",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=unsafe_rate,
            unit="ratio",
            target=0.0,
            target_relation="eq",
            blocking=True,
            numerator=unsafe_accepted,
            denominator=unsafe_total,
        ),
        EvaluationMetric(
            metric_id="evidence.selected_note_accuracy",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=accuracy,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct,
            denominator=len(fixture),
        ),
        EvaluationMetric(
            metric_id="evidence.full_evidence_precision",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=correct_full / predicted_full if predicted_full else 0.0,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct_full,
            denominator=predicted_full,
        ),
        EvaluationMetric(
            metric_id="evidence.full_evidence_recall",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=correct_full / expected_full if expected_full else 0.0,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct_full,
            denominator=expected_full,
        ),
        EvaluationMetric(
            metric_id="evidence.accepted_evidence_precision",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=correct_accepted / predicted_accepted if predicted_accepted else 0.0,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct_accepted,
            denominator=predicted_accepted,
        ),
        EvaluationMetric(
            metric_id="evidence.accepted_evidence_recall",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=correct_accepted / expected_accepted if expected_accepted else 0.0,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=correct_accepted,
            denominator=expected_accepted,
        ),
        EvaluationMetric(
            metric_id="evidence.rejected_evidence_accuracy",
            domain=EvaluationDomain.EVIDENCE_GATE,
            value=(unsafe_total - unsafe_accepted) / unsafe_total
            if unsafe_total
            else 1.0,
            unit="ratio",
            target=1.0,
            target_relation="eq",
            blocking=True,
            numerator=unsafe_total - unsafe_accepted,
            denominator=unsafe_total,
        ),
    ]
    checks = [
        check(
            "evidence.fixture_mapping",
            EvaluationDomain.EVIDENCE_GATE,
            "Full supplied verdict and evidence mapping matches fixture",
            correct == len(fixture),
            expected=len(fixture),
            actual=correct,
        ),
        check(
            "evidence.distribution",
            EvaluationDomain.EVIDENCE_GATE,
            "Supplied verdict distribution remains 3/12/4",
            counts
            == {
                EvidenceVerdict.JUSTIFIED: 3,
                EvidenceVerdict.PARTIALLY_EXPLAINED: 12,
                EvidenceVerdict.UNEXPLAINED: 4,
            },
            expected={"justified": 3, "partially_explained": 12, "unexplained": 4},
            actual={key.value: value for key, value in counts.items()},
        ),
        check(
            "evidence.adversarial_fixture",
            EvaluationDomain.EVIDENCE_GATE,
            "Mandatory adversarial case catalogue is present",
            _adversarial_fixture_complete(
                fixture_path.parent / "adversarial_evidence_cases.json"
            ),
            expected=20,
            actual=_adversarial_fixture_count(
                fixture_path.parent / "adversarial_evidence_cases.json"
            ),
        ),
    ]
    return checks, metrics


def _adversarial_fixture_count(path: Path) -> int:
    return len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0


def _adversarial_fixture_complete(path: Path) -> bool:
    required = {
        "valid_exact_route_and_week",
        "wrong_route",
        "reverse_direction_route",
        "wrong_date_before_start",
        "wrong_date_after_end",
        "one_day_overlap",
        "outside_dataset_scope",
        "negated_cost_impact",
        "explicit_no_rate_change",
        "normal_operations",
        "cost_impact_not_stated",
        "no_evidence",
        "global_own_only_full",
        "global_peer_partial",
        "high_similarity_but_invalid",
        "low_similarity_structured_recall_valid",
        "multiple_full_deterministic_selection",
        "multiple_partial_no_full_combination",
        "full_and_partial_full_wins",
        "independent_no_impact_note_does_not_cancel_valid_note",
    }
    if not path.exists():
        return False
    return {
        item["case_id"] for item in json.loads(path.read_text(encoding="utf-8"))
    } == required
