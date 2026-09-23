"""Application service owning private execution and atomic publication."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from starlette.concurrency import run_in_threadpool

from ..core.config import Settings
from ..state.errors import (
    AnalysisRunFailedError,
    ApplicationError,
    UnsupportedExplanationModeError,
)
from ..state.models import AnalysisSnapshot, PublishedRunResult, RunAnalysisCommand
from ..state.run_coordinator import RunCoordinator
from ..state.snapshot_store import SnapshotStore
from .pipeline import PipelineExecutionResult, execute_pipeline
from .snapshot_builder import build_snapshot


class AnalysisService:
    def __init__(
        self,
        settings: Settings,
        store: SnapshotStore,
        coordinator: RunCoordinator,
        *,
        pipeline_runner: Callable[
            [Settings, str], PipelineExecutionResult
        ] = execute_pipeline,
        snapshot_factory: Callable[..., AnalysisSnapshot] = build_snapshot,
    ) -> None:
        self.settings = settings
        self.store = store
        self.coordinator = coordinator
        self.pipeline_runner = pipeline_runner
        self.snapshot_factory = snapshot_factory

    async def run(self, command: RunAnalysisCommand) -> PublishedRunResult:
        mode = command.explanation_mode
        if mode not in {"template", "replay", "live"}:
            raise UnsupportedExplanationModeError("Unsupported explanation mode.")
        if mode == "live" and not self.settings.api_live_explanations_enabled:
            raise UnsupportedExplanationModeError("Live explanations are disabled.")
        previous = self.store.get()
        status = self.coordinator.begin(has_snapshot=previous is not None)
        started = status.started_at or datetime.now(UTC)
        try:
            private_root = (
                self.settings.output_data_dir / "api_runs" / str(status.attempt_id)
            )
            run_settings = self.settings.model_copy(
                update={
                    "output_data_dir": Path(private_root),
                    "explanation_cache_path": Path(private_root)
                    / "explanation_cache.jsonl",
                }
            )
            result = await run_in_threadpool(self.pipeline_runner, run_settings, mode)
            snapshot = self.snapshot_factory(
                result,
                mode=mode,
                threshold=self.settings.anomaly_threshold_percent,
            )
            self.store.replace(snapshot)
            finished_status = self.coordinator.succeed(snapshot.snapshot_id)
            finished = finished_status.finished_at or datetime.now(UTC)
            return PublishedRunResult(
                attempt_id=str(status.attempt_id),
                snapshot=snapshot,
                started_at=started,
                finished_at=finished,
                duration_ms=max(0, round((finished - started).total_seconds() * 1000)),
                replaced_previous_snapshot=previous is not None,
            )
        except ApplicationError as exc:
            self.coordinator.fail(exc.code, str(exc), has_snapshot=previous is not None)
            raise
        except Exception as exc:
            message = (
                "Analysis failed; the previously published snapshot was preserved."
            )
            self.coordinator.fail(
                "analysis_run_failed", message, has_snapshot=previous is not None
            )
            raise AnalysisRunFailedError(message) from exc
        finally:
            self.coordinator.release()
