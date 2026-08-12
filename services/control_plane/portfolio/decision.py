"""
PortfolioControlDecision — the granular outcome of Portfolio Control
(Commit 26 Part 1.3, spec section 11).

Portfolio Control decides four capabilities:

    allow_new_risk       → may the portfolio increase overall risk?
    allow_new_orders     → may new orders be submitted under it?
    allow_reduce_orders  → may position-reducing orders be submitted?
    allow_liquidation    → may the portfolio be actively liquidated?
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import PortfolioState


@dataclass(frozen=True)
class PortfolioControlDecision:

    portfolio_id: str

    current_state: PortfolioState

    allow_new_risk: bool

    allow_new_orders: bool

    allow_reduce_orders: bool

    allow_liquidation: bool

    reason: str

    @property
    def allow_any_orders(self) -> bool:
        return self.allow_new_orders or self.allow_reduce_orders
