"""VolatilityShock — volatility spike simulation.

Simulates sudden volatility increases and their impact on
VaR, ES, margin requirements, and position sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VolatilityShockResult:
    """Result of a volatility shock simulation."""

    vol_increase_pct: float = 0.0
    original_vol: float = 0.0
    shocked_vol: float = 0.0
    var_increase_pct: float = 0.0
    es_increase_pct: float = 0.0
    margin_requirement_increase_pct: float = 0.0
    position_size_reduction_pct: float = 0.0
    risk_budget_consumed_pct: float = 0.0
    needs_rebalancing: bool = False


class VolatilityShockSimulator:
    """Simulates volatility spike impacts.

    Usage::

        sim = VolatilityShockSimulator()
        result = sim.simulate(
            vol_increase_pct=100.0,  # vol doubles
            current_var=8_000_000,
            risk_budget=10_000_000,
            current_vol=0.15,
        )
        if result.needs_rebalancing:
            print(f"Reduce positions by {result.position_size_reduction_pct:.0f}%")
    """

    def __init__(self, target_risk_ratio: float = 1.0):
        self._target_risk_ratio = target_risk_ratio

    def simulate(
        self,
        vol_increase_pct: float,
        current_var: float,
        risk_budget: float,
        current_vol: float = 0.15,
        current_es: Optional[float] = None,
    ) -> VolatilityShockResult:
        """Simulate a volatility shock.

        Args:
            vol_increase_pct: volatility increase percentage (e.g., 100 = doubled)
            current_var: current VaR (99%)
            risk_budget: total risk budget
            current_vol: current annualized volatility
            current_es: current Expected Shortfall (defaults to 1.3x VaR)
        """
        vol_multiplier = 1.0 + vol_increase_pct / 100.0
        shocked_vol = current_vol * vol_multiplier

        # VaR scales linearly with vol
        new_var = current_var * vol_multiplier
        var_increase = (new_var - current_var) / max(current_var, 1e-9) * 100

        # ES scales similarly (slightly more)
        current_es_val = current_es if current_es else current_var * 1.3
        new_es = current_es_val * vol_multiplier
        es_increase = (new_es - current_es_val) / max(current_es_val, 1e-9) * 100

        # margin requirement (roughly proportional to VaR)
        margin_increase = var_increase

        # position size reduction to maintain risk budget
        reduction_pct = 0.0
        if new_var > risk_budget * self._target_risk_ratio:
            reduction_pct = (1.0 - risk_budget / max(new_var, 1e-9)) * 100

        # risk budget consumption
        budget_consumed = (new_var / max(risk_budget, 1e-9)) * 100

        needs_rebalance = reduction_pct > 5.0

        return VolatilityShockResult(
            vol_increase_pct=vol_increase_pct,
            original_vol=current_vol,
            shocked_vol=shocked_vol,
            var_increase_pct=var_increase,
            es_increase_pct=es_increase,
            margin_requirement_increase_pct=margin_increase,
            position_size_reduction_pct=reduction_pct,
            risk_budget_consumed_pct=budget_consumed,
            needs_rebalancing=needs_rebalance,
        )

    def compute_required_position_reduction(
        self,
        current_leverage: float,
        vol_increase_pct: float,
        target_var: Optional[float] = None,
        current_var: Optional[float] = None,
    ) -> float:
        """Compute reduction needed to maintain risk target."""
        vol_factor = 1.0 + vol_increase_pct / 100.0
        new_leverage = current_leverage / vol_factor

        if target_var and current_var:
            new_var = current_var * vol_factor
            if new_var > target_var:
                scale = target_var / new_var
                new_leverage *= scale

        reduction = (1.0 - new_leverage / max(current_leverage, 1e-9)) * 100
        return max(0.0, reduction)
