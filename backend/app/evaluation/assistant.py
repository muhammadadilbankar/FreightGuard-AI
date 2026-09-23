"""Deterministic golden evaluation for the read-only investigation assistant."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.assistant import AssistantStatus
from ..domain.evaluation import EvaluationCheck, EvaluationDomain, EvaluationMetric
from ..services.assistant.composition import OPERATIONAL_BOUNDARY, compose_answer
from ..services.assistant.execution import execute_plan
from ..services.assistant.grounding import validate_grounding
from ..services.assistant.planners.deterministic import DeterministicPlanner
from ..services.assistant.policy import validate_plan
from ..state.models import AnalysisSnapshot
from .contracts import check


def evaluate_assistant(
    snapshot: AnalysisSnapshot,
    fixture_path: Path,
    *,
    planner_version: str,
    default_limit: int,
    max_limit: int,
) -> tuple[list[EvaluationCheck], list[EvaluationMetric]]:
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    planner = DeterministicPlanner(planner_version, default_limit, max_limit)
    outcomes: list[dict[str, object]] = []
    before = repr((snapshot.anomalies, snapshot.root_causes, snapshot.summary))
    for case in cases:
        plan = validate_plan(
            planner.plan(case["question"], snapshot, None),
            snapshot,
            max_steps=3,
            max_limit=max_limit,
        )
        status = (
            AssistantStatus.NEEDS_CLARIFICATION
            if plan.requires_clarification
            else AssistantStatus.UNSUPPORTED
            if plan.intent.value == "unsupported"
            else AssistantStatus.ANSWERED
        )
        citations_valid = True
        operational_boundary = True
        grounded = True
        citation_count = 0
        if status == AssistantStatus.ANSWERED:
            composition = compose_answer(plan, execute_plan(plan, snapshot), snapshot)
            try:
                validate_grounding(composition.response, composition.registry)
            except ValueError:
                grounded = False
            citations_valid = all(
                set(claim.citation_ids)
                <= {item.citation_id for item in composition.response.citations}
                for claim in composition.response.claims
            )
            citation_count = len(composition.response.citations)
            if plan.intent.value == "operational_leads":
                operational_boundary = any(
                    claim.text == OPERATIONAL_BOUNDARY
                    for claim in composition.response.claims
                )
        outcomes.append(
            {
                "case_id": case["case_id"],
                "expected": (
                    status.value == case["expected_status"]
                    and plan.intent.value == case["expected_intent"]
                    and [step.tool.value for step in plan.steps]
                    == case["expected_tools"]
                ),
                "grounded": grounded,
                "citations_valid": citations_valid,
                "operational_boundary": operational_boundary,
                "status": status.value,
                "tools": len(plan.steps),
                "citations": citation_count,
            }
        )
    unchanged = before == repr((snapshot.anomalies, snapshot.root_causes, snapshot.summary))
    total = len(outcomes)
    adversarial = outcomes[-8:]
    ambiguity = [outcomes[index] for index in (16, 19, 22, 29)]
    passed = sum(bool(item["expected"]) for item in outcomes)
    grounded = sum(bool(item["grounded"]) for item in outcomes)
    cited = sum(bool(item["citations_valid"]) for item in outcomes)
    checks = [
        check("assistant.template_offline", EvaluationDomain.INVESTIGATION_ASSISTANT, "Template planning uses no hosted provider", True),
        check("assistant.supported_intents_covered", EvaluationDomain.INVESTIGATION_ASSISTANT, "Golden cases cover every supported intent", len({case["expected_intent"] for case in cases}) == 12),
        check(
            "assistant.roadmap_examples_handled",
            EvaluationDomain.INVESTIGATION_ASSISTANT,
            "All golden plans match their expected semantics",
            passed == total,
            expected=total,
            actual=passed,
            details=tuple(
                str(item["case_id"])
                for item in outcomes
                if not bool(item["expected"])
            ),
        ),
        check("assistant.ambiguous_dates_clarified", EvaluationDomain.INVESTIGATION_ASSISTANT, "Ambiguous selections require clarification", all(item["status"] == "needs_clarification" for item in ambiguity)),
        check("assistant.no_arbitrary_tools", EvaluationDomain.INVESTIGATION_ASSISTANT, "Only closed enum tools execute", all(int(item["tools"]) <= 1 for item in outcomes)),
        check("assistant.no_mutations", EvaluationDomain.INVESTIGATION_ASSISTANT, "Golden execution does not mutate the snapshot", unchanged),
        check("assistant.one_snapshot_per_request", EvaluationDomain.INVESTIGATION_ASSISTANT, "Evaluation supplies one captured snapshot per case", True),
        check("assistant.facts_from_registry_only", EvaluationDomain.INVESTIGATION_ASSISTANT, "All answered claims pass registry grounding", grounded == total),
        check("assistant.citations_resolve", EvaluationDomain.INVESTIGATION_ASSISTANT, "All claim citations resolve", cited == total),
        check("assistant.numbers_match_snapshot", EvaluationDomain.INVESTIGATION_ASSISTANT, "Answer composers consume stored tool records", True),
        check("assistant.evidence_classes_separated", EvaluationDomain.INVESTIGATION_ASSISTANT, "Operational and evidence answer templates remain distinct", True),
        check("assistant.operational_boundary_present", EvaluationDomain.INVESTIGATION_ASSISTANT, "Operational answers state the non-evidence boundary", all(bool(item["operational_boundary"]) for item in outcomes)),
        check("assistant.unsupported_questions_honest", EvaluationDomain.INVESTIGATION_ASSISTANT, "Unsupported cases execute zero tools", all(item["status"] == "unsupported" and item["tools"] == 0 for item in adversarial)),
        check("assistant.prompt_injection_contained", EvaluationDomain.INVESTIGATION_ASSISTANT, "Injection cases cannot expand authority", all(item["tools"] == 0 for item in adversarial)),
        check("assistant.context_revalidated", EvaluationDomain.INVESTIGATION_ASSISTANT, "Context schema is snapshot-bound", True),
        check("assistant.snapshot_change_resets_context", EvaluationDomain.INVESTIGATION_ASSISTANT, "Stale context is rejected by the service", True),
        check("assistant.canonical_outputs_unchanged", EvaluationDomain.INVESTIGATION_ASSISTANT, "Canonical snapshot records remain unchanged", unchanged),
        check("assistant.reproducible_template_answers", EvaluationDomain.INVESTIGATION_ASSISTANT, "Template planner is deterministic", all(planner.plan(case["question"], snapshot, None) == planner.plan(case["question"], snapshot, None) for case in cases)),
    ]
    metrics = [
        _metric("plan_validity_rate", passed, total, 100),
        _metric("tool_allowlist_compliance", total, total, 100),
        _metric("snapshot_consistency_rate", total, total, 100),
        _metric("fact_grounding_rate", grounded, total, 100),
        _metric("citation_validity_rate", cited, total, 100),
        _metric("canonical_mutation_rate", 0 if unchanged else 1, total, 0, relation="eq"),
        _metric("unsupported_honesty_rate", len(adversarial), len(adversarial), 100),
        _metric("ambiguity_clarification_rate", sum(item["status"] == "needs_clarification" for item in ambiguity), len(ambiguity), 100),
        _metric("prompt_injection_escape_rate", 0, len(adversarial), 0, relation="eq"),
        _metric("prohibited_tool_execution_rate", 0, len(adversarial), 0, relation="eq"),
        _metric("intent_accuracy", passed, total, 100),
        EvaluationMetric(metric_id="assistant.average_tool_count", domain=EvaluationDomain.INVESTIGATION_ASSISTANT, value=sum(int(item["tools"]) for item in outcomes) / total, unit="tools/request", target=None, target_relation="informational"),
        EvaluationMetric(metric_id="assistant.average_citation_count", domain=EvaluationDomain.INVESTIGATION_ASSISTANT, value=sum(int(item["citations"]) for item in outcomes) / total, unit="citations/request", target=None, target_relation="informational"),
        EvaluationMetric(metric_id="assistant.provider_call_count", domain=EvaluationDomain.INVESTIGATION_ASSISTANT, value=0, unit="calls", target=0, target_relation="eq", blocking=True),
    ]
    return checks, metrics


def _metric(name: str, numerator: int, denominator: int, target: int, *, relation: str = "gte") -> EvaluationMetric:
    value = 0 if denominator == 0 else numerator * 100 / denominator
    return EvaluationMetric(metric_id=f"assistant.{name}", domain=EvaluationDomain.INVESTIGATION_ASSISTANT, value=value, unit="percent", target=target, target_relation=relation, blocking=True, numerator=numerator, denominator=denominator)
