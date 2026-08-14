"""
Risk decision context.

The context captures everything a single risk evaluation needs to know
about a trading request. The Risk domain only *reads* the context; it never
mutates account, position, order, or execution state directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..context_snapshot import RiskDecisionContextSnapshot


@dataclass(frozen=True)
class RiskDecisionContext:
    account_id: str
    strategy_id: str
    signal_id: str
    instrument_id: str

    side: str
    quantity: Decimal
    price: Decimal

    available_cash: Decimal
    current_position: Decimal

    daily_pnl: Decimal
    daily_loss_limit: Decimal

    max_position: Decimal

    correlation_id: str | None = None
    causation_id: str | None = None
    lineage_id: str | None = None

    @classmethod
    def from_snapshot(
        cls,
        snapshot: "RiskDecisionContextSnapshot",
    ) -> "RiskDecisionContext":
        """Rebuild the historical context captured in a snapshot.

        This is the deterministic entry point used by decision replay: the
        context is reconstructed from the frozen decision-time inputs rather
        than from current market / account state.
        """
        return snapshot.to_context()
