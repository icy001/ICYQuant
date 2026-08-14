"""Strategy runtime heartbeat.

The runtime periodically reports its state through ``RuntimeHeartbeat``
(by default every 5 seconds).  When no heartbeat has been observed within
the timeout window the runtime is considered ``UNKNOWN``: the system can no
longer claim the strategy is running, which must drive recovery and
reconciliation rather than a blind assumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from services.strategy.runtime.state import RuntimeState

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class RuntimeHeartbeat:
    """A single heartbeat emitted by a strategy runtime."""

    strategy_id: str
    runtime_id: str
    timestamp: datetime
    sequence: int
    state: str


def utcnow() -> datetime:
    """Timezone-aware UTC now, kept behind one name for testability."""
    return datetime.now(timezone.utc)


class HeartbeatTracker:
    """Tracks the latest heartbeat per strategy and detects staleness.

    A strategy whose heartbeat is stale (or that was explicitly expired)
    reports ``RuntimeState.UNKNOWN`` so that reconciliation treats it as
    unrecoverable-by-assumption.
    """

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._latest: dict[str, RuntimeHeartbeat] = {}
        self._expired: set[str] = set()

    def record(self, heartbeat: RuntimeHeartbeat) -> None:
        """Register ``heartbeat`` as the latest state for its strategy."""
        self._latest[heartbeat.strategy_id] = heartbeat
        self._expired.discard(heartbeat.strategy_id)

    def last(self, strategy_id: str) -> RuntimeHeartbeat | None:
        """Return the latest heartbeat for ``strategy_id`` or ``None``."""
        return self._latest.get(strategy_id)

    def expire(self, strategy_id: str) -> None:
        """Force ``strategy_id`` into the unknown/expired bucket."""
        self._expired.add(strategy_id)

    def is_expired(self, strategy_id: str) -> bool:
        return strategy_id in self._expired

    def is_stale(self, strategy_id: str, now: datetime | None = None) -> bool:
        """Return True when the latest heartbeat is older than the timeout."""
        if self.is_expired(strategy_id):
            return True
        latest = self._latest.get(strategy_id)
        if latest is None:
            return True
        reference = now if now is not None else utcnow()
        return (reference - latest.timestamp).total_seconds() > self.timeout_seconds

    def state(self, strategy_id: str, now: datetime | None = None) -> str:
        """Return the authoritative runtime state for ``strategy_id``.

        ``UNKNOWN`` is returned when there is no heartbeat, the heartbeat
        expired, or the latest heartbeat is stale.
        """
        if self.is_stale(strategy_id, now=now):
            return RuntimeState.UNKNOWN.value
        latest = self._latest.get(strategy_id)
        if latest is None:
            return RuntimeState.UNKNOWN.value
        return latest.state
