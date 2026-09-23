"""Deterministic answer composition exclusively from stored tool results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote

from ...domain.assistant import (
    AssistantConversationContext,
    AssistantIntent,
    AssistantQueryPlan,
    AssistantResponseData,
    AssistantStatus,
    Citation,
    CitationType,
    FactRegistry,
    FactType,
    GroundedClaim,
    NavigationAction,
    ResultTable,
    TableColumn,
    ToolExecutionResult,
    VerifiedFact,
)
from ...domain.root_cause import RootCauseAnalysis
from ...state.models import AnalysisSnapshot, AnomalyView, TimelinePoint

OPERATIONAL_BOUNDARY = (
    "These are operational leads derived from shipment patterns. They are not "
    "accepted contextual evidence and do not change the canonical verdict."
)


@dataclass(frozen=True, slots=True)
class Composition:
    response: AssistantResponseData
    registry: FactRegistry
    result_count: int


class _Builder:
    def __init__(self, snapshot: AnalysisSnapshot) -> None:
        self.snapshot = snapshot
        self.citations: dict[str, Citation] = {}
        self.facts: list[VerifiedFact] = []
        self.claims: list[GroundedClaim] = []

    def anomaly_citation(self, item: AnomalyView) -> str:
        identifier = f"anomaly:{quote(item.candidate_key, safe='')}"
        self.citations.setdefault(
            identifier,
            Citation(
                citation_id=identifier,
                citation_type=CitationType.ANOMALY,
                label=f"{item.route} · {item.week_of.isoformat()}",
                route=item.route,
                week_of=item.week_of,
                candidate_key=item.candidate_key,
                snapshot_id=self.snapshot.snapshot_id,
                navigation_target=_anomaly_target(item),
            ),
        )
        return identifier

    def route_week_citation(self, route: str, point: TimelinePoint) -> str:
        identifier = f"route_week:{quote(route, safe='')}:{point.week_of.isoformat()}"
        self.citations.setdefault(
            identifier,
            Citation(
                citation_id=identifier,
                citation_type=CitationType.ROUTE_WEEK,
                label=f"{route} · {point.week_of.isoformat()}",
                route=route,
                week_of=point.week_of,
                snapshot_id=self.snapshot.snapshot_id,
                navigation_target=f"/?selectedRoute={quote(route)}",
            ),
        )
        return identifier

    def root_citation(self, item: RootCauseAnalysis) -> str:
        identifier = f"root_cause:{quote(item.candidate_key, safe='')}"
        self.citations.setdefault(
            identifier,
            Citation(
                citation_id=identifier,
                citation_type=CitationType.ROOT_CAUSE,
                label=f"Operational leads · {item.route} · {item.week_of.isoformat()}",
                route=item.route,
                week_of=item.week_of,
                candidate_key=item.candidate_key,
                snapshot_id=self.snapshot.snapshot_id,
                navigation_target=_anomaly_target_values(item.route, item.week_of.isoformat()),
            ),
        )
        return identifier

    def evidence_citations(self, anomaly: AnomalyView, note_id: str) -> tuple[str, str]:
        note = f"note:{quote(note_id, safe='')}"
        decision = f"evidence:{quote(anomaly.candidate_key, safe='')}"
        self.citations.setdefault(
            note,
            Citation(
                citation_id=note,
                citation_type=CitationType.CONTEXT_NOTE,
                label=f"Context note {note_id}",
                route=anomaly.route,
                week_of=anomaly.week_of,
                candidate_key=anomaly.candidate_key,
                note_id=note_id,
                snapshot_id=self.snapshot.snapshot_id,
                navigation_target=_anomaly_target(anomaly),
            ),
        )
        self.citations.setdefault(
            decision,
            Citation(
                citation_id=decision,
                citation_type=CitationType.EVIDENCE_DECISION,
                label=f"Evidence decision · {anomaly.route} · {anomaly.week_of.isoformat()}",
                route=anomaly.route,
                week_of=anomaly.week_of,
                candidate_key=anomaly.candidate_key,
                snapshot_id=self.snapshot.snapshot_id,
                navigation_target=_anomaly_target(anomaly),
            ),
        )
        return note, decision

    def simple_citation(self, kind: CitationType, label: str, suffix: str) -> str:
        identifier = f"{kind.value}:{quote(suffix, safe='')}"
        self.citations.setdefault(
            identifier,
            Citation(
                citation_id=identifier,
                citation_type=kind,
                label=label,
                check_id=suffix if kind == CitationType.EVALUATION_CHECK else None,
                snapshot_id=self.snapshot.snapshot_id,
            ),
        )
        return identifier

    def claim(self, text: str, citation_ids: tuple[str, ...], fact_type: FactType, value: object) -> None:
        index = len(self.claims) + 1
        fact_id = f"fact:{index:03d}"
        self.facts.append(
            VerifiedFact(
                fact_id=fact_id,
                fact_type=fact_type,
                canonical_value=value,
                display_text=text,
                citation_ids=citation_ids,
            )
        )
        self.claims.append(
            GroundedClaim(
                claim_id=f"claim:{index:03d}",
                text=text,
                citation_ids=citation_ids,
            )
        )


def compose_answer(
    plan: AssistantQueryPlan,
    results: tuple[ToolExecutionResult, ...],
    snapshot: AnalysisSnapshot,
) -> Composition:
    builder = _Builder(snapshot)
    table = None
    actions: tuple[NavigationAction, ...] = ()
    limitations: list[str] = []
    title = "FreightGuard investigation"
    count = sum(len(result.records) for result in results)

    if plan.intent == AssistantIntent.HELP:
        title = "Questions FreightGuard can answer"
        limitations.extend(
            (
                "Explain or list stored anomalies and route trends.",
                "Review accepted or rejected evidence and operational leads.",
                "Inspect evaluation status, run metrics, and snapshot summary.",
                "Predictions, web research, arbitrary computation, and mutations are not supported.",
            )
        )
    elif not results:
        limitations.append("The requested stored result is unavailable in this snapshot.")
    elif plan.intent in {AssistantIntent.LIST_ANOMALIES, AssistantIntent.RANK_ANOMALIES}:
        title = "Ranked anomalies" if plan.intent == AssistantIntent.RANK_ANOMALIES else "Anomaly results"
        anomalies = tuple(results[0].records)
        rows = []
        for item in anomalies:
            assert isinstance(item, AnomalyView)
            citation = builder.anomaly_citation(item)
            rows.append(
                (
                    item.route,
                    item.week_of.isoformat(),
                    item.verdict.value,
                    _number(item.cost_per_tonne_km),
                    _number(item.vs_own_history_pct),
                    _number(item.vs_similar_routes_pct),
                    citation,
                )
            )
        builder.claim(
            f"The snapshot query returned {len(anomalies)} of {results[0].total_count} matching anomalies.",
            tuple(builder.anomaly_citation(item) for item in anomalies),
            FactType.ANOMALY,
            len(anomalies),
        ) if anomalies else limitations.append("No anomalies match those filters.")
        table = ResultTable(
            caption=title,
            columns=tuple(
                TableColumn(key=key, label=label)
                for key, label in (
                    ("route", "Route"), ("week", "Week"), ("verdict", "Verdict"),
                    ("cost", "INR/t-km"), ("own", "Own %"), ("peer", "Peer %"),
                    ("citation", "Source"),
                )
            ),
            rows=tuple(rows),
            citation_column_index=6,
        )
        if results[0].truncated:
            limitations.append("Results were truncated at the configured limit.")
    elif plan.intent == AssistantIntent.EXPLAIN_ANOMALY:
        item = results[0].records[0]
        assert isinstance(item, AnomalyView)
        citation = builder.anomaly_citation(item)
        title = f"{item.route} · {item.week_of.isoformat()}"
        builder.claim(
            f"Observed cost was {_number(item.cost_per_tonne_km)} INR per tonne-km; own-history deviation was {_percent(item.vs_own_history_pct)} and peer deviation was {_percent(item.vs_similar_routes_pct)}.",
            (citation,), FactType.ANOMALY, item.cost_per_tonne_km,
        )
        builder.claim(
            f"The canonical verdict is {item.verdict.value.replace('_', ' ')} and the trigger is {item.trigger.replace('_', ' ')}.",
            (citation,), FactType.ANOMALY, item.verdict.value,
        )
        if item.matched_note_id:
            citations = builder.evidence_citations(item, item.matched_note_id)
            builder.claim(
                f"Context note {item.matched_note_id} is the selected accepted evidence.",
                citations, FactType.EVIDENCE, item.matched_note_id,
            )
        else:
            builder.claim(
                "No context note fully justified this anomaly.",
                (citation,), FactType.EVIDENCE, None,
            )
        limitations.append("This answer reports stored analysis and does not infer an external real-world cause.")
        actions = (_open_anomaly_action(item),)
    elif plan.intent == AssistantIntent.ROUTE_TREND:
        route = plan.steps[0].filters.route or "Route"
        title = f"{route} weekly timeline"
        rows = []
        for point in results[0].records:
            assert isinstance(point, TimelinePoint)
            citation = builder.route_week_citation(route, point)
            rows.append((point.week_of.isoformat(), _number(point.cost_per_tonne_km), _number(point.own_history_baseline), _number(point.peer_baseline), citation))
        if rows:
            builder.claim(
                f"The stored timeline contains {len(rows)} returned route-week points.",
                tuple(row[-1] for row in rows), FactType.ROUTE_WEEK, len(rows),
            )
        table = ResultTable(
            caption=title,
            columns=tuple(TableColumn(key=key, label=label) for key, label in (("week", "Week"), ("cost", "Cost"), ("own", "Own baseline"), ("peer", "Peer baseline"), ("citation", "Source"))),
            rows=tuple(rows), citation_column_index=4,
        )
        if results[0].truncated:
            limitations.append("Timeline results were truncated at the configured limit.")
    elif plan.intent == AssistantIntent.EVIDENCE_REVIEW:
        item = results[0].records[0]
        assert isinstance(item, AnomalyView)
        title = f"Evidence review · {item.route}"
        decision = builder.simple_citation(CitationType.EVIDENCE_DECISION, "Evidence decision", item.candidate_key)
        builder.claim(
            f"The canonical evidence verdict is {item.verdict.value.replace('_', ' ')}.",
            (decision,), FactType.EVIDENCE, item.verdict.value,
        )
        for evidence in item.evidence:
            note, decision_id = builder.evidence_citations(item, evidence.note_id)
            codes = ", ".join(evidence.rejection_codes) or "no rejection codes"
            builder.claim(
                f"Note {evidence.note_id} is {evidence.role}; Evidence Gate result: {codes}.",
                (note, decision_id), FactType.EVIDENCE, evidence.note_id,
            )
        actions = (_open_anomaly_action(item),)
    elif plan.intent == AssistantIntent.REJECTED_EVIDENCE:
        title = "Rejected evidence"
        rows = []
        for anomaly, evidence in results[0].records:
            note, decision = builder.evidence_citations(anomaly, evidence.note_id)
            rows.append((anomaly.route, anomaly.week_of.isoformat(), evidence.note_id, ", ".join(evidence.rejection_codes), note, decision))
        if rows:
            builder.claim(
                f"The query returned {len(rows)} rejected evidence records.",
                tuple(row[5] for row in rows), FactType.EVIDENCE, len(rows),
            )
        else:
            limitations.append("No rejected evidence matches that selection.")
        table = ResultTable(
            caption=title,
            columns=tuple(TableColumn(key=key, label=label) for key, label in (("route", "Route"), ("week", "Week"), ("note", "Note"), ("reasons", "Rejection reasons"), ("note_source", "Note source"), ("decision", "Decision"))),
            rows=tuple(rows), citation_column_index=5,
        )
        if results[0].truncated:
            limitations.append("Results were truncated at the configured limit.")
    elif plan.intent == AssistantIntent.OPERATIONAL_LEADS:
        item = results[0].records[0]
        assert isinstance(item, RootCauseAnalysis)
        citation = builder.root_citation(item)
        title = f"Operational leads · {item.route}"
        builder.claim(OPERATIONAL_BOUNDARY, (citation,), FactType.ROOT_CAUSE, item.canonical_verdict)
        for lens in (item.transporter, item.material):
            for lead in lens.leads:
                builder.claim(
                    f"{lens.lens.title()} lead: {lead.category} has a stored effect of {lead.effect:+.4f} INR/t-km ({lead.support_level.value} support).",
                    (citation,), FactType.ROOT_CAUSE, lead.effect,
                )
        builder.claim(
            f"Both lenses independently reconstruct the same target gap of {item.target_gap:+.4f} INR/t-km.",
            (citation,), FactType.ROOT_CAUSE, item.target_gap,
        )
        limitations.extend(item.caveats)
        actions = (
            NavigationAction(label="Open Operational Leads", action="open_root_cause", params={"route": item.route, "week_of": item.week_of.isoformat()}),
        )
    elif plan.intent == AssistantIntent.ANALYSIS_SUMMARY:
        summary = results[0].records[0]
        citation = builder.simple_citation(CitationType.ANALYSIS_SUMMARY, "Analysis summary", snapshot.snapshot_id)
        title = "Analysis snapshot summary"
        builder.claim(
            f"The snapshot contains {summary.weekly_record_count} weekly route records and {summary.candidate_count} anomalies.",
            (citation,), FactType.SUMMARY, summary.candidate_count,
        )
        builder.claim(
            f"Verdicts: {summary.justified_count} justified, {summary.partially_explained_count} partially explained, and {summary.unexplained_count} unexplained.",
            (citation,), FactType.SUMMARY, summary.unexplained_count,
        )
    elif plan.intent == AssistantIntent.EVALUATION_STATUS:
        report = results[0].records[0]
        citation = builder.simple_citation(CitationType.EVALUATION_CHECK, "Evaluation report", "overall")
        title = "Evaluation status"
        builder.claim(
            f"The stored formal evaluation status is {report.overall_status} across {report.run_count} reproducibility runs.",
            (citation,), FactType.EVALUATION, report.overall_status,
        )
        actions = (NavigationAction(label="Open evaluation diagnostics", action="open_evaluation", params={}),)
    elif plan.intent == AssistantIntent.RUN_METRICS:
        metrics = results[0].records[0]
        citation = builder.simple_citation(CitationType.RUN_METRICS, "Run metrics", snapshot.snapshot_id)
        title = "Run metrics"
        builder.claim(
            f"The stored run used {metrics.hosted_model_call_count} hosted model calls and took {metrics.total_duration_ms} ms.",
            (citation,), FactType.METRICS, metrics.hosted_model_call_count,
        )

    context = _context(plan, snapshot, results)
    response = AssistantResponseData(
        status=AssistantStatus.ANSWERED,
        title=title,
        claims=tuple(builder.claims),
        table=table,
        limitations=tuple(limitations),
        citations=tuple(builder.citations.values()),
        actions=actions,
        context=context,
    )
    return Composition(response=response, registry=FactRegistry(facts=tuple(builder.facts)), result_count=count)


def _context(plan: AssistantQueryPlan, snapshot: AnalysisSnapshot, results: tuple[ToolExecutionResult, ...]) -> AssistantConversationContext:
    anomalies = [item for result in results for item in result.records if isinstance(item, AnomalyView)]
    root_causes = [item for result in results for item in result.records if isinstance(item, RootCauseAnalysis)]
    route = plan.steps[0].filters.route if plan.steps else None
    week = plan.steps[0].filters.week_of if plan.steps else None
    keys = tuple(item.candidate_key for item in anomalies[:5])
    if root_causes:
        route, week, keys = root_causes[0].route, root_causes[0].week_of, (root_causes[0].candidate_key,)
    return AssistantConversationContext(
        snapshot_id=snapshot.snapshot_id,
        last_intent=plan.intent,
        route=route,
        week_of=week,
        week_from=plan.steps[0].filters.week_from if plan.steps else None,
        week_to=plan.steps[0].filters.week_to if plan.steps else None,
        candidate_keys=keys,
    )


def _open_anomaly_action(item: AnomalyView) -> NavigationAction:
    return NavigationAction(label="Open Cost Courtroom", action="open_anomaly", params={"route": item.route, "week_of": item.week_of.isoformat()})


def _anomaly_target(item: AnomalyView) -> str:
    return _anomaly_target_values(item.route, item.week_of.isoformat())


def _anomaly_target_values(route: str, week: str) -> str:
    return f"/?selectedRoute={quote(route)}&selectedWeek={quote(week)}"


def _number(value: float | Decimal | None) -> str:
    return "unavailable" if value is None else f"{float(value):.2f}"


def _percent(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:+.2f}%"
