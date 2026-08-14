"""
Risk decision context factory.

Builds a ``RiskDecisionContext`` from an approved signal and the latest
account/position snapshots. This layer only transforms data; it never
mutates account or position state.
"""

from __future__ import annotations

from .decision_context import RiskDecisionContext


class RiskDecisionContextFactory:

    def build(
        self,
        signal,
        account_snapshot,
        position_snapshot,
    ) -> RiskDecisionContext:

        return RiskDecisionContext(
            account_id=account_snapshot.account_id,
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            instrument_id=signal.instrument_id,
            side=signal.side,
            quantity=signal.quantity,
            price=signal.price,
            available_cash=account_snapshot.available_cash,
            current_position=position_snapshot.quantity,
            daily_pnl=account_snapshot.daily_pnl,
            daily_loss_limit=account_snapshot.daily_loss_limit,
            max_position=account_snapshot.max_position,
            correlation_id=signal.correlation_id,
            causation_id=signal.event_id,
            lineage_id=signal.lineage_id,
        )
