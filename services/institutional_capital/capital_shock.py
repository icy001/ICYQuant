"""
Capital Shock — Simulates single-strategy shock events and cascade effects.

Example:
    Strategy A Return -20%
    → Observe: Portfolio, Capital, Risk, Liquidity
    → Determine: Reallocation needed?
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ShockType(str, Enum):
    RETURN_SHOCK = "return_shock"
    VOLATILITY_SHOCK = "volatility_shock"
    DRAWDOWN_SHOCK = "drawdown_shock"
    CAPACITY_SHOCK = "capacity_shock"
    CORRELATION_SHOCK = "correlation_shock"


class ShockPropagation(str, Enum):
    ISOLATED = "isolated"       # Only affects the shocked strategy
    CONTAGION = "contagion"     # Spills over to correlated strategies
    SYSTEMIC = "systemic"       # Affects entire portfolio


@dataclass
class StrategyShock:
    """A shock event applied to a specific strategy."""

    shock_id: str = field(default_factory=lambda: f"SH-{uuid.uuid4().hex[:8]}")
    name: str = ""
    strategy_id: str = ""
    shock_type: ShockType = ShockType.RETURN_SHOCK
    magnitude: float = 0.0            # e.g. -0.20 = -20% return shock
    propagation: ShockPropagation = ShockPropagation.ISOLATED
    propagation_decay: float = 0.5    # how much spills to correlated strategies
    duration_days: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shock_id": self.shock_id,
            "name": self.name,
            "strategy_id": self.strategy_id,
            "type": self.shock_type.value,
            "magnitude": self.magnitude,
            "propagation": self.propagation.value,
        }


@dataclass
class ShockResult:
    """Outcome of applying a strategy shock."""

    shock_id: str = ""
    shock_name: str = ""
    strategy_id: str = ""

    # Direct impact on the shocked strategy
    strategy_return_impact: float = 0.0
    strategy_risk_impact: float = 0.0
    strategy_drawdown_impact: float = 0.0

    # Portfolio impact
    portfolio_return_impact: float = 0.0
    portfolio_risk_impact: float = 0.0
    portfolio_drawdown_impact: float = 0.0

    # Capital impact
    capital_impact: float = 0.0
    capital_impact_pct: float = 0.0

    # Contagion
    correlated_strategies_impacted: List[str] = field(default_factory=list)
    contagion_loss: float = 0.0

    # Decision
    reallocation_needed: bool = False
    stop_strategy: bool = False
    reduce_capital: bool = False
    recommended_action: str = "HOLD"

    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shock_id": self.shock_id,
            "shock_name": self.shock_name,
            "strategy_id": self.strategy_id,
            "portfolio_return_impact": self.portfolio_return_impact,
            "portfolio_risk_impact": self.portfolio_risk_impact,
            "capital_impact_pct": self.capital_impact_pct,
            "reallocation_needed": self.reallocation_needed,
            "recommended_action": self.recommended_action,
        }


class ShockSimulator:
    """Simulates strategy-level shocks and cascade effects."""

    def __init__(self):
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        self._strategy_weights: Dict[str, float] = {}
        self._total_capital: float = 0.0

    def set_correlation_matrix(self, matrix: Dict[str, Dict[str, float]]) -> None:
        self._correlation_matrix = matrix

    def set_strategy_weights(self, weights: Dict[str, float]) -> None:
        self._strategy_weights = weights

    def set_total_capital(self, total: float) -> None:
        self._total_capital = total

    def simulate(self, shock: StrategyShock) -> ShockResult:
        """Simulate a strategy shock and measure impact."""
        result = ShockResult(
            shock_id=shock.shock_id,
            shock_name=shock.name,
            strategy_id=shock.strategy_id,
        )

        weight = self._strategy_weights.get(shock.strategy_id, 0.0)
        strategy_capital = self._total_capital * weight

        # Direct impact
        if shock.shock_type == ShockType.RETURN_SHOCK:
            result.strategy_return_impact = shock.magnitude
            result.capital_impact = strategy_capital * shock.magnitude
            result.strategy_drawdown_impact = abs(shock.magnitude) * 0.7
        elif shock.shock_type == ShockType.VOLATILITY_SHOCK:
            result.strategy_risk_impact = shock.magnitude
            result.capital_impact = strategy_capital * abs(shock.magnitude) * 0.1
        elif shock.shock_type == ShockType.DRAWDOWN_SHOCK:
            result.strategy_drawdown_impact = shock.magnitude
            result.capital_impact = strategy_capital * shock.magnitude

        result.capital_impact_pct = result.capital_impact / max(self._total_capital, 1.0)

        # Portfolio-level impact
        result.portfolio_return_impact = result.strategy_return_impact * weight
        result.portfolio_risk_impact = result.strategy_risk_impact * weight * 1.5
        result.portfolio_drawdown_impact = result.strategy_drawdown_impact * weight

        # Contagion to correlated strategies
        if shock.propagation in (ShockPropagation.CONTAGION, ShockPropagation.SYSTEMIC):
            corr_row = self._correlation_matrix.get(shock.strategy_id, {})
            for sid, corr in corr_row.items():
                if sid == shock.strategy_id:
                    continue
                if corr > 0.5:
                    spill = result.strategy_return_impact * corr * shock.propagation_decay
                    result.contagion_loss += abs(spill) * self._strategy_weights.get(sid, 0) * self._total_capital
                    result.correlated_strategies_impacted.append(sid)

        # Decision logic
        total_loss_pct = (result.capital_impact + result.contagion_loss) / max(self._total_capital, 1.0)

        if total_loss_pct > 0.10 or abs(result.strategy_return_impact) > 0.30:
            result.stop_strategy = True
            result.recommended_action = "QUARANTINE"
            result.warnings.append(f"Strategy {shock.strategy_id} should be quarantined")
        elif total_loss_pct > 0.05:
            result.reduce_capital = True
            result.recommended_action = "REDUCE"
            result.warnings.append(f"Reduce capital allocation to {shock.strategy_id}")
        elif total_loss_pct > 0.02:
            result.reallocation_needed = True
            result.recommended_action = "REALLOCATE"
        else:
            result.recommended_action = "HOLD"

        return result

    def batch_simulate(self, shocks: List[StrategyShock]) -> List[ShockResult]:
        return [self.simulate(s) for s in shocks]
