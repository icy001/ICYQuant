"""Strategy execution readiness gate.

The gate is the last system-level barrier before signal generation::

    Lifecycle RUNNING AND Runtime RUNNING AND Readiness READY
        ==> Execution Eligible

Even a strategy whose lifecycle and runtime are both RUNNING is blocked from
producing execution intents when the gate does not pass.  Hard check
failures (risk, execution, lifecycle, ...) always result in ``BLOCKED``; soft
failures merely ``DEGRADE`` the strategy, and whether a degraded strategy may
still trade is a policy decision (``ReadinessPolicy.allow_degraded``).

A readiness verdict must never be reused forever - it expires after its TTL
(``ReadinessCache``) and the pipeline re-evaluates before the next signal.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional, Sequence

from services.strategy.readiness.checks import DEFAULT_READINESS_CHECKS, ReadinessCheck
from services.strategy.readiness.policy import ReadinessPolicy
from services.strategy.readiness.result import ReadinessResult
from services.strategy.readiness.state import ReadinessContext, new_evaluation_id

#: Readiness events emitted as the strategy moves between readiness states.
READINESS_EVENTS: dict[str, str] = {
    "checking": "STRATEGY_READINESS_CHECKING",
    "ready": "STRATEGY_READY",
    "not_ready": "STRATEGY_NOT_READY",
    "blocked": "STRATEGY_EXECUTION_BLOCKED",
    "unblocked": "STRATEGY_EXECUTION_UNBLOCKED",
    "degraded": "STRATEGY_READINESS_DEGRADED",
}


class StrategyExecutionReadinessGate:
    """Aggregates readiness checks into a single verdict."""

    def __init__(
        self,
        checks: Optional[Sequence[ReadinessCheck]] = None,
        policy: Optional[ReadinessPolicy] = None,
    ) -> None:
        self.checks = tuple(checks) if checks is not None else DEFAULT_READINESS_CHECKS
        self.policy = policy or ReadinessPolicy()

    def evaluate(self, context: ReadinessContext) -> ReadinessResult:
        failures: list[str] = []
        hard_failures: list[str] = []

        for check in self.checks:
            if not self.policy.requires(check.name):
                continue
            result = check.check(context)
            if result.passed:
                continue
            failures.append(check.name)
            if result.hard:
                hard_failures.append(check.name)

        evaluation_id = context.evaluation_id or new_evaluation_id(context.timestamp)

        if hard_failures:
            return ReadinessResult(
                strategy_id=context.strategy_id,
                state="BLOCKED",
                ready=False,
                reasons=tuple(hard_failures),
                checked_at=context.timestamp,
                evaluation_id=evaluation_id,
            )

        if failures:
            # Soft failures only: the strategy is degraded.  Whether it may
            # still attempt to trade is decided by the strategy policy.
            return ReadinessResult(
                strategy_id=context.strategy_id,
                state="DEGRADED",
                ready=self.policy.allow_degraded,
                reasons=tuple(failures),
                checked_at=context.timestamp,
                evaluation_id=evaluation_id,
            )

        return ReadinessResult(
            strategy_id=context.strategy_id,
            state="READY",
            ready=True,
            reasons=(),
            checked_at=context.timestamp,
            evaluation_id=evaluation_id,
        )


def can_execute(result: ReadinessResult) -> bool:
    """Return True when ``result`` permits the strategy to attempt execution.

    This is the signal generation gate: a ``BLOCKED`` (or non-ready)
    strategy cannot produce execution intents.
    """
    return result.ready


class ReadinessCache:
    """TTL-bound cache of the latest readiness verdict per strategy.

    Readiness must never be reused forever: a verdict cached at 10:00 cannot
    still be trusted at 10:30 once risk has become blocked.  Entries expire
    after ``default_ttl`` seconds (or the result's own ``ttl`` when set).
    """

    def __init__(self, default_ttl: float = 5.0) -> None:
        self.default_ttl = default_ttl
        self._entries: dict[str, ReadinessResult] = {}
        self._lock = threading.Lock()

    def put(self, result: ReadinessResult) -> None:
        with self._lock:
            self._entries[result.strategy_id] = result

    def get(
        self,
        strategy_id: str,
        now: Optional[float] = None,
    ) -> Optional[ReadinessResult]:
        with self._lock:
            result = self._entries.get(strategy_id)
            if result is None:
                return None
            reference = now if now is not None else time.time()
            ttl = result.ttl if result.ttl is not None else self.default_ttl
            if reference - result.checked_at > ttl:
                del self._entries[strategy_id]
                return None
            return result

    def drop(self, strategy_id: str) -> None:
        with self._lock:
            self._entries.pop(strategy_id, None)


class ReadinessTracker:
    """Tracks per-strategy readiness transitions and emits readiness events.

    A strategy that was ready and stops being ready emits
    ``STRATEGY_EXECUTION_BLOCKED``; the reverse transition emits
    ``STRATEGY_EXECUTION_UNBLOCKED``.  Event payloads carry the full audit
    context (strategy_id, evaluation_id, previous/new state, reasons).
    """

    def __init__(
        self,
        emit: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        self._emit = emit
        self._last: dict[str, Optional[ReadinessResult]] = {}

    def record(self, result: ReadinessResult) -> None:
        previous = self._last.get(result.strategy_id)
        self._last[result.strategy_id] = result
        if self._emit is None:
            return
        if previous is None:
            event = self._initial_event(result)
        else:
            event = self._transition_event(previous, result)
        if event is not None:
            self._emit(event, self._payload(previous, result))

    def last(self, strategy_id: str) -> Optional[ReadinessResult]:
        return self._last.get(strategy_id)

    def _initial_event(self, result: ReadinessResult) -> Optional[str]:
        if result.state == "BLOCKED":
            return READINESS_EVENTS["blocked"]
        if result.state == "DEGRADED":
            return READINESS_EVENTS["degraded"]
        if result.state == "NOT_READY":
            return READINESS_EVENTS["not_ready"]
        if result.ready:
            return READINESS_EVENTS["ready"]
        return None

    def _transition_event(
        self,
        previous: ReadinessResult,
        result: ReadinessResult,
    ) -> Optional[str]:
        if previous.ready and not result.ready:
            return READINESS_EVENTS["blocked"]
        if not previous.ready and result.ready:
            return READINESS_EVENTS["unblocked"]
        if result.state != previous.state:
            if result.state == "DEGRADED":
                return READINESS_EVENTS["degraded"]
            if result.state == "NOT_READY":
                return READINESS_EVENTS["not_ready"]
        return None

    def _payload(
        self,
        previous: Optional[ReadinessResult],
        result: ReadinessResult,
    ) -> dict[str, Any]:
        return {
            "strategy_id": result.strategy_id,
            "evaluation_id": result.evaluation_id,
            "previous_state": previous.state if previous else None,
            "new_state": result.state,
            "ready": result.ready,
            "reasons": list(result.reasons),
            "checked_at": result.checked_at,
        }
