"""
Risk decision context snapshot (Commit 41 Part 1.4).

A snapshot freezes every input that produced a ``RiskDecision`` at decision
time.  Replay rebuilds the *historical* context from the snapshot so that a
re-evaluation is fully deterministic and independent of current market /
account state.

Design notes:

- The snapshot is immutable (``frozen=True``) so a historical decision can
  never be silently re-interpreted with different inputs.
- ``from_context`` is used at decision time to persist the exact inputs.
- ``to_context`` (exposed as ``RiskDecisionContext.from_snapshot``) rebuilds
  the ``RiskDecisionContext`` used by the evaluator during replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context.decision_context import RiskDecisionContext

#: Default policy set version stamped onto every decision record.
#: Bump this whenever policy semantics change (e.g. ``risk-policy-v2``).
DEFAULT_POLICY_VERSION = "risk-policy-v1"


@dataclass(frozen=True)
class RiskDecisionContextSnapshot:
    """Complete input snapshot captured at decision time."""

    account_id: str
    strategy_id: str
    signal_id: str
    instrument: str
    side: str

    current_position: Decimal
    proposed_quantity: Decimal

    available_cash: Decimal

    daily_pnl: Decimal
    daily_loss_limit: Decimal

    position_limit: Decimal

    market_price: Decimal

    snapshot_at: datetime

    correlation_id: str | None = None
    causation_id: str | None = None
    lineage_id: str | None = None

    @classmethod
    def from_context(
        cls,
        context: "RiskDecisionContext",
        *,
        snapshot_at: datetime,
    ) -> "RiskDecisionContextSnapshot":
        """Freeze a decision-time ``RiskDecisionContext`` into a snapshot."""
        return cls(
            account_id=context.account_id,
            strategy_id=context.strategy_id,
            signal_id=context.signal_id,
            instrument=context.instrument_id,
            side=context.side,
            current_position=context.current_position,
            proposed_quantity=context.quantity,
            available_cash=context.available_cash,
            daily_pnl=context.daily_pnl,
            daily_loss_limit=context.daily_loss_limit,
            position_limit=context.max_position,
            market_price=context.price,
            snapshot_at=snapshot_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            lineage_id=context.lineage_id,
        )

    def to_context(self) -> "RiskDecisionContext":
        """Rebuild the historical context used during replay.

        Imported lazily to avoid a circular import between
        ``context_snapshot`` and ``context.decision_context``.
        """
        from .context.decision_context import RiskDecisionContext

        return RiskDecisionContext(
            account_id=self.account_id,
            strategy_id=self.strategy_id,
            signal_id=self.signal_id,
            instrument_id=self.instrument,
            side=self.side,
            quantity=self.proposed_quantity,
            price=self.market_price,
            available_cash=self.available_cash,
            current_position=self.current_position,
            daily_pnl=self.daily_pnl,
            daily_loss_limit=self.daily_loss_limit,
            max_position=self.position_limit,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            lineage_id=self.lineage_id,
        )


__all__ = [
    "DEFAULT_POLICY_VERSION",
    "RiskDecisionContextSnapshot",
]
