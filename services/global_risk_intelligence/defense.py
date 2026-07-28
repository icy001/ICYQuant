"""Auto Defense Engine.

Triggers automatic protective actions when risk exceeds thresholds:
reduce positions, lower leverage, pause strategies, increase hedges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DefenseLevel(str, Enum):
    """Defense posture levels."""

    NONE = "none"
    CAUTIOUS = "cautious"
    DEFENSIVE = "defensive"
    PROTECTIVE = "protective"
    FULL_DEFENSE = "full_defense"


class DefenseAction(str, Enum):
    """Auto-defense actions."""

    REDUCE_POSITION = "reduce_position"
    LOWER_LEVERAGE = "lower_leverage"
    PAUSE_STRATEGY = "pause_strategy"
    INCREASE_HEDGE = "increase_hedge"
    RAISE_CASH = "raise_cash"
    STOP_TRADING = "stop_trading"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class DefenseOrder:
    """An auto-generated defensive order.

    Attributes:
        action: Defensive action type.
        target: Target of the action.
        current_value: Current value/ratio.
        target_value: Desired value/ratio.
        urgency: Urgency score [0, 1].
        reason: Human-readable justification.
    """

    action: DefenseAction = DefenseAction.REDUCE_POSITION
    target: str = "portfolio"
    current_value: float = 0.0
    target_value: float = 0.0
    urgency: float = 0.0
    reason: str = ""

    @property
    def delta_pct(self) -> float:
        return abs(self.current_value - self.target_value) / max(self.current_value, 0.01) * 100


@dataclass
class DefenseDecision:
    """Complete auto-defense decision.

    Attributes:
        level: Determined defense level.
        orders: Generated defensive orders.
        pos_pct_target: Target position percentage.
        leverage_target: Target leverage.
        hedge_pct_target: Target hedge percentage.
        cash_pct_target: Target cash allocation.
        description: Human-readable summary.
        timestamp: Decision timestamp.
    """

    level: DefenseLevel = DefenseLevel.NONE
    orders: list[DefenseOrder] = field(default_factory=list)
    pos_pct_target: float = 100.0
    leverage_target: float = 1.0
    hedge_pct_target: float = 0.0
    cash_pct_target: float = 0.05
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def requires_action(self) -> bool:
        return len(self.orders) > 0

    @property
    def critical_orders(self) -> list[DefenseOrder]:
        return [o for o in self.orders if o.urgency >= 0.7]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AutoDefenseEngine:
    """Automatically decides defensive actions based on risk levels.

    Evaluates risk inputs and generates specific defensive orders
    for position reduction, leverage adjustment, strategy pausing,
    and hedge increases.

    Attributes:
        DEFENSE_PARAMS: Configuration per defense level.
    """

    DEFENSE_PARAMS: dict[DefenseLevel, dict[str, Any]] = {
        DefenseLevel.NONE: {
            "reduce_position": False,
            "hedge": False,
            "leverage_limit": 2.0,
            "position_limit": 0.25,
            "cash_target": 0.05,
            "hedge_target": 0.0,
            "pause": False,
        },
        DefenseLevel.CAUTIOUS: {
            "reduce_position": False,
            "hedge": False,
            "leverage_limit": 1.5,
            "position_limit": 0.20,
            "cash_target": 0.10,
            "hedge_target": 0.05,
            "pause": False,
        },
        DefenseLevel.DEFENSIVE: {
            "reduce_position": True,
            "hedge": True,
            "leverage_limit": 1.0,
            "position_limit": 0.15,
            "cash_target": 0.20,
            "hedge_target": 0.10,
            "pause": False,
        },
        DefenseLevel.PROTECTIVE: {
            "reduce_position": True,
            "hedge": True,
            "leverage_limit": 0.5,
            "position_limit": 0.08,
            "cash_target": 0.35,
            "hedge_target": 0.20,
            "pause": True,
        },
        DefenseLevel.FULL_DEFENSE: {
            "reduce_position": True,
            "hedge": True,
            "leverage_limit": 0.0,
            "position_limit": 0.03,
            "cash_target": 0.60,
            "hedge_target": 0.30,
            "pause": True,
        },
    }

    def __init__(self,
                 current_position: float = 1.0,
                 current_leverage: float = 1.0,
                 current_hedge: float = 0.0,
                 current_cash: float = 0.05) -> None:
        self.current_position = current_position
        self.current_leverage = current_leverage
        self.current_hedge = current_hedge
        self.current_cash = current_cash

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def decide(self, risk_level: str,
               systemic_score: float = 0.0,
               vol_regime: str = "normal_vol",
               liquidity_level: str = "normal",
               current_drawdown: float = 0.0,
               ) -> DefenseDecision:
        """Determine defense posture and generate orders.

        Args:
            risk_level: Overall risk level (normal/warning/critical).
            systemic_score: Systemic risk score [0, 1].
            vol_regime: Volatility regime label.
            liquidity_level: Liquidity condition.
            current_drawdown: Current portfolio drawdown.

        Returns:
            DefenseDecision with specific orders.
        """
        # Determine defense level
        level = self._determine_level(
            risk_level, systemic_score, vol_regime,
            liquidity_level, current_drawdown,
        )
        params = self.DEFENSE_PARAMS[level]
        orders: list[DefenseOrder] = []

        # Position adjustment
        if params["reduce_position"]:
            orders.append(DefenseOrder(
                action=DefenseAction.REDUCE_POSITION,
                target="portfolio",
                current_value=self.current_position * 100,
                target_value=params["position_limit"] * 100,
                urgency=min(1.0, systemic_score * 1.5),
                reason=f"Risk level {risk_level} requires position reduction",
            ))

        # Leverage adjustment
        if self.current_leverage > params["leverage_limit"]:
            orders.append(DefenseOrder(
                action=DefenseAction.LOWER_LEVERAGE,
                target="portfolio",
                current_value=self.current_leverage,
                target_value=params["leverage_limit"],
                urgency=min(1.0, (self.current_leverage - params["leverage_limit"]) / 2),
                reason=f"Leverage ({self.current_leverage:.1f}x) exceeds limit ({params['leverage_limit']:.1f}x)",
            ))

        # Hedge increase
        if params["hedge"] and self.current_hedge < params["hedge_target"]:
            orders.append(DefenseOrder(
                action=DefenseAction.INCREASE_HEDGE,
                target="portfolio",
                current_value=self.current_hedge * 100,
                target_value=params["hedge_target"] * 100,
                urgency=min(1.0, systemic_score),
                reason=f"Increase hedge from {self.current_hedge:.0%} to {params['hedge_target']:.0%}",
            ))

        # Cash target
        if self.current_cash < params["cash_target"]:
            orders.append(DefenseOrder(
                action=DefenseAction.RAISE_CASH,
                target="portfolio",
                current_value=self.current_cash * 100,
                target_value=params["cash_target"] * 100,
                urgency=min(1.0, (params["cash_target"] - self.current_cash) * 3),
                reason=f"Raise cash buffer to {params['cash_target']:.0%}",
            ))

        # Pause strategies
        if params["pause"]:
            orders.append(DefenseOrder(
                action=DefenseAction.PAUSE_STRATEGY,
                target="all_strategies",
                urgency=0.9,
                reason=f"Risk critical — trading suspended",
            ))

        # Full defense: stop trading
        if level == DefenseLevel.FULL_DEFENSE:
            orders.append(DefenseOrder(
                action=DefenseAction.STOP_TRADING,
                target="all_strategies",
                urgency=1.0,
                reason="Full defense activated — stop all trading",
            ))

        description = self._describe(level, orders, risk_level)

        return DefenseDecision(
            level=level,
            orders=orders,
            pos_pct_target=params["position_limit"] * 100,
            leverage_target=params["leverage_limit"],
            hedge_pct_target=params["hedge_target"] * 100,
            cash_pct_target=params["cash_target"] * 100,
            description=description,
        )

    # ------------------------------------------------------------------
    # Level determination
    # ------------------------------------------------------------------

    def _determine_level(self, risk_level: str, systemic_score: float,
                         vol_regime: str, liquidity_level: str,
                         drawdown: float) -> DefenseLevel:
        """Determine defense posture from multi-factor inputs."""
        score = 0.0

        # Risk level
        risk_scores = {"critical": 3.0, "warning": 1.5, "normal": 0.0}
        score += risk_scores.get(risk_level, 0.0)

        # Systemic risk
        if systemic_score >= 0.6:
            score += 2.5
        elif systemic_score >= 0.4:
            score += 1.5

        # Volatility regime
        vol_scores = {
            "crisis_vol": 3.0, "high_vol": 2.0,
            "normal_vol": 0.0, "low_vol": 0.0,
        }
        score += vol_scores.get(vol_regime, 0.0)

        # Liquidity
        liq_scores = {
            "freeze": 3.0, "stressed": 2.0,
            "tight": 1.0, "normal": 0.0, "ample": 0.0,
        }
        score += liq_scores.get(liquidity_level, 0.0)

        # Drawdown
        if drawdown >= 0.20:
            score += 2.5
        elif drawdown >= 0.10:
            score += 1.5

        if score >= 8.0:
            return DefenseLevel.FULL_DEFENSE
        elif score >= 6.0:
            return DefenseLevel.PROTECTIVE
        elif score >= 4.0:
            return DefenseLevel.DEFENSIVE
        elif score >= 2.0:
            return DefenseLevel.CAUTIOUS
        return DefenseLevel.NONE

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------

    def _describe(self, level: DefenseLevel,
                  orders: list[DefenseOrder],
                  risk_level: str) -> str:
        actions = [o.action.value for o in orders]
        if not actions:
            return f"Defense: {level.value} — no action required"
        return (f"Defense: {level.value} — risk={risk_level}. "
                f"Actions: {', '.join(actions)}")
