"""
StrategyPortfolioControlResolver — merge Portfolio × Strategy into a single
effective control (Commit 26 Part 1.3, spec sections 14–17).

Control hierarchy:

    Portfolio Control
          ↓
    Strategy Control
          ↓
    Order Admission

The most restrictive layer always wins (AND semantics).  For example:

    Portfolio = REDUCE_ONLY
    Strategy  = RUNNING
    ──────────────────────────────────
    Signal Generation     ✅
    New Order             ❌
    Reduce                ✅
"""

from __future__ import annotations

from ..portfolio.decision import PortfolioControlDecision
from ..strategy.decision import StrategyControlDecision
from .model import EffectiveStrategyControl


class StrategyPortfolioControlResolver:

    def resolve(
        self,
        strategy_decision: StrategyControlDecision,
        portfolio_decision: PortfolioControlDecision,
    ) -> EffectiveStrategyControl:

        return EffectiveStrategyControl(
            strategy_id=(
                strategy_decision.strategy_id
            ),
            portfolio_id=(
                portfolio_decision.portfolio_id
            ),
            allow_signal_generation=(
                strategy_decision
                .allow_signal_generation
                and portfolio_decision
                .allow_new_risk
            ),
            allow_new_risk=(
                portfolio_decision
                .allow_new_risk
                and strategy_decision
                .allow_new_orders
            ),
            allow_new_orders=(
                portfolio_decision
                .allow_new_orders
                and strategy_decision
                .allow_new_orders
            ),
            allow_reduce_orders=(
                portfolio_decision
                .allow_reduce_orders
                and strategy_decision
                .allow_reduce_orders
            ),
            allow_liquidation=(
                portfolio_decision
                .allow_liquidation
            ),
            reason=(
                f"portfolio="
                f"{portfolio_decision.reason};"
                f"strategy="
                f"{strategy_decision.reason}"
            ),
        )
