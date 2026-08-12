"""
EffectiveStrategyControl — the merged control outcome of Portfolio × Strategy
(Commit 26 Part 1.3, spec sections 15–16).

Portfolio Control cannot be bypassed by Strategy Control, so the effective
decision is the AND-combination of both layers:

    Effective New Order
    = Portfolio Allow AND Strategy Allow AND Risk Allow AND Gateway Allow
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectiveStrategyControl:

    strategy_id: str

    portfolio_id: str

    allow_signal_generation: bool

    allow_new_risk: bool

    allow_new_orders: bool

    allow_reduce_orders: bool

    allow_liquidation: bool

    reason: str

    @property
    def allow_any_orders(self) -> bool:
        return self.allow_new_orders or self.allow_reduce_orders
