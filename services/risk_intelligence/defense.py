"""Portfolio Defense Automation.

Automatically generates and executes defensive portfolio adjustments
in response to detected risks. Provides hedging strategies, position
sizing rules, and drawdown-control mechanisms for institutional
portfolio protection.
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
    """Portfolio defense posture level."""

    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    FULL = "full"


class HedgeInstrument(str, Enum):
    """Instruments available for hedging."""

    VIX_FUTURES = "vix_futures"
    VIX_CALLS = "vix_calls"
    PUT_OPTIONS = "put_options"
    INVERSE_ETF = "inverse_etf"
    TREASURY_BONDS = "treasury_bonds"
    GOLD = "gold"
    CASH = "cash"
    USD = "usd"
    JPY = "jpy"
    CHF = "chf"


class DefenseActionType(str, Enum):
    """Type of defensive action."""

    REDUCE_EXPOSURE = "reduce_exposure"
    ADD_HEDGE = "add_hedge"
    INCREASE_CASH = "increase_cash"
    REDUCE_LEVERAGE = "reduce_leverage"
    ROTATE_DEFENSIVE = "rotate_defensive"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    POSITION_LIMIT = "position_limit"
    CORRELATION_HEDGE = "correlation_hedge"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class DefenseAction:
    """A single defensive portfolio adjustment.

    Attributes:
        action_type: Type of defensive action.
        target_asset: Asset or asset class to adjust.
        current_allocation: Current allocation percentage.
        target_allocation: Target allocation percentage.
        hedge_instrument: Recommended hedge instrument.
        hedge_ratio: Hedge ratio (0-1).
        stop_loss_level: Stop-loss price level.
        priority: Execution priority (1=highest).
        reason: Rationale for the action.
        urgency: Urgency score [0.0, 1.0].
    """

    action_type: DefenseActionType = DefenseActionType.REDUCE_EXPOSURE
    target_asset: str = ""
    current_allocation: float = 0.0
    target_allocation: float = 0.0
    hedge_instrument: HedgeInstrument | None = None
    hedge_ratio: float = 0.0
    stop_loss_level: float = 0.0
    priority: int = 5
    reason: str = ""
    urgency: float = 0.0

    @property
    def delta_bps(self) -> float:
        """Allocation change in basis points."""
        return abs(self.target_allocation - self.current_allocation) * 10000

    @property
    def is_critical(self) -> bool:
        return self.priority == 1


@dataclass
class DefensePlan:
    """A complete portfolio defense plan.

    Attributes:
        defense_level: Overall defense posture.
        actions: Ordered list of defensive actions.
        target_cash: Target cash allocation.
        hedge_budget: Percentage of portfolio to allocate to hedges.
        max_drawdown_limit: Maximum acceptable drawdown.
        expected_impact: Expected P&L impact of hedging.
        description: Human-readable plan summary.
        generated_at: Plan generation timestamp.
    """

    defense_level: DefenseLevel = DefenseLevel.NONE
    actions: list[DefenseAction] = field(default_factory=list)
    target_cash: float = 0.05  # 5% cash
    hedge_budget: float = 0.0
    max_drawdown_limit: float = 0.20
    expected_impact: float = 0.0
    description: str = ""
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def is_defensive(self) -> bool:
        return self.defense_level != DefenseLevel.NONE

    @property
    def critical_actions(self) -> list[DefenseAction]:
        return [a for a in self.actions if a.is_critical]

    @property
    def total_allocation_change(self) -> float:
        return sum(a.delta_bps for a in self.actions) / 10000

    def sorted_actions(self) -> list[DefenseAction]:
        return sorted(self.actions, key=lambda a: a.priority)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class PortfolioDefenseAutomation:
    """Automates portfolio defense based on risk intelligence signals.

    Generates defense plans with specific hedging actions, position
    sizing rules, and drawdown controls based on multi-source risk
    inputs including systemic risk, crisis warnings, and volatility
    regime predictions.

    Attributes:
        max_portfolio_leverage: Maximum allowed leverage.
        max_single_position: Maximum single position size (fraction).
        min_cash_buffer: Minimum cash buffer for liquidity.
    """

    # Defense rule templates by level
    DEFENSE_RULES: dict[DefenseLevel, dict[str, float]] = {
        DefenseLevel.NONE: {
            "target_cash": 0.05,
            "hedge_budget": 0.0,
            "max_leverage": 2.0,
            "max_position": 0.25,
            "drawdown_limit": 0.25,
        },
        DefenseLevel.LIGHT: {
            "target_cash": 0.10,
            "hedge_budget": 0.05,
            "max_leverage": 1.5,
            "max_position": 0.20,
            "drawdown_limit": 0.20,
        },
        DefenseLevel.MODERATE: {
            "target_cash": 0.20,
            "hedge_budget": 0.10,
            "max_leverage": 1.0,
            "max_position": 0.15,
            "drawdown_limit": 0.15,
        },
        DefenseLevel.HEAVY: {
            "target_cash": 0.35,
            "hedge_budget": 0.20,
            "max_leverage": 0.5,
            "max_position": 0.10,
            "drawdown_limit": 0.10,
        },
        DefenseLevel.FULL: {
            "target_cash": 0.50,
            "hedge_budget": 0.30,
            "max_leverage": 0.0,
            "max_position": 0.05,
            "drawdown_limit": 0.05,
        },
    }

    # Instrument recommendations by scenario
    HEDGE_MAP: dict[str, list[HedgeInstrument]] = {
        "volatility_spike": [
            HedgeInstrument.VIX_CALLS,
            HedgeInstrument.PUT_OPTIONS,
            HedgeInstrument.CASH,
        ],
        "correlation_crisis": [
            HedgeInstrument.VIX_FUTURES,
            HedgeInstrument.TREASURY_BONDS,
            HedgeInstrument.GOLD,
        ],
        "liquidity_freeze": [
            HedgeInstrument.CASH,
            HedgeInstrument.TREASURY_BONDS,
        ],
        "credit_stress": [
            HedgeInstrument.TREASURY_BONDS,
            HedgeInstrument.GOLD,
            HedgeInstrument.JPY,
        ],
        "dollar_surge": [
            HedgeInstrument.USD,
            HedgeInstrument.TREASURY_BONDS,
            HedgeInstrument.GOLD,
        ],
        "em_crisis": [
            HedgeInstrument.CASH,
            HedgeInstrument.USD,
            HedgeInstrument.GOLD,
        ],
        "safe_haven_rush": [
            HedgeInstrument.TREASURY_BONDS,
            HedgeInstrument.GOLD,
            HedgeInstrument.CHF,
        ],
        "momentum_crash": [
            HedgeInstrument.INVERSE_ETF,
            HedgeInstrument.CASH,
        ],
        "tail_risk": [
            HedgeInstrument.VIX_CALLS,
            HedgeInstrument.PUT_OPTIONS,
            HedgeInstrument.CASH,
        ],
    }

    def __init__(self,
                 max_leverage: float = 2.0,
                 max_single_position: float = 0.25,
                 min_cash_buffer: float = 0.05):
        self.max_portfolio_leverage = max_leverage
        self.max_single_position = max_single_position
        self.min_cash_buffer = min_cash_buffer

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def generate_plan(self,
                      systemic_risk_score: float = 0.0,
                      crisis_alert: float = 0.0,
                      volatility_regime: str = "normal",
                      current_drawdown: float = 0.0,
                      current_leverage: float = 1.0,
                      concentration: float = 0.3,
                      positions: dict[str, float] | None = None,
                      correlations: dict[str, float] | None = None,
                      risk_scenarios: list[str] | None = None,
                      ) -> DefensePlan:
        """Generate a portfolio defense plan.

        Args:
            systemic_risk_score: Systemic risk score [0, 1].
            crisis_alert: Crisis composite alert [0, 1].
            volatility_regime: Current volatility regime label.
            current_drawdown: Current portfolio drawdown.
            current_leverage: Current portfolio leverage.
            concentration: Portfolio concentration (0-1).
            positions: Current position allocations {asset: weight}.
            correlations: Pairwise correlations to main portfolio.
            risk_scenarios: Active risk scenario labels.

        Returns:
            DefensePlan with ordered actions and hedge recommendations.
        """
        if positions is None:
            positions = {}
        if correlations is None:
            correlations = {}
        if risk_scenarios is None:
            risk_scenarios = []

        # Determine defense level
        defense_level = self._determine_defense_level(
            systemic_risk_score, crisis_alert, volatility_regime,
            current_drawdown, concentration,
        )

        # Get rules for this level
        rules = self.DEFENSE_RULES[defense_level]

        # Generate actions
        actions: list[DefenseAction] = []

        # Action: Cash buffer
        if rules["target_cash"] > self.min_cash_buffer:
            actions.extend(self._generate_cash_action(rules["target_cash"]))

        # Action: Leverage reduction
        if current_leverage > rules["max_leverage"]:
            actions.extend(self._generate_leverage_action(
                current_leverage, rules["max_leverage"],
            ))

        # Action: Position size limits
        oversized = {
            asset: weight
            for asset, weight in positions.items()
            if weight > rules["max_position"]
        }
        for asset, weight in oversized.items():
            actions.extend(self._generate_position_limit_action(
                asset, weight, rules["max_position"],
            ))

        # Action: Drawdown stop
        if current_drawdown > rules["drawdown_limit"]:
            actions.extend(self._generate_drawdown_stop_action(
                current_drawdown, rules["drawdown_limit"],
            ))

        # Action: Hedge recommendations based on risk scenarios
        hedge_actions = self._generate_hedge_actions(
            risk_scenarios, rules["hedge_budget"],
        )
        actions.extend(hedge_actions)

        # Action: Correlation-based defensive rotation
        if correlations and defense_level.value in ("moderate", "heavy", "full"):
            actions.extend(self._generate_correlation_defense(
                correlations, rules["max_position"],
            ))

        # Sort by priority
        actions.sort(key=lambda a: a.priority)

        # Compute expected impact
        expected_impact = self._estimate_impact(actions, rules["hedge_budget"])

        description = self._generate_plan_description(
            defense_level, actions, rules, systemic_risk_score,
            crisis_alert, volatility_regime,
        )

        return DefensePlan(
            defense_level=defense_level,
            actions=actions,
            target_cash=rules["target_cash"],
            hedge_budget=rules["hedge_budget"],
            max_drawdown_limit=rules["drawdown_limit"],
            expected_impact=expected_impact,
            description=description,
        )

    # ------------------------------------------------------------------
    # Defense Level
    # ------------------------------------------------------------------

    def _determine_defense_level(self,
                                  systemic_risk: float,
                                  crisis_alert: float,
                                  vol_regime: str,
                                  drawdown: float,
                                  concentration: float) -> DefenseLevel:
        """Determine required defense level from risk inputs."""
        score = 0.0

        # Systemic risk contribution
        if systemic_risk >= 0.7:
            score += 3.0
        elif systemic_risk >= 0.5:
            score += 2.0
        elif systemic_risk >= 0.3:
            score += 1.0

        # Crisis alert contribution
        if crisis_alert >= 0.7:
            score += 3.0
        elif crisis_alert >= 0.5:
            score += 2.0
        elif crisis_alert >= 0.3:
            score += 1.0

        # Volatility regime
        vol_scores = {
            "tail": 4.0,
            "extreme": 3.0,
            "high_vol": 2.0,
            "elevated": 1.0,
            "normal": 0.0,
            "low_vol": 0.0,
        }
        score += vol_scores.get(vol_regime, 0.0)

        # Drawdown penalty
        if drawdown > 0.15:
            score += 2.0
        elif drawdown > 0.10:
            score += 1.0

        # Concentration penalty
        if concentration > 0.6:
            score += 1.0

        if score >= 8.0:
            return DefenseLevel.FULL
        elif score >= 6.0:
            return DefenseLevel.HEAVY
        elif score >= 4.0:
            return DefenseLevel.MODERATE
        elif score >= 2.0:
            return DefenseLevel.LIGHT
        return DefenseLevel.NONE

    # ------------------------------------------------------------------
    # Action Generators
    # ------------------------------------------------------------------

    def _generate_cash_action(self, target_cash: float) -> list[DefenseAction]:
        return [DefenseAction(
            action_type=DefenseActionType.INCREASE_CASH,
            target_asset="portfolio",
            current_allocation=1.0 - target_cash,
            target_allocation=1.0 - target_cash,
            priority=1,
            reason=f"Maintain {target_cash:.0%} cash buffer for liquidity",
            urgency=target_cash * 2.0,
        )]

    def _generate_leverage_action(self, current: float,
                                   target: float) -> list[DefenseAction]:
        return [DefenseAction(
            action_type=DefenseActionType.REDUCE_LEVERAGE,
            target_asset="portfolio",
            current_allocation=current,
            target_allocation=target,
            priority=1,
            reason=f"Reduce leverage from {current:.1f}x to {target:.1f}x",
            urgency=min(1.0, (current - target) / current),
        )]

    def _generate_position_limit_action(self, asset: str, current_weight: float,
                                         limit: float) -> list[DefenseAction]:
        return [DefenseAction(
            action_type=DefenseActionType.POSITION_LIMIT,
            target_asset=asset,
            current_allocation=current_weight,
            target_allocation=limit,
            priority=2,
            reason=f"Position {asset} ({current_weight:.1%}) exceeds limit ({limit:.1%})",
            urgency=min(1.0, (current_weight - limit) * 3),
        )]

    def _generate_drawdown_stop_action(self, drawdown: float,
                                        limit: float) -> list[DefenseAction]:
        exceed = drawdown - limit
        actions = [DefenseAction(
            action_type=DefenseActionType.STOP_LOSS,
            target_asset="portfolio",
            current_allocation=1.0,
            target_allocation=0.5,
            stop_loss_level=limit,
            priority=1,
            reason=f"Drawdown ({drawdown:.1%}) exceeds limit ({limit:.1%})",
            urgency=min(1.0, exceed * 10),
        )]
        if drawdown > 0.2:
            actions.append(DefenseAction(
                action_type=DefenseActionType.TRAILING_STOP,
                target_asset="portfolio",
                priority=3,
                reason="Activate trailing stop to protect remaining capital",
                urgency=0.8,
            ))
        return actions

    def _generate_hedge_actions(self, scenarios: list[str],
                                 hedge_budget: float) -> list[DefenseAction]:
        """Generate hedge actions based on active risk scenarios."""
        if not scenarios or hedge_budget <= 0:
            return []

        actions: list[DefenseAction] = []
        instruments: set[HedgeInstrument] = set()
        for scenario in scenarios:
            insts = self.HEDGE_MAP.get(scenario, [])
            instruments.update(insts)

        if not instruments:
            return []

        budget_per = hedge_budget / max(len(instruments), 1)
        for i, inst in enumerate(sorted(instruments, key=lambda x: x.value)):
            actions.append(DefenseAction(
                action_type=DefenseActionType.ADD_HEDGE,
                target_asset=f"hedge_{inst.value}",
                hedge_instrument=inst,
                hedge_ratio=budget_per,
                priority=3 + i,
                reason=f"Hedge against {', '.join(scenarios[:2])} using {inst.value}",
                urgency=min(1.0, hedge_budget * 2),
            ))

        return actions

    def _generate_correlation_defense(self, correlations: dict[str, float],
                                       max_position: float) -> list[DefenseAction]:
        """Generate actions to reduce highly correlated positions."""
        actions: list[DefenseAction] = []
        for asset, corr in correlations.items():
            if corr >= 0.8:
                actions.append(DefenseAction(
                    action_type=DefenseActionType.CORRELATION_HEDGE,
                    target_asset=asset,
                    target_allocation=max_position * 0.5,
                    priority=4,
                    reason=f"High correlation ({corr:.2f}) – reduce {asset} position",
                    urgency=min(1.0, (corr - 0.6) * 2),
                ))
        return actions

    # ------------------------------------------------------------------
    # Impact Estimation
    # ------------------------------------------------------------------

    def _estimate_impact(self, actions: list[DefenseAction],
                         hedge_budget: float) -> float:
        """Estimate expected P&L impact of hedging (negative = cost)."""
        # Simple model: each hedge action costs ~1% of its budget
        hedge_actions = [a for a in actions
                         if a.action_type == DefenseActionType.ADD_HEDGE]
        impact = -len(hedge_actions) * 0.005 * hedge_budget

        # Stop-loss actions reduce further losses (positive impact)
        stop_actions = [a for a in actions
                        if a.action_type in (DefenseActionType.STOP_LOSS,
                                             DefenseActionType.TRAILING_STOP)]
        impact += len(stop_actions) * 0.01

        return round(impact, 4)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------

    def _generate_plan_description(self, level: DefenseLevel,
                                    actions: list[DefenseAction],
                                    rules: dict[str, float],
                                    systemic: float,
                                    crisis: float,
                                    vol_regime: str) -> str:
        level_desc = {
            DefenseLevel.NONE: "No defense required – normal operating mode",
            DefenseLevel.LIGHT: "Light defense – moderate risk reduction",
            DefenseLevel.MODERATE: "Moderate defense – significant risk reduction",
            DefenseLevel.HEAVY: "Heavy defense – strong risk reduction",
            DefenseLevel.FULL: "FULL defense – maximum capital preservation",
        }
        base = level_desc.get(level, "Unknown")
        details = (
            f"Cash target: {rules['target_cash']:.0%}, "
            f"Hedge budget: {rules['hedge_budget']:.0%}, "
            f"Drawdown limit: {rules['drawdown_limit']:.0%}"
        )
        triggers = f"Triggers: systemic={systemic:.2f}, crisis={crisis:.2f}, vol={vol_regime}"
        return f"{base}. {details}. {triggers}. Actions: {len(actions)}"

    # ------------------------------------------------------------------
    # Quick Defense Check
    # ------------------------------------------------------------------

    def quick_defense_check(self,
                            systemic_risk: float = 0.0,
                            crisis_alert: float = 0.0,
                            vol_regime: str = "normal",
                            drawdown: float = 0.0) -> dict[str, Any]:
        """Quick check of required defense posture."""
        level = self._determine_defense_level(
            systemic_risk, crisis_alert, vol_regime, drawdown, 0.3,
        )
        rules = self.DEFENSE_RULES[level]
        return {
            "defense_level": level.value,
            "needs_defense": level != DefenseLevel.NONE,
            "target_cash": rules["target_cash"],
            "hedge_budget": rules["hedge_budget"],
            "max_leverage": rules["max_leverage"],
            "max_position": rules["max_position"],
            "drawdown_limit": rules["drawdown_limit"],
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset internal state."""
        pass  # Stateless engine, no-op
