"""
Dynamic Risk Budget — regime-aware risk budget allocation.

Dynamically adjusts the risk budget based on:
    - Market regime (trending, high vol, risk-off, crisis)
    - Recent performance (drawdown scaling)
    - Volatility environment
    - Portfolio concentration level
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class RiskBudget:
    """Risk budget allocation."""
    id: str = field(default_factory=lambda: str(uuid4()))
    total_budget: float = 1.0
    strategy_allocation: dict[str, float] = field(default_factory=dict)
    factor_allocation: dict[str, float] = field(default_factory=dict)
    asset_allocation: dict[str, float] = field(default_factory=dict)
    regime: str = "NORMAL"
    regime_budget_scale: float = 1.0
    drawdown_scale: float = 1.0
    volatility_scale: float = 1.0
    concentration_penalty: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def effective_budget(self) -> float:
        """Effective risk budget after all adjustments."""
        return (
            self.total_budget
            * self.regime_budget_scale
            * self.drawdown_scale
            * self.volatility_scale
            * (1.0 - self.concentration_penalty)
        )


class DynamicRiskBudget:
    """
    Dynamic risk budget allocator.

    Principles:
        - Regime-aware: reduce risk in high-vol / crisis regimes
        - Drawdown-responsive: scale down as drawdown increases
        - Volatility-targeting: adjust for current market volatility
        - Concentration-aware: penalize over-concentrated portfolios

    Budget tiers:
        NORMAL: 100% budget
        HIGH_VOL: 60-70% budget
        RISK_OFF: 35-40% budget
        CRISIS: 15-25% budget
    """

    def __init__(self, base_budget: float = 1.0) -> None:
        self._base_budget = base_budget
        self._current_budget: Optional[RiskBudget] = None
        self._budget_history: list[RiskBudget] = []

    # ── Budget Regime Scaling ──────────────────────────────────

    def get_regime_scale(self, regime: str) -> float:
        """Get budget scaling factor for a given regime."""
        scales = {
            "NORMAL": 1.00,
            "TRENDING_UP": 0.90,
            "TRENDING_DOWN": 0.80,
            "HIGH_VOL_UP": 0.65,
            "HIGH_VOL_DOWN": 0.55,
            "MEAN_REVERTING": 0.75,
            "RISK_ON": 0.95,
            "RISK_OFF": 0.35,
            "CRISIS": 0.15,
            "LIQUIDITY_STRESS": 0.20,
        }
        return scales.get(regime, 0.60)

    def get_drawdown_scale(self, drawdown_pct: float) -> float:
        """Get budget scaling based on current drawdown."""
        if drawdown_pct <= 0.02:
            return 1.00
        elif drawdown_pct <= 0.05:
            return 0.85
        elif drawdown_pct <= 0.08:
            return 0.65
        elif drawdown_pct <= 0.10:
            return 0.45
        elif drawdown_pct <= 0.15:
            return 0.25
        else:
            return 0.10

    def get_volatility_scale(self, current_vol: float, target_vol: float = 0.15) -> float:
        """Scale budget to target volatility."""
        if current_vol <= 0:
            return 1.0
        scale = target_vol / current_vol
        return max(0.20, min(scale, 1.5))

    def get_concentration_penalty(self, hhi: float, top5_pct: float) -> float:
        """Penalize high concentration."""
        penalty = 0.0
        if hhi > 0.15:
            penalty += 0.10
        if hhi > 0.25:
            penalty += 0.10
        if top5_pct > 0.60:
            penalty += 0.10
        return min(penalty, 0.30)

    # ── Core Allocation ────────────────────────────────────────

    async def allocate(
        self,
        strategy_risks: dict[str, float],
        regime: str = "NORMAL",
        drawdown: float = 0.0,
        current_vol: float = 0.15,
        hhi: float = 0.10,
        top5_pct: float = 0.40,
    ) -> RiskBudget:
        """
        Compute dynamic risk budget allocation.

        Args:
            strategy_risks: {strategy_name: risk_contribution}
            regime: Current market regime
            drawdown: Current portfolio drawdown
            current_vol: Current portfolio volatility
            hhi: Herfindahl-Hirschman Index for concentration
            top5_pct: Top 5 positions as percentage

        Returns:
            RiskBudget with allocations
        """
        budget = RiskBudget(
            total_budget=self._base_budget,
            regime=regime,
            regime_budget_scale=self.get_regime_scale(regime),
            drawdown_scale=self.get_drawdown_scale(drawdown),
            volatility_scale=self.get_volatility_scale(current_vol),
            concentration_penalty=self.get_concentration_penalty(hhi, top5_pct),
        )

        # Allocate risk budget proportionally to strategy risk
        total_risk = sum(strategy_risks.values()) or 1.0
        budget.strategy_allocation = {
            name: (risk / total_risk) * budget.effective_budget
            for name, risk in strategy_risks.items()
        }

        budget.timestamp = datetime.now()
        self._current_budget = budget
        self._budget_history.append(budget)

        # Keep last 1000 records
        if len(self._budget_history) > 1000:
            self._budget_history = self._budget_history[-500:]

        logger.info(
            "Risk budget: total=%.2f effective=%.2f regime=%s drawdown_scale=%.2f",
            budget.total_budget, budget.effective_budget,
            regime, budget.drawdown_scale,
        )
        return budget

    # ── Query ──────────────────────────────────────────────────

    @property
    def current_budget(self) -> Optional[RiskBudget]:
        return self._current_budget

    def get_budget_history(self, limit: int = 20) -> list[RiskBudget]:
        return self._budget_history[-limit:]

    def get_effective_budget(self) -> float:
        if self._current_budget:
            return self._current_budget.effective_budget
        return self._base_budget
