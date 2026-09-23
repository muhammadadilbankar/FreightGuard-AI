"""Allowlisted read-only tools over one explicitly supplied snapshot."""

from __future__ import annotations

from ...application.snapshot_queries import get_anomaly, get_root_cause, get_timeline, list_anomalies
from ...domain.assistant import AssistantQueryPlan, AssistantSortField, AssistantTool, ToolExecutionResult
from ...state.models import AnalysisSnapshot


def execute_plan(
    plan: AssistantQueryPlan, snapshot: AnalysisSnapshot
) -> tuple[ToolExecutionResult, ...]:
    return tuple(_execute(step, snapshot) for step in plan.steps)


def _execute(step, snapshot: AnalysisSnapshot) -> ToolExecutionResult:
    filters = step.filters
    if step.tool == AssistantTool.GET_SUMMARY:
        records = (snapshot.summary,)
        total = 1
    elif step.tool == AssistantTool.LIST_ANOMALIES:
        sort_by = (step.sort_by or AssistantSortField.WEEK_OF).value
        records, total = list_anomalies(
            snapshot,
            route=filters.route,
            route_type=filters.route_type,
            verdict=filters.verdict,
            trigger=filters.trigger,
            week_from=filters.week_from,
            week_to=filters.week_to,
            min_own_deviation_pct=filters.min_own_deviation_pct,
            min_peer_deviation_pct=filters.min_peer_deviation_pct,
            sort_by=sort_by,
            sort_order=(step.sort_order.value if step.sort_order else "asc"),
            limit=step.limit,
            offset=0,
        )
    elif step.tool in {
        AssistantTool.GET_ANOMALY_DETAIL,
        AssistantTool.GET_EVIDENCE_REVIEW,
    }:
        assert filters.route is not None and filters.week_of is not None
        records = (get_anomaly(snapshot, filters.route, filters.week_of),)
        total = 1
    elif step.tool == AssistantTool.GET_ROUTE_TIMELINE:
        assert filters.route is not None
        all_points = tuple(
            point
            for point in get_timeline(snapshot, filters.route)
            if (filters.week_from is None or point.week_of >= filters.week_from)
            and (filters.week_to is None or point.week_of <= filters.week_to)
        )
        total = len(all_points)
        records = all_points[: step.limit]
    elif step.tool == AssistantTool.LIST_REJECTED_EVIDENCE:
        rows = []
        for anomaly in snapshot.anomalies:
            if filters.route is not None and anomaly.route != filters.route:
                continue
            if filters.week_of is not None and anomaly.week_of != filters.week_of:
                continue
            if filters.week_from is not None and anomaly.week_of < filters.week_from:
                continue
            if filters.week_to is not None and anomaly.week_of > filters.week_to:
                continue
            for evidence in anomaly.evidence:
                if evidence.role != "rejected":
                    continue
                if filters.note_id is not None and evidence.note_id != filters.note_id:
                    continue
                if filters.rejection_code is not None and filters.rejection_code not in evidence.rejection_codes:
                    continue
                rows.append((anomaly, evidence))
        rows.sort(key=lambda row: (row[0].week_of, row[0].route, row[1].note_id))
        total = len(rows)
        records = tuple(rows[: step.limit])
    elif step.tool == AssistantTool.GET_OPERATIONAL_LEADS:
        assert filters.route is not None and filters.week_of is not None
        records = (get_root_cause(snapshot, filters.route, filters.week_of),)
        total = 1
    elif step.tool == AssistantTool.GET_EVALUATION_STATUS:
        records = (snapshot.evaluation,) if snapshot.evaluation is not None else ()
        total = len(records)
    elif step.tool == AssistantTool.GET_RUN_METRICS:
        records = (snapshot.run_metrics,)
        total = 1
    else:  # pragma: no cover - enum exhaustiveness guard
        raise ValueError("Assistant tool is not implemented.")
    return ToolExecutionResult(
        tool=step.tool,
        records=tuple(records),
        total_count=total,
        truncated=total > len(records),
    )
