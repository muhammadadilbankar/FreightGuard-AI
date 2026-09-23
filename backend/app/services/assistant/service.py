"""Snapshot-bound orchestration for the investigation assistant."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter

from ...core.config import Settings
from ...domain.assistant import (
    AssistantConversationContext,
    AssistantIntent,
    AssistantMode,
    AssistantQueryPlan,
    AssistantRequest,
    AssistantResponseData,
    AssistantResponseEnvelope,
    AssistantResponseMeta,
    AssistantStatus,
    AssistantUsage,
)
from ...state.errors import (
    AssistantExecutionError,
    AssistantGroundingError,
    AssistantPlannerUnavailableError,
    InvalidQueryError,
    UnsupportedAssistantModeError,
)
from ...state.models import AnalysisSnapshot
from .cache import load_cached_plan, plan_cache_key, store_cached_plan
from .composition import compose_answer
from .execution import execute_plan
from .grounding import validate_grounding
from .planners.deterministic import DeterministicPlanner
from .planners.provider import OpenAIPlanProvider
from .policy import validate_plan


class InvestigationAssistantService:
    """Plan and answer questions without allowing a model to own any fact."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider: OpenAIPlanProvider | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.deterministic = DeterministicPlanner(
            planner_version=settings.assistant_planner_version,
            default_limit=settings.assistant_default_result_limit,
            max_limit=settings.assistant_max_result_limit,
        )

    def query(
        self,
        request: AssistantRequest,
        snapshot: AnalysisSnapshot,
        *,
        request_id: str,
    ) -> AssistantResponseEnvelope:
        started = perf_counter()
        self._validate_request(request, snapshot)
        mode = request.mode or AssistantMode(self.settings.assistant_mode)
        plan, source, cache_hit, usage = self._plan(request, snapshot, mode)
        try:
            validated = validate_plan(
                plan,
                snapshot,
                max_steps=self.settings.assistant_max_plan_steps,
                max_limit=self.settings.assistant_max_result_limit,
            )
        except (TypeError, ValueError) as exc:
            raise AssistantPlannerUnavailableError(
                "The assistant planner produced a plan that policy rejected."
            ) from exc

        if validated.requires_clarification:
            data = AssistantResponseData(
                status=AssistantStatus.NEEDS_CLARIFICATION,
                title="Clarification needed",
                clarification=validated.clarification,
                context=self._context(request.context, validated, snapshot),
            )
            result_count = 0
        elif validated.intent == AssistantIntent.UNSUPPORTED:
            data = AssistantResponseData(
                status=AssistantStatus.UNSUPPORTED,
                title="Request outside supported investigation scope",
                limitations=(validated.unsupported_reason or "That request is not supported.",),
                context=self._context(request.context, validated, snapshot),
            )
            result_count = 0
        else:
            try:
                execution = execute_plan(validated, snapshot)
                composition = compose_answer(validated, execution, snapshot)
                validate_grounding(composition.response, composition.registry)
            except (AssertionError, IndexError, TypeError, ValueError) as exc:
                error_type = (
                    AssistantGroundingError
                    if isinstance(exc, ValueError)
                    else AssistantExecutionError
                )
                raise error_type("The assistant could not produce a verified response.") from exc
            data = composition.response
            result_count = composition.result_count

        if len(data.citations) > self.settings.assistant_max_citations:
            raise AssistantGroundingError("The response exceeded the citation safety limit.")
        elapsed = max(0, round((perf_counter() - started) * 1000))
        response = AssistantResponseEnvelope(
            data=data,
            meta=AssistantResponseMeta(
                snapshot_id=snapshot.snapshot_id,
                planner_mode=mode,
                planner_source=source,
                planner_version=validated.planner_version,
                cache_hit=cache_hit,
                latency_ms=elapsed,
                tool_count=len(validated.steps),
                result_count=result_count,
                request_id=request_id,
                usage=usage,
            ),
        )
        self._audit(request, response)
        return response

    def _validate_request(
        self, request: AssistantRequest, snapshot: AnalysisSnapshot
    ) -> None:
        if not self.settings.assistant_enabled:
            raise UnsupportedAssistantModeError("The assistant is disabled.")
        if len(request.question) > self.settings.assistant_max_question_chars:
            raise InvalidQueryError("The question exceeds the configured length limit.")
        if request.context and request.context.snapshot_id != snapshot.snapshot_id:
            raise InvalidQueryError(
                "Conversation context belongs to a different analysis snapshot."
            )

    def _plan(
        self,
        request: AssistantRequest,
        snapshot: AnalysisSnapshot,
        mode: AssistantMode,
    ) -> tuple[AssistantQueryPlan, str, bool, AssistantUsage]:
        if mode.value not in self.settings.assistant_allowed_modes:
            raise UnsupportedAssistantModeError(
                f"Assistant mode '{mode.value}' is not allowed."
            )
        if mode == AssistantMode.TEMPLATE:
            return (
                self.deterministic.plan(request.question, snapshot, request.context),
                "deterministic",
                False,
                AssistantUsage(),
            )
        identity = (
            self.settings.assistant_planner_model
            if mode == AssistantMode.LIVE
            else "validated-replay"
        )
        key = plan_cache_key(
            request.question,
            request.context,
            snapshot.snapshot_id,
            self.settings.assistant_planner_version,
            self.settings.assistant_policy_version,
            identity,
        )
        cached = load_cached_plan(self.settings.assistant_cache_path, key)
        if cached is not None:
            return cached, "cache", True, AssistantUsage()
        if mode == AssistantMode.REPLAY:
            if self.settings.assistant_replay_fallback_to_template:
                return (
                    self.deterministic.plan(request.question, snapshot, request.context),
                    "deterministic",
                    False,
                    AssistantUsage(),
                )
            raise AssistantPlannerUnavailableError(
                "No validated replay plan exists for this snapshot and question."
            )
        provider = self.provider or self._live_provider()
        try:
            result = provider.plan(request.question, snapshot, request.context)
        except Exception as exc:
            raise AssistantPlannerUnavailableError(
                "The live planning provider was unavailable."
            ) from exc
        validated = validate_plan(
            result.plan,
            snapshot,
            max_steps=self.settings.assistant_max_plan_steps,
            max_limit=self.settings.assistant_max_result_limit,
        )
        if self.settings.assistant_cache_enabled:
            store_cached_plan(self.settings.assistant_cache_path, key, validated)
        return validated, "provider", False, result.usage

    def _live_provider(self) -> OpenAIPlanProvider:
        if self.settings.openai_api_key is None:
            raise AssistantPlannerUnavailableError(
                "Live planning credentials are not configured."
            )
        return OpenAIPlanProvider(
            api_key=self.settings.openai_api_key.get_secret_value(),
            model=self.settings.assistant_planner_model,
            timeout_seconds=self.settings.assistant_timeout_seconds,
        )

    @staticmethod
    def _context(
        previous: AssistantConversationContext | None,
        plan: AssistantQueryPlan,
        snapshot: AnalysisSnapshot,
    ) -> AssistantConversationContext:
        return AssistantConversationContext(
            snapshot_id=snapshot.snapshot_id,
            last_intent=(
                plan.intent if plan.intent != AssistantIntent.UNSUPPORTED else None
            ),
            route=previous.route if previous else None,
            week_of=previous.week_of if previous else None,
            week_from=previous.week_from if previous else None,
            week_to=previous.week_to if previous else None,
            candidate_keys=previous.candidate_keys if previous else (),
            note_id=previous.note_id if previous else None,
        )

    def _audit(
        self, request: AssistantRequest, response: AssistantResponseEnvelope
    ) -> None:
        path: Path = self.settings.assistant_audit_path
        record = {
            "question_sha256": hashlib.sha256(
                request.question.encode("utf-8")
            ).hexdigest(),
            "raw_question": (
                request.question if self.settings.assistant_store_raw_questions else None
            ),
            "snapshot_id": response.meta.snapshot_id,
            "status": response.data.status.value,
            "planner_mode": response.meta.planner_mode.value,
            "planner_source": response.meta.planner_source,
            "tool_count": response.meta.tool_count,
            "request_id": response.meta.request_id,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError:
            # Audit I/O is useful telemetry, but never changes an assistant fact.
            return
