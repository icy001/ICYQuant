"""Execution readiness gate - the second gate at intent creation time.

The Part 1.3 readiness verdict has a TTL: a READY at 14:00:00 cannot be
assumed at 14:00:03 after risk became blocked.  The execution gate therefore
re-verifies readiness against the frozen :class:`ExecutionContext` snapshot
every time the strategy attempts to create an execution intent::

    Approved Signal
        -> Execution Readiness (second gate)
        -> Session ACTIVE?
        -> Intent Validation
        -> Execution Intent

Without this second gate, a signal generated while the strategy was READY
could bypass a risk state change that happened moments later::

    14:00:00  Strategy READY
    14:00:01  Signal generated
    14:00:02  Risk BLOCKED
    14:00:03  Intent creation  -> BLOCKED (the second gate catches it)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from services.strategy.readiness.result import ReadinessResult
from services.strategy.readiness.state import new_evaluation_id

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from services.strategy.execution.context import ExecutionContext


class ExecutionReadinessGate:
    """Re-verifies execution readiness at intent-creation time.

    The gate inspects the :class:`ExecutionContext` snapshot rather than
    trusting a previously cached verdict.  It fails safe: any UNKNOWN or
    non-good state blocks intent creation, and a READY verdict older than
    ``max_readiness_age`` (or market data older than ``max_market_staleness``)
    is treated as expired.  Only a freshly confirmed READY result lets the
    strategy create an execution intent.
    """

    def __init__(
        self,
        max_market_staleness: float = 5.0,
        max_readiness_age: float = 5.0,
    ) -> None:
        self.max_market_staleness = max_market_staleness
        self.max_readiness_age = max_readiness_age

    def evaluate(self, context: ExecutionContext) -> ReadinessResult:
        failures: list[str] = []

        if context.lifecycle_state != "RUNNING":
            failures.append("lifecycle")
        if context.runtime_state != "RUNNING":
            failures.append("runtime")
        if context.readiness_state != "READY":
            failures.append("readiness")
        elif (
            context.readiness_checked_at > 0
            and context.timestamp - context.readiness_checked_at > self.max_readiness_age
        ):
            # The previous READY verdict is stale: it must be re-evaluated
            # before the strategy can create a new intent.
            failures.append("readiness")
        if context.risk_state not in ("ALLOWED", "OK", "HEALTHY"):
            failures.append("risk")
        if context.execution_state not in ("CONNECTED", "READY"):
            failures.append("execution")
        if (
            context.market_timestamp > 0
            and context.timestamp - context.market_timestamp > self.max_market_staleness
        ):
            failures.append("market_data")

        evaluation_id = new_evaluation_id(context.timestamp)

        if failures:
            return ReadinessResult(
                strategy_id=context.strategy_id,
                state="BLOCKED",
                ready=False,
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

    def can_create_intent(self, context: ExecutionContext) -> bool:
        """Shortcut: whether ``context`` may proceed to intent creation."""
        return self.evaluate(context).ready
