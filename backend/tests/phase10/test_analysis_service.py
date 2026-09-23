from __future__ import annotations

import asyncio
from threading import Event

import pytest

from backend.app.application.analysis_service import AnalysisService
from backend.app.core.config import Settings
from backend.app.state.errors import (
    AnalysisRunFailedError,
    AnalysisRunInProgressError,
    UnsupportedExplanationModeError,
)
from backend.app.state.models import RunAnalysisCommand, RunState
from backend.app.state.run_coordinator import RunCoordinator
from backend.app.state.snapshot_store import SnapshotStore


def test_success_publishes_and_failure_preserves_previous(snapshot_factory) -> None:
    asyncio.run(_success_and_failure(snapshot_factory))


async def _success_and_failure(snapshot_factory) -> None:
    first, second = snapshot_factory("first"), snapshot_factory("second")
    store = SnapshotStore(first)
    coordinator = RunCoordinator()
    service = AnalysisService(
        Settings(_env_file=None),
        store,
        coordinator,
        pipeline_runner=lambda settings, mode: object(),  # type: ignore[arg-type]
        snapshot_factory=lambda result, **kwargs: second,
    )
    published = await service.run(RunAnalysisCommand("template"))
    assert published.replaced_previous_snapshot is True
    assert store.require() is second

    def fail(settings, mode):
        raise RuntimeError("private detail")

    failing = AnalysisService(
        Settings(_env_file=None),
        store,
        coordinator,
        pipeline_runner=fail,
        snapshot_factory=lambda result, **kwargs: first,
    )
    with pytest.raises(AnalysisRunFailedError, match="preserved"):
        await failing.run(RunAnalysisCommand("template"))
    assert store.require() is second
    assert coordinator.status().state == RunState.FAILED
    assert "private detail" not in str(coordinator.status().failure_message)


def test_single_run_policy_and_disabled_live_mode(snapshot_factory) -> None:
    asyncio.run(_single_run_policy(snapshot_factory))


async def _single_run_policy(snapshot_factory) -> None:
    entered, release = Event(), Event()

    def wait_for_release(settings, mode):
        entered.set()
        release.wait(timeout=2)
        return object()

    store = SnapshotStore()
    service = AnalysisService(
        Settings(_env_file=None),
        store,
        RunCoordinator(),
        pipeline_runner=wait_for_release,  # type: ignore[arg-type]
        snapshot_factory=lambda result, **kwargs: snapshot_factory(),
    )
    first = asyncio.create_task(service.run(RunAnalysisCommand("template")))
    await asyncio.to_thread(entered.wait, 1)
    with pytest.raises(AnalysisRunInProgressError):
        await service.run(RunAnalysisCommand("template"))
    release.set()
    await first
    with pytest.raises(UnsupportedExplanationModeError):
        await service.run(RunAnalysisCommand("live"))
