"""Frozen intent snapshot used for the risk handoff.

An intent is mutable in the strategy domain (its state advances through the
lifecycle) but the moment it crosses into the risk domain it must be frozen:
the risk engine decides on exactly what the strategy expressed at handoff
time, not on whatever the intent looks like one microsecond later.

:class:`IntentSnapshot` is therefore an immutable view of an intent: full
lineage (strategy / session / signal / intent / correlation ids), the
instrument and desired trade (symbol / side / target_quantity), the execution
preferences (policy / urgency), the frozen state and the TTL window plus the
exact capture time.  The risk engine can store it, replay it and audit it
without ever mutating the strategy's intent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from services.strategy.execution.intent import ExecutionIntent


@dataclass(frozen=True)
class IntentSnapshot:
    """Immutable view of an execution intent at one point in time."""

    intent_id: str
    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: Optional[str]

    symbol: str
    side: str
    target_quantity: float

    execution_policy: str
    urgency: str

    state: str

    created_at: float
    expires_at: float
    captured_at: float

    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the snapshot."""
        return {
            "intent_id": self.intent_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "symbol": self.symbol,
            "side": self.side,
            "target_quantity": self.target_quantity,
            "execution_policy": self.execution_policy,
            "urgency": self.urgency,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "captured_at": self.captured_at,
        }


def snapshot_intent(
    intent: ExecutionIntent,
    *,
    captured_at: Optional[float] = None,
) -> IntentSnapshot:
    """Freeze an execution intent into an immutable snapshot.

    ``captured_at`` defaults to the current wall clock; pass an explicit
    value for deterministic tests.
    """
    return IntentSnapshot(
        intent_id=intent.intent_id,
        strategy_id=intent.strategy_id,
        session_id=intent.session_id,
        signal_id=intent.signal_id,
        correlation_id=intent.correlation_id,
        symbol=intent.symbol,
        side=intent.side,
        target_quantity=intent.target_quantity,
        execution_policy=intent.execution_policy,
        urgency=intent.urgency,
        state=intent.state,
        created_at=intent.created_at,
        expires_at=intent.expires_at,
        captured_at=time.time() if captured_at is None else captured_at,
        metadata=dict(intent.metadata),
    )
