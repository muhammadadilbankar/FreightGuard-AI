from datetime import date
from threading import Event, Thread

import pytest

from backend.app.application.snapshot_queries import (
    get_anomaly,
    get_timeline,
    list_anomalies,
)
from backend.app.state.errors import (
    AnalysisNotReadyError,
    AnalysisRunInProgressError,
    AnomalyNotFoundError,
    RouteNotFoundError,
)
from backend.app.state.run_coordinator import RunCoordinator
from backend.app.state.snapshot_store import SnapshotStore


def test_snapshot_store_is_atomic_and_requires_initial_publication(
    snapshot_factory,
) -> None:
    store = SnapshotStore()
    with pytest.raises(AnalysisNotReadyError):
        store.require()
    snapshot = snapshot_factory()
    store.replace(snapshot)
    assert store.require() is snapshot


def test_coordinator_allows_exactly_one_active_run() -> None:
    coordinator = RunCoordinator()
    coordinator.begin(has_snapshot=False)
    with pytest.raises(AnalysisRunInProgressError):
        coordinator.begin(has_snapshot=False)
    coordinator.release()
    assert coordinator.begin(has_snapshot=False).attempt_id is not None
    coordinator.release()


def test_queries_filter_page_and_use_exact_keys(snapshot_factory) -> None:
    snapshot = snapshot_factory()
    items, total = list_anomalies(snapshot, route="R1", limit=1)
    assert total == 1
    assert items[0].candidate_key == "R1|2024-01-08"
    assert get_anomaly(snapshot, "R1", date(2024, 1, 8)) is items[0]
    assert len(get_timeline(snapshot, "R1")) == 1
    with pytest.raises(AnomalyNotFoundError):
        get_anomaly(snapshot, "R1", date(2024, 1, 15))
    with pytest.raises(RouteNotFoundError):
        get_timeline(snapshot, "r1")


def test_readers_never_observe_a_partial_replacement(snapshot_factory) -> None:
    first, second = snapshot_factory("first"), snapshot_factory("second")
    store = SnapshotStore(first)
    start = Event()
    seen: list[str] = []

    def reader() -> None:
        start.wait()
        for _ in range(500):
            seen.append(store.require().snapshot_id)

    thread = Thread(target=reader)
    thread.start()
    start.set()
    store.replace(second)
    thread.join(timeout=2)
    assert set(seen) <= {"first", "second"}
    assert store.require() is second
