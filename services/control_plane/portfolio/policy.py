"""
PortfolioControlPolicy — the configurable knobs of Portfolio Control
(Commit 26 Part 1.3, spec section 12).

Defaults encode the fail-safe principle: every non-ACTIVE state blocks new
risk and new orders, while keeping the position-reduction and liquidation
channels open so the portfolio can always wind down existing risk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioControlPolicy:

    restricted_allow_new_risk: bool = False

    restricted_allow_new_orders: bool = False

    restricted_allow_reduce: bool = True

    reduce_only_allow_reduce: bool = True

    frozen_allow_reduce: bool = True

    liquidating_allow_reduce: bool = True
