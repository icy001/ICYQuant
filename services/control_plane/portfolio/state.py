"""
PortfolioState — the state model of a portfolio under Institutional Control
(Commit 26 Part 1.3, spec section 10).

A portfolio is one level above strategy: if the portfolio's risk posture is
compromised, every strategy underneath it is constrained.  States form the
hierarchical risk-contraction path:

    Normal → Restricted → Reduce Only → Draining → Liquidating → Flattened

``RECOVERING`` is the explicit transition state used while a portfolio is
being brought back under control after an incident — fail-closed by default
until an authorized operator returns the portfolio to ACTIVE.
"""

from __future__ import annotations

from enum import Enum


class PortfolioState(str, Enum):

    ACTIVE = "ACTIVE"

    RESTRICTED = "RESTRICTED"

    REDUCE_ONLY = "REDUCE_ONLY"

    FROZEN = "FROZEN"

    LIQUIDATING = "LIQUIDATING"

    RECOVERING = "RECOVERING"

    @property
    def risk_reduction_stage(self) -> int:
        """0=active ... 5=liquidating — higher is more restrictive."""
        if self is PortfolioState.ACTIVE:
            return 0
        if self is PortfolioState.RESTRICTED:
            return 1
        if self is PortfolioState.REDUCE_ONLY:
            return 2
        if self is PortfolioState.FROZEN:
            return 3
        if self is PortfolioState.LIQUIDATING:
            return 5
        return 4  # RECOVERING
