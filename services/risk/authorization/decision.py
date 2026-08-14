"""Risk decision - the immutable output of a risk evaluation.

The risk engine evaluates an execution intent and produces a
:class:`RiskDecision`.  A decision is a frozen fact: it records whether the
trade was approved, the exact approved quantity, the execution policy the
approval applies to and the full identity chain (strategy / session / signal /
intent / correlation) that the approval is scoped to.

A rejected decision can never be turned into a certificate; an approved
decision carries the ``approved_quantity`` that later becomes the hard ceiling
for any order request.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class RiskDecision:
    """Immutable risk engine output for one execution intent."""

    decision_id: str
    intent_id: str
    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: str

    approved: bool
    approved_quantity: Optional[float]

    symbol: str = ""
    side: str = ""
    execution_policy: Optional[str] = None

    decided_at: float = 0.0
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id is required")
        if not self.intent_id:
            raise ValueError("intent_id is required")
        if not self.strategy_id:
            raise ValueError("strategy_id is required")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")

    def as_dict(self) -> dict[str, Any]:
        """Audit-ready plain mapping of the decision."""
        return {
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "approved": self.approved,
            "approved_quantity": self.approved_quantity,
            "symbol": self.symbol,
            "side": self.side,
            "execution_policy": self.execution_policy,
            "decided_at": self.decided_at,
            "reason": self.reason,
        }


_decision_counter = itertools.count(1)


def new_decision_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic risk decision id.

    Example: ``RISK-20260813-000001``.  The id is stable per risk decision
    and is what the certificate ledger uses for 1:1 replay protection.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_decision_counter)
    return f"RISK-{date_part}-{sequence:06d}"


def approved_decision(
    *,
    intent_id: str = "INT-001",
    strategy_id: str = "STRAT-001",
    session_id: str = "SESSION-001",
    signal_id: str = "SIG-001",
    correlation_id: str = "CORR-001",
    symbol: str = "NVDA",
    side: str = "BUY",
    approved_quantity: float = 100.0,
    execution_policy: Optional[str] = "MARKET",
    decided_at: Optional[float] = None,
    reason: Optional[str] = None,
    decision_id: Optional[str] = None,
) -> RiskDecision:
    """Build an approved decision with generated ids (test-friendly)."""
    reference = time.time() if decided_at is None else decided_at
    return RiskDecision(
        decision_id=decision_id or new_decision_id(reference),
        intent_id=intent_id,
        strategy_id=strategy_id,
        session_id=session_id,
        signal_id=signal_id,
        correlation_id=correlation_id,
        approved=True,
        approved_quantity=approved_quantity,
        symbol=symbol,
        side=side,
        execution_policy=execution_policy,
        decided_at=reference,
        reason=reason,
    )


def rejected_decision(
    *,
    intent_id: str = "INT-001",
    strategy_id: str = "STRAT-001",
    session_id: str = "SESSION-001",
    signal_id: str = "SIG-001",
    correlation_id: str = "CORR-001",
    decided_at: Optional[float] = None,
    reason: str = "rejected by risk policy",
    decision_id: Optional[str] = None,
) -> RiskDecision:
    """Build a rejected decision (no approved quantity)."""
    reference = time.time() if decided_at is None else decided_at
    return RiskDecision(
        decision_id=decision_id or new_decision_id(reference),
        intent_id=intent_id,
        strategy_id=strategy_id,
        session_id=session_id,
        signal_id=signal_id,
        correlation_id=correlation_id,
        approved=False,
        approved_quantity=None,
        decided_at=reference,
        reason=reason,
    )
