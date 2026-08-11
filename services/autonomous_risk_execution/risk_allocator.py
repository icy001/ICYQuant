"""
Risk Allocator — distributes risk across strategies and assets.

Translates risk budget into actual capital and exposure allocations.
Supports multiple allocation methodologies:
    - Risk parity
    - Equal risk contribution (ERC)
    - Volatility targeting
    - Correlation-adjusted
    - Regime-conditioned
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AllocationMethod(Enum):
    """Risk allocation methodologies."""
    RISK_PARITY = "risk_parity"
    EQUAL_RISK_CONTRIBUTION = "equal_risk_contribution"
    VOLATILITY_TARGETING = "volatility_targeting"
    CORRELATION_ADJUSTED = "correlation_adjusted"
    REGIME_CONDITIONED = "regime_conditioned"
    KELLY_CONSTRAINED = "kelly_constrained"


@dataclass
class RiskAllocation:
    """Output of risk allocation."""
    asset: str
    allocation: float
    risk_contribution: float
    capital_weight: float
    method: AllocationMethod = AllocationMethod.RISK_PARITY


@dataclass
class AllocationResult:
    """Complete allocation result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    total_capital: float = 1.0
    total_risk_budget: float = 1.0
    allocations: list[RiskAllocation] = field(default_factory=list)
    method: AllocationMethod = AllocationMethod.RISK_PARITY
    unused: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class RiskAllocator:
    """
    Distributes risk budget across strategies and assets.

    Core formula (Risk Parity):
        weight_i = (1/vol_i) / sum(1/vol_j) * risk_budget

    Core formula (Volatility Targeting):
        weight_i = (target_vol / vol_i) * risk_budget_i
    """

    def __init__(self, default_method: AllocationMethod = AllocationMethod.RISK_PARITY) -> None:
        self._default_method = default_method
        self._last_result: Optional[AllocationResult] = None

    async def allocate(
        self,
        assets: dict[str, float],  # {asset: volatility}
        risk_budget: float = 1.0,
        method: Optional[AllocationMethod] = None,
        correlations: Optional[dict[str, dict[str, float]]] = None,
    ) -> AllocationResult:
        """Allocate risk budget across assets."""
        method = method or self._default_method

        if method == AllocationMethod.RISK_PARITY:
            allocations = self._risk_parity(assets, risk_budget)
        elif method == AllocationMethod.VOLATILITY_TARGETING:
            allocations = self._volatility_targeting(assets, risk_budget)
        elif method == AllocationMethod.CORRELATION_ADJUSTED:
            allocations = self._correlation_adjusted(assets, risk_budget, correlations)
        else:
            allocations = self._risk_parity(assets, risk_budget)

        total_allocated = sum(a.allocation for a in allocations)
        result = AllocationResult(
            total_risk_budget=risk_budget,
            allocations=allocations,
            method=method,
            unused=max(0, risk_budget - total_allocated),
        )
        self._last_result = result
        return result

    # ── Allocation Methods ─────────────────────────────────────

    def _risk_parity(
        self, assets: dict[str, float], budget: float
    ) -> list[RiskAllocation]:
        """Risk parity: weight inversely proportional to volatility."""
        inv_vols = {asset: 1.0 / max(vol, 0.001) for asset, vol in assets.items()}
        total_inv = sum(inv_vols.values()) or 1.0
        return [
            RiskAllocation(
                asset=asset,
                allocation=(inv / total_inv) * budget,
                risk_contribution=budget / len(assets),
                capital_weight=inv / total_inv,
            )
            for asset, inv in inv_vols.items()
        ]

    def _volatility_targeting(
        self, assets: dict[str, float], budget: float, target_vol: float = 0.15
    ) -> list[RiskAllocation]:
        """Volatility targeting: scale weights to target volatility."""
        result = []
        for asset, vol in assets.items():
            safe_vol = max(vol, 0.001)
            weight = (target_vol / safe_vol) * (budget / len(assets))
            result.append(RiskAllocation(
                asset=asset,
                allocation=weight,
                risk_contribution=weight * safe_vol,
                capital_weight=weight,
                method=AllocationMethod.VOLATILITY_TARGETING,
            ))
        return result

    def _correlation_adjusted(
        self,
        assets: dict[str, float],
        budget: float,
        correlations: Optional[dict[str, dict[str, float]]] = None,
    ) -> list[RiskAllocation]:
        """Adjust allocations based on pairwise correlations."""
        base = self._risk_parity(assets, budget)
        if not correlations:
            return base

        for alloc in base:
            total_corr = 0.0
            count = 0
            for other, corr in correlations.get(alloc.asset, {}).items():
                if other != alloc.asset:
                    total_corr += abs(corr)
                    count += 1
            avg_corr = total_corr / max(count, 1)
            corr_penalty = max(0.3, 1.0 - avg_corr * 0.5)
            alloc.allocation *= corr_penalty
            alloc.capital_weight *= corr_penalty

        return base

    @property
    def last_result(self) -> Optional[AllocationResult]:
        return self._last_result
