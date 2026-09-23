"""Closed assistant policy and untrusted-plan validation."""

from __future__ import annotations

from ...domain.assistant import AssistantIntent, AssistantQueryPlan, AssistantTool
from ...state.models import AnalysisSnapshot


def validate_plan(
    plan: AssistantQueryPlan,
    snapshot: AnalysisSnapshot,
    *,
    max_steps: int,
    max_limit: int,
) -> AssistantQueryPlan:
    allowed_tools = {
        AssistantIntent.EXPLAIN_ANOMALY: {AssistantTool.GET_ANOMALY_DETAIL},
        AssistantIntent.LIST_ANOMALIES: {AssistantTool.LIST_ANOMALIES},
        AssistantIntent.RANK_ANOMALIES: {AssistantTool.LIST_ANOMALIES},
        AssistantIntent.ROUTE_TREND: {AssistantTool.GET_ROUTE_TIMELINE},
        AssistantIntent.EVIDENCE_REVIEW: {AssistantTool.GET_EVIDENCE_REVIEW},
        AssistantIntent.REJECTED_EVIDENCE: {AssistantTool.LIST_REJECTED_EVIDENCE},
        AssistantIntent.OPERATIONAL_LEADS: {AssistantTool.GET_OPERATIONAL_LEADS},
        AssistantIntent.ANALYSIS_SUMMARY: {AssistantTool.GET_SUMMARY},
        AssistantIntent.EVALUATION_STATUS: {AssistantTool.GET_EVALUATION_STATUS},
        AssistantIntent.RUN_METRICS: {AssistantTool.GET_RUN_METRICS},
        AssistantIntent.HELP: set(),
        AssistantIntent.UNSUPPORTED: set(),
    }
    if len(plan.steps) > max_steps:
        raise ValueError("Assistant plan exceeds the step limit.")
    routes = set(snapshot.route_timelines)
    candidates = {(item.route, item.week_of) for item in snapshot.anomalies}
    for step in plan.steps:
        if step.tool not in allowed_tools[plan.intent]:
            raise ValueError("Assistant intent cannot invoke that tool.")
        if step.limit > max_limit:
            raise ValueError("Assistant plan exceeds the result limit.")
        filters = step.filters
        if filters.route is not None and filters.route not in routes:
            raise ValueError("Assistant plan references an unknown route.")
        if filters.week_of is not None and filters.route is not None:
            if (filters.route, filters.week_of) not in candidates and plan.intent not in {
                AssistantIntent.ROUTE_TREND,
                AssistantIntent.LIST_ANOMALIES,
            }:
                raise ValueError("Assistant plan references an unknown candidate.")
    return plan


UNSAFE_TERMS = (
    "clear this anomaly",
    "mark this justified",
    "change the verdict",
    "change the threshold",
    "replace the matched note",
    "delete this evidence",
    "ignore the evidence gate",
    "rewrite final",
    "api key",
    "environment variable",
    "system prompt",
    "developer prompt",
    "read a local file",
    "read file",
    "run sql",
    "write sql",
    "run python",
    "run shell",
    "execute code",
    "fetch url",
    "browse the web",
    "search the web",
)


def unsafe_reason(question: str) -> str | None:
    lowered = question.casefold()
    if any(term in lowered for term in UNSAFE_TERMS):
        return (
            "FreightGuard Assistant is read-only and cannot mutate analysis, expose "
            "secrets, access files or the web, or execute code."
        )
    return None
