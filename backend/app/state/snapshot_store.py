"""Thread-safe atomic snapshot reference."""

from threading import RLock

from .errors import AnalysisNotReadyError
from .models import AnalysisSnapshot


class SnapshotStore:
    def __init__(self, initial: AnalysisSnapshot | None = None) -> None:
        self._snapshot = initial
        self._lock = RLock()

    def get(self) -> AnalysisSnapshot | None:
        with self._lock:
            return self._snapshot

    def require(self) -> AnalysisSnapshot:
        snapshot = self.get()
        if snapshot is None:
            raise AnalysisNotReadyError(
                "Run an analysis before requesting snapshot data."
            )
        return snapshot

    def replace(self, snapshot: AnalysisSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot
