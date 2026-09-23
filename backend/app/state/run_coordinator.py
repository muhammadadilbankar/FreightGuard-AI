"""Single-run coordination and safe latest-attempt status."""

from datetime import UTC, datetime
from threading import Lock, RLock
from uuid import uuid4

from .errors import AnalysisRunInProgressError
from .models import RunState, RunStatus


class RunCoordinator:
    def __init__(self) -> None:
        self._run_lock = Lock()
        self._status_lock = RLock()
        self._status = RunStatus()

    def begin(self, *, has_snapshot: bool) -> RunStatus:
        if not self._run_lock.acquire(blocking=False):
            raise AnalysisRunInProgressError("An analysis run is already in progress.")
        status = RunStatus(
            state=RunState.RUNNING,
            attempt_id=str(uuid4()),
            started_at=datetime.now(UTC),
            previous_snapshot_available=has_snapshot,
            latest_snapshot_id=self.status().latest_snapshot_id,
        )
        with self._status_lock:
            self._status = status
        return status

    def succeed(self, snapshot_id: str) -> RunStatus:
        with self._status_lock:
            current = self._status
            self._status = RunStatus(
                state=RunState.SUCCEEDED,
                attempt_id=current.attempt_id,
                started_at=current.started_at,
                finished_at=datetime.now(UTC),
                latest_snapshot_id=snapshot_id,
                previous_snapshot_available=True,
            )
            return self._status

    def fail(self, code: str, message: str, *, has_snapshot: bool) -> RunStatus:
        with self._status_lock:
            current = self._status
            self._status = RunStatus(
                state=RunState.FAILED,
                attempt_id=current.attempt_id,
                started_at=current.started_at,
                finished_at=datetime.now(UTC),
                latest_snapshot_id=current.latest_snapshot_id,
                failure_code=code,
                failure_message=message,
                previous_snapshot_available=has_snapshot,
            )
            return self._status

    def release(self) -> None:
        if self._run_lock.locked():
            self._run_lock.release()

    def status(self) -> RunStatus:
        with self._status_lock:
            return self._status
