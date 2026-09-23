"""Ordered deterministic parser for the supported investigation language."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ....domain.assistant import (
    AnswerTemplate,
    AssistantConversationContext,
    AssistantIntent,
    AssistantQueryPlan,
    AssistantSortField,
    AssistantTool,
    ClarificationOption,
    ClarificationRequest,
    QueryFilters,
    QueryStep,
    SortDirection,
)
from ....domain.evidence import EvidenceVerdict
from ....state.models import AnalysisSnapshot, AnomalyView
from ..dates import DateResolution, resolve_dates
from ..entities import resolve_route
from ..normalization import normalize_text
from ..policy import unsafe_reason


@dataclass(frozen=True, slots=True)
class DeterministicPlanner:
    planner_version: str
    default_limit: int
    max_limit: int

    def plan(
        self,
        question: str,
        snapshot: AnalysisSnapshot,
        context: AssistantConversationContext | None,
    ) -> AssistantQueryPlan:
        normalized = normalize_text(question)
        unsafe = unsafe_reason(normalized)
        if unsafe:
            return self._unsupported(unsafe)
        if _contains_any(normalized, ("predict", "forecast", "real-world cause", "who should we fire", "recommend a transporter")):
            return self._unsupported(
                "That request requires prediction, external knowledge, or a business recommendation outside the stored snapshot."
            )
        if _contains_any(normalized, ("help", "what can you", "supported questions")):
            return self._plan(AssistantIntent.HELP, AnswerTemplate.HELP)

        route, route_suggestions = resolve_route(normalized, snapshot)
        if context and context.route and route and route != context.route:
            return self._clarify(
                AssistantIntent.UNSUPPORTED,
                "The question and current context name different routes. Which route should I use?",
                tuple(
                    ClarificationOption(option_id=value, label=value, value=value)
                    for value in (context.route, route)
                ),
            )
        if route is None and context and _contains_any(normalized, ("this anomaly", "this route", "here", "it")):
            route = context.route

        dates = resolve_dates(
            normalized,
            tuple(point.week_of for points in snapshot.route_timelines.values() for point in points),
        )
        if dates.clarification:
            inferred = self._intent(normalized, context)
            return self._clarify(
                inferred,
                dates.clarification.question,
                dates.clarification.options,
            )
        if dates.invalid:
            return self._unsupported(dates.invalid)

        intent = self._intent(normalized, context)
        if intent == AssistantIntent.ANALYSIS_SUMMARY:
            return self._single(intent, AssistantTool.GET_SUMMARY, AnswerTemplate.SUMMARY)
        if intent == AssistantIntent.EVALUATION_STATUS:
            return self._single(intent, AssistantTool.GET_EVALUATION_STATUS, AnswerTemplate.STATUS)
        if intent == AssistantIntent.RUN_METRICS:
            return self._single(intent, AssistantTool.GET_RUN_METRICS, AnswerTemplate.STATUS)
        if intent == AssistantIntent.ROUTE_TREND:
            if route is None:
                return self._route_clarification(intent, route_suggestions, snapshot)
            return self._single(
                intent,
                AssistantTool.GET_ROUTE_TIMELINE,
                AnswerTemplate.ROUTE_TREND,
                QueryFilters(route=route, week_from=dates.week_from, week_to=dates.week_to),
            )
        if intent in {
            AssistantIntent.EXPLAIN_ANOMALY,
            AssistantIntent.EVIDENCE_REVIEW,
            AssistantIntent.OPERATIONAL_LEADS,
        }:
            candidate_or_plan = self._resolve_candidate(
                intent, route, dates, snapshot, context
            )
            if isinstance(candidate_or_plan, AssistantQueryPlan):
                return candidate_or_plan
            candidate = candidate_or_plan
            tool = {
                AssistantIntent.EXPLAIN_ANOMALY: AssistantTool.GET_ANOMALY_DETAIL,
                AssistantIntent.EVIDENCE_REVIEW: AssistantTool.GET_EVIDENCE_REVIEW,
                AssistantIntent.OPERATIONAL_LEADS: AssistantTool.GET_OPERATIONAL_LEADS,
            }[intent]
            template = {
                AssistantIntent.EXPLAIN_ANOMALY: AnswerTemplate.ANOMALY,
                AssistantIntent.EVIDENCE_REVIEW: AnswerTemplate.EVIDENCE,
                AssistantIntent.OPERATIONAL_LEADS: AnswerTemplate.OPERATIONAL,
            }[intent]
            return self._single(
                intent,
                tool,
                template,
                QueryFilters(route=candidate.route, week_of=candidate.week_of),
                limit=1,
            )
        if intent == AssistantIntent.REJECTED_EVIDENCE:
            filters = QueryFilters(
                route=route,
                week_of=dates.week_of,
                week_from=dates.week_from,
                week_to=dates.week_to,
                rejection_code=_rejection_code(normalized),
            )
            return self._single(
                intent,
                AssistantTool.LIST_REJECTED_EVIDENCE,
                AnswerTemplate.REJECTED_EVIDENCE,
                filters,
            )
        if intent in {AssistantIntent.LIST_ANOMALIES, AssistantIntent.RANK_ANOMALIES}:
            verdict = _verdict(normalized)
            trigger = _trigger(normalized)
            route_type = next(
                (value for value in ("Short", "Medium", "Long") if value.casefold() in normalized),
                None,
            )
            filters = QueryFilters(
                route=route,
                route_type=route_type,
                verdict=verdict,
                trigger=trigger,
                week_from=dates.week_from,
                week_to=dates.week_to,
            )
            limit = min(_limit(normalized) or self.default_limit, self.max_limit)
            sort = _sort_field(normalized)
            if intent == AssistantIntent.RANK_ANOMALIES and sort is None:
                return self._clarify(
                    intent,
                    "Which supported metric should define the ranking?",
                    tuple(
                        ClarificationOption(
                            option_id=value.value,
                            label=label,
                            value=label,
                        )
                        for value, label in (
                            (AssistantSortField.VS_OWN_HISTORY_PCT, "Own-history deviation"),
                            (AssistantSortField.VS_SIMILAR_ROUTES_PCT, "Peer deviation"),
                            (AssistantSortField.COST_PER_TONNE_KM, "Cost per tonne-km"),
                        )
                    ),
                )
            return AssistantQueryPlan(
                planner_version=self.planner_version,
                intent=intent,
                steps=(
                    QueryStep(
                        tool=AssistantTool.LIST_ANOMALIES,
                        filters=filters,
                        sort_by=sort or AssistantSortField.WEEK_OF,
                        sort_order=SortDirection.DESC if intent == AssistantIntent.RANK_ANOMALIES else SortDirection.ASC,
                        limit=limit,
                    ),
                ),
                answer_template=AnswerTemplate.ANOMALY_LIST,
            )
        return self._unsupported(
            "I could not map that question to a supported snapshot investigation."
        )

    def _intent(
        self, text: str, context: AssistantConversationContext | None
    ) -> AssistantIntent:
        if _contains_any(text, ("model call", "hosted call", "tokens", "run metrics", "latency")):
            return AssistantIntent.RUN_METRICS
        if _contains_any(text, ("evaluation", "eval pass", "checks pass")):
            return AssistantIntent.EVALUATION_STATUS
        if _contains_any(text, ("how many anomalies", "analysis summary", "snapshot summary", "how many candidates")):
            return AssistantIntent.ANALYSIS_SUMMARY
        if _contains_any(text, ("operational lead", "operational factor", "transporter mix", "average load", "material mix")):
            return AssistantIntent.OPERATIONAL_LEADS
        if _contains_any(text, ("rejected", "failed the evidence gate", "wrong-route", "wrong route")):
            return AssistantIntent.REJECTED_EVIDENCE
        if _contains_any(text, ("which note", "what evidence", "evidence supported", "evidence review")):
            return AssistantIntent.EVIDENCE_REVIEW
        if _contains_any(text, ("trend", "weekly cost", "costs change", "cost versus", "timeline")):
            return AssistantIntent.ROUTE_TREND
        if _contains_any(text, ("largest", "highest", "top ", "rank")):
            return AssistantIntent.RANK_ANOMALIES
        if text.startswith("explain ") or _contains_any(
            text, ("why did", "why was", "became expensive", "flagged")
        ):
            return AssistantIntent.EXPLAIN_ANOMALY
        if _contains_any(text, ("show", "list", "which anomalies", "anomalies")):
            return AssistantIntent.LIST_ANOMALIES
        if context and context.last_intent:
            return context.last_intent
        return AssistantIntent.UNSUPPORTED

    def _resolve_candidate(
        self,
        intent: AssistantIntent,
        route: str | None,
        dates: DateResolution,
        snapshot: AnalysisSnapshot,
        context: AssistantConversationContext | None,
    ) -> AnomalyView | AssistantQueryPlan:
        week = dates.week_of
        if week is None and context and route == context.route:
            week = context.week_of
        matches = [
            item
            for item in snapshot.anomalies
            if (route is None or item.route == route)
            and (week is None or item.week_of == week)
            and (dates.week_from is None or item.week_of >= dates.week_from)
            and (dates.week_to is None or item.week_of <= dates.week_to)
        ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return self._unsupported("No anomaly in the active snapshot matches that selection.")
        options = tuple(
            ClarificationOption(
                option_id=item.candidate_key,
                label=f"{item.route} — {item.week_of.isoformat()}",
                value=f"{item.route} {item.week_of.isoformat()}",
            )
            for item in sorted(matches, key=lambda value: (value.week_of, value.route))[:5]
        )
        return self._clarify(
            intent,
            "More than one anomaly matches. Which route-week should I investigate?",
            options,
        )

    def _route_clarification(
        self,
        intent: AssistantIntent,
        suggestions: tuple[str, ...],
        snapshot: AnalysisSnapshot,
    ) -> AssistantQueryPlan:
        routes = suggestions or tuple(sorted(snapshot.route_timelines)[:5])
        return self._clarify(
            intent,
            "Which exact route should I use?",
            tuple(
                ClarificationOption(option_id=route, label=route, value=route)
                for route in routes
            ),
        )

    def _single(
        self,
        intent: AssistantIntent,
        tool: AssistantTool,
        template: AnswerTemplate,
        filters: QueryFilters | None = None,
        *,
        limit: int | None = None,
    ) -> AssistantQueryPlan:
        return AssistantQueryPlan(
            planner_version=self.planner_version,
            intent=intent,
            steps=(
                QueryStep(
                    tool=tool,
                    filters=filters or QueryFilters(),
                    limit=limit or self.default_limit,
                ),
            ),
            answer_template=template,
        )

    def _plan(self, intent: AssistantIntent, template: AnswerTemplate) -> AssistantQueryPlan:
        return AssistantQueryPlan(
            planner_version=self.planner_version,
            intent=intent,
            answer_template=template,
        )

    def _unsupported(self, reason: str) -> AssistantQueryPlan:
        return AssistantQueryPlan(
            planner_version=self.planner_version,
            intent=AssistantIntent.UNSUPPORTED,
            answer_template=AnswerTemplate.LIMITATION,
            unsupported_reason=reason,
        )

    def _clarify(
        self,
        intent: AssistantIntent,
        question: str,
        options: tuple[ClarificationOption, ...] = (),
    ) -> AssistantQueryPlan:
        return AssistantQueryPlan(
            planner_version=self.planner_version,
            intent=intent,
            answer_template=AnswerTemplate.LIMITATION,
            requires_clarification=True,
            clarification=ClarificationRequest(question=question, options=options),
        )


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


def _verdict(text: str) -> EvidenceVerdict | None:
    if "unexplained" in text or "not explained" in text:
        return EvidenceVerdict.UNEXPLAINED
    if "partial" in text:
        return EvidenceVerdict.PARTIALLY_EXPLAINED
    if "justified" in text:
        return EvidenceVerdict.JUSTIFIED
    return None


def _trigger(text: str) -> str | None:
    if "both" in text and ("baseline" in text or "comparison" in text):
        return "both"
    if "peer" in text and "trigger" in text:
        return "peer"
    if "own" in text and ("baseline" in text or "trigger" in text):
        return "own_history"
    return None


def _sort_field(text: str) -> AssistantSortField | None:
    if "peer" in text:
        return AssistantSortField.VS_SIMILAR_ROUTES_PCT
    if "own" in text or "history" in text:
        return AssistantSortField.VS_OWN_HISTORY_PCT
    if "cost" in text or "expensive" in text:
        return AssistantSortField.COST_PER_TONNE_KM
    if "week" in text or "recent" in text:
        return AssistantSortField.WEEK_OF
    return None


def _limit(text: str) -> int | None:
    match = re.search(r"\btop\s+(\d+)\b", text)
    if match:
        return int(match.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
    return next((value for word, value in words.items() if f"top {word}" in text), None)


def _rejection_code(text: str) -> str | None:
    for code in (
        "route_mismatch",
        "date_no_overlap",
        "cost_impact_not_positive",
        "impact_direction_not_increase",
        "scope_outside_dataset",
    ):
        if code in text or code.replace("_", " ") in text:
            return code
    return None


def _month_tokens() -> tuple[str, ...]:
    return (
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    )
