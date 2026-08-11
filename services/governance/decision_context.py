"""
Decision Context — unified snapshot of system state for governance evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DecisionContext:
    """Complete context snapshot provided to governance for a single decision."""

    # ---- Capital ----
    capital: float = 0.0
    deployed_capital: float = 0.0
    available_capital: float = 0.0

    # ---- Portfolio ----
    portfolio_value: float = 0.0
    portfolio_count: int = 0
    strategy_allocations: Dict[str, float] = field(default_factory=dict)

    # ---- Risk ----
    current_risk: float = 0.0
    risk_budget_total: float = 0.0
    risk_budget_used: float = 0.0
    risk_budget_available: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    expected_shortfall: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0

    # ---- Factor ----
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    factor_concentration: Dict[str, float] = field(default_factory=dict)
    correlation_risk: float = 0.0

    # ---- Tail ----
    tail_risk_score: float = 0.0
    tail_dependence: float = 0.0

    # ---- Leverage ----
    current_leverage: float = 1.0
    max_leverage: float = 3.0

    # ---- Liquidity ----
    liquidity_score: float = 100.0
    market_liquidity: float = 1.0
    execution_capacity: float = 0.0

    # ---- Capacity ----
    strategy_capacity: Optional[float] = None
    market_capacity: Optional[float] = None

    # ---- Stress ----
    stress_loss: float = 0.0
    stress_drawdown: float = 0.0
    stress_survival_score: float = 100.0

    # ---- Survival ----
    survival_score: float = 100.0
    survival_horizon_days: float = 365.0
    capital_erosion_rate: float = 0.0
    recovery_capacity: float = 100.0

    # ---- Strategy ----
    strategy_id: Optional[str] = None
    strategy_score: float = 0.0
    strategy_alpha: float = 0.0
    strategy_sharpe: float = 0.0
    strategy_weight: float = 0.0

    # ---- Concentration ----
    max_single_strategy_weight: float = 0.25
    max_single_factor_weight: float = 0.35
    current_concentration: float = 0.0

    # ---- Market ----
    market_regime: str = "NORMAL"
    volatility_index: float = 0.0

    # ---- Actor ----
    actor: str = ""
    actor_autonomy_level: int = 0

    # ---- Governance State ----
    governance_enabled: bool = True
    emergency_mode: bool = False

    # ---- Extras ----
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a serializable dictionary."""
        return {
            "capital": self.capital,
            "deployed_capital": self.deployed_capital,
            "available_capital": self.available_capital,
            "portfolio_value": self.portfolio_value,
            "portfolio_count": self.portfolio_count,
            "strategy_allocations": self.strategy_allocations,
            "current_risk": self.current_risk,
            "risk_budget_total": self.risk_budget_total,
            "risk_budget_used": self.risk_budget_used,
            "risk_budget_available": self.risk_budget_available,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "expected_shortfall": self.expected_shortfall,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "factor_exposures": self.factor_exposures,
            "factor_concentration": self.factor_concentration,
            "correlation_risk": self.correlation_risk,
            "tail_risk_score": self.tail_risk_score,
            "tail_dependence": self.tail_dependence,
            "current_leverage": self.current_leverage,
            "max_leverage": self.max_leverage,
            "liquidity_score": self.liquidity_score,
            "market_liquidity": self.market_liquidity,
            "execution_capacity": self.execution_capacity,
            "strategy_capacity": self.strategy_capacity,
            "market_capacity": self.market_capacity,
            "stress_loss": self.stress_loss,
            "stress_drawdown": self.stress_drawdown,
            "stress_survival_score": self.stress_survival_score,
            "survival_score": self.survival_score,
            "survival_horizon_days": self.survival_horizon_days,
            "capital_erosion_rate": self.capital_erosion_rate,
            "recovery_capacity": self.recovery_capacity,
            "strategy_id": self.strategy_id,
            "strategy_score": self.strategy_score,
            "strategy_alpha": self.strategy_alpha,
            "strategy_sharpe": self.strategy_sharpe,
            "strategy_weight": self.strategy_weight,
            "max_single_strategy_weight": self.max_single_strategy_weight,
            "max_single_factor_weight": self.max_single_factor_weight,
            "current_concentration": self.current_concentration,
            "market_regime": self.market_regime,
            "volatility_index": self.volatility_index,
            "actor": self.actor,
            "actor_autonomy_level": self.actor_autonomy_level,
            "governance_enabled": self.governance_enabled,
            "emergency_mode": self.emergency_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionContext":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
