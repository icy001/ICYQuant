"""
StrategyControlDecision — the granular outcome of Strategy Control
(Commit 26 Part 1.3, spec section 4).

Strategy Control is no longer a single ``enabled = true / false`` flag.
It directly decides three distinct capabilities:

    allow_signal_generation → may the Signal Generator produce new signals?
    allow_new_orders        → may new orders be submitted?
    allow_reduce_orders     → may position-reducing orders be submitted?
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import StrategyState


@dataclass(frozen=True)
class StrategyControlDecision:

    strategy_id: str

    current_state: StrategyState

    allow_signal_generation: bool

    allow_new_orders: bool

    allow_reduce_orders: bool

    reason: str

    @property
    def allow_any_orders(self) -> bool:
        return self.allow_new_orders or self.allow_reduce_orders
