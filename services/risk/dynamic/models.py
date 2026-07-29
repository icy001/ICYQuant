"""Dynamic Risk Management - data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class RiskLevel(str, Enum):
    """Portfolio risk level classification."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAction(str, Enum):
    """Actions triggered by risk decisions."""
    NONE = "NONE"
    REDUCE_POSITION = "REDUCE_POSITION"
    HEDGE = "HEDGE"
    EXIT_POSITION = "EXIT_POSITION"
    STOP_TRADING = "STOP_TRADING"


class MarketRegime(str, Enum):
    """Market regime classification."""
    NORMAL = "NORMAL"
    HIGH_VOL = "HIGH_VOL"
    CRISIS = "CRISIS"
    RECOVERY = "RECOVERY"
    BUBBLE = "BUBBLE"


class StressSeverity(str, Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"


@dataclass
class RiskSnapshot:
    """A point-in-time risk snapshot of the portfolio."""

    portfolio_id: str
    timestamp: datetime
    volatility: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    drawdown: float
    max_drawdown: float
    exposure: Dict[str, float]
    concentration_ratio: float
    sharpe_ratio: float
    risk_level: RiskLevel
    market_regime: MarketRegime
    position_count: int = 0
    leverage: float = 1.0

    def to_dict(self) -> dict:
        return {
            "portfolio": self.portfolio_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "risk": {
                "volatility": round(self.volatility, 4),
                "var_95": round(self.var_95, 4),
                "var_99": round(self.var_99, 4),
                "cvar_95": round(self.cvar_95, 4),
                "cvar_99": round(self.cvar_99, 4),
                "drawdown": round(self.drawdown, 4),
                "max_drawdown": round(self.max_drawdown, 4),
            },
            "exposure": self.exposure,
            "concentration_ratio": round(self.concentration_ratio, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "risk_level": self.risk_level.value,
            "market_regime": self.market_regime.value,
        }


@dataclass
class PositionRisk:
    """Risk metrics for a single position."""

    symbol: str
    weight: float
    notional: float
    volatility: float
    var_95: float
    cvar_95: float
    marginal_risk: float
    risk_contribution_pct: float
    beta: float = 1.0
    correlation_to_portfolio: float = 0.7

    def risk_score(self) -> float:
        return self.risk_contribution_pct * self.volatility * (abs(self.beta) + 0.5)


@dataclass
class RiskDecision:
    """A risk-based decision for the portfolio."""

    decision_id: str
    portfolio_id: str
    timestamp: datetime
    risk_snapshot: RiskSnapshot
    action: RiskAction
    target_exposure: Dict[str, float]
    position_adjustments: List[Dict[str, float]]
    reason: str
    urgency: int  # 1-10 scale
    reduction_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "portfolio_id": self.portfolio_id,
            "action": self.action.value,
            "reason": self.reason,
            "target_exposure": self.target_exposure,
            "position_adjustments": self.position_adjustments,
            "reduction_pct": self.reduction_pct,
            "urgency": self.urgency,
        }


@dataclass
class RiskThresholds:
    """Configurable risk thresholds."""

    max_volatility: float = 0.30
    max_var_95: float = 0.05
    max_cvar_95: float = 0.08
    max_drawdown: float = 0.20
    max_concentration: float = 0.40
    min_sharpe: float = -1.0
    target_volatility: float = 0.15

    volatility_high: float = 0.25
    volatility_critical: float = 0.40
    drawdown_elevated: float = 0.10
    drawdown_high: float = 0.15
    drawdown_critical: float = 0.25
    var_elevated: float = 0.03
    var_high: float = 0.05
    var_critical: float = 0.08


@dataclass
class StressScenario:
    """A stress test scenario definition."""

    name: str
    description: str
    severity: StressSeverity
    market_shock: Dict[str, float]  # asset -> shock %
    volatility_multiplier: float = 1.0
    correlation_shift: float = 0.0
    liquidity_discount: float = 0.0
    duration_days: int = 1


@dataclass
class StressResult:
    """Result of a stress test simulation."""

    scenario_name: str
    portfolio_id: str
    initial_value: float
    stressed_value: float
    loss_pct: float
    loss_amount: float
    worst_asset: str
    worst_asset_loss: float
    action_required: RiskAction
    post_stress_exposure: Dict[str, float]


@dataclass
class MarketRegimeSnapshot:
    """Current market regime assessment."""

    regime: MarketRegime
    confidence: float
    indicators: Dict[str, float]
    transition_probability: Dict[str, float]

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 2),
            "indicators": self.indicators,
            "transition_probability": self.transition_probability,
        }
