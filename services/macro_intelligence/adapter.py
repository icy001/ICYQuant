"""Macro Strategy Adapter.

Connects macro regime intelligence to strategy selection, portfolio
allocation, and risk management. Translates macro regime signals
into actionable investment decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .classifier import MacroClassification
from .data import MacroRegimeState


class StrategyTheme(str, Enum):
    """Investment strategy themes driven by macro regime."""
    GROWTH = "growth"                       # growth stocks, tech
    VALUE = "value"                         # value stocks, financials
    MOMENTUM = "momentum"                   # trend following
    DEFENSIVE = "defensive"                 # consumer staples, utilities
    INCOME = "income"                       # dividend, bond income
    INFLATION_HEDGE = "inflation_hedge"     # commodities, TIPS, real assets
    SAFE_HAVEN = "safe_haven"              # gold, treasuries, JPY
    SHORT_VOLATILITY = "short_volatility"   # selling vol in calm markets
    LONG_VOLATILITY = "long_volatility"     # buying vol for protection
    MARKET_NEUTRAL = "market_neutral"       # pair trades, arbitrage
    MACRO_TREND = "macro_trend"             # macro-driven directional bets
    CARRY = "carry"                         # carry trades


@dataclass
class MacroAdaptation:
    """Macro-driven strategy and portfolio adaptation.

    Attributes:
        regime_state: The macro regime state driving this adaptation.
        primary_themes: Primary strategy themes for this regime.
        secondary_themes: Supporting strategy themes.
        avoid_themes: Strategy themes to avoid.
        equity_exposure: Recommended equity exposure (0-1).
        bond_duration_bias: Duration bias (-1 short, 0 neutral, 1 long).
        commodity_exposure: Commodity exposure (0-1).
        cash_weight: Recommended cash allocation (0-1).
        leverage_multiplier: Recommended leverage (1.0 = no leverage).
        sector_rotation: Sector over/underweight recommendations.
        risk_budget: Recommended risk budget adjustment.
        confidence: Adaptation confidence (0-1).
        details: Additional adaptation details.
        timestamp: Adaptation timestamp.
    """
    regime_state: MacroRegimeState
    primary_themes: list[StrategyTheme]
    secondary_themes: list[StrategyTheme] = field(default_factory=list)
    avoid_themes: list[StrategyTheme] = field(default_factory=list)
    equity_exposure: float = 0.6
    bond_duration_bias: float = 0.0
    commodity_exposure: float = 0.1
    cash_weight: float = 0.1
    leverage_multiplier: float = 1.0
    sector_rotation: dict[str, float] = field(default_factory=dict)
    risk_budget: float = 1.0
    confidence: float = 0.5
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_aggressive(self) -> bool:
        return self.equity_exposure > 0.7

    @property
    def is_defensive(self) -> bool:
        return self.equity_exposure < 0.4

    @property
    def summary(self) -> str:
        themes = ", ".join(t.value for t in self.primary_themes)
        return (
            f"[{self.regime_state.value}] equity={self.equity_exposure:.0%}, "
            f"themes=[{themes}], confidence={self.confidence:.0%}"
        )


class MacroStrategyAdapter:
    """Adapts strategy and portfolio to macro regime.

    Translates macro regime classifications into concrete
    strategy theme selections, asset allocation biases,
    sector rotations, and risk budget adjustments.
    """

    # Regime → Strategy Theme Mapping
    _REGIME_THEMES: dict[MacroRegimeState, dict[str, Any]] = {
        MacroRegimeState.GOLDILOCKS: {
            "primary": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "secondary": [StrategyTheme.VALUE, StrategyTheme.CARRY],
            "avoid": [StrategyTheme.DEFENSIVE, StrategyTheme.SAFE_HAVEN],
            "equity": 0.85, "duration": -0.3, "commodity": 0.15,
            "cash": 0.05, "leverage": 1.1, "risk_budget": 1.1,
        },
        MacroRegimeState.REFLATION: {
            "primary": [StrategyTheme.VALUE, StrategyTheme.INFLATION_HEDGE],
            "secondary": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "avoid": [StrategyTheme.DEFENSIVE, StrategyTheme.SHORT_VOLATILITY],
            "equity": 0.70, "duration": -0.5, "commodity": 0.30,
            "cash": 0.10, "leverage": 1.0, "risk_budget": 1.0,
        },
        MacroRegimeState.OVERHEATING: {
            "primary": [StrategyTheme.INFLATION_HEDGE, StrategyTheme.VALUE],
            "secondary": [StrategyTheme.LONG_VOLATILITY],
            "avoid": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "equity": 0.50, "duration": -0.7, "commodity": 0.35,
            "cash": 0.15, "leverage": 0.9, "risk_budget": 0.8,
        },
        MacroRegimeState.STAGFLATION: {
            "primary": [StrategyTheme.SAFE_HAVEN, StrategyTheme.INFLATION_HEDGE],
            "secondary": [StrategyTheme.LONG_VOLATILITY, StrategyTheme.MARKET_NEUTRAL],
            "avoid": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM, StrategyTheme.CARRY],
            "equity": 0.30, "duration": -0.3, "commodity": 0.40,
            "cash": 0.25, "leverage": 0.7, "risk_budget": 0.5,
        },
        MacroRegimeState.RECESSION: {
            "primary": [StrategyTheme.SAFE_HAVEN, StrategyTheme.DEFENSIVE],
            "secondary": [StrategyTheme.INCOME, StrategyTheme.LONG_VOLATILITY],
            "avoid": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM, StrategyTheme.VALUE],
            "equity": 0.20, "duration": 0.8, "commodity": 0.05,
            "cash": 0.30, "leverage": 0.6, "risk_budget": 0.4,
        },
        MacroRegimeState.RECOVERY: {
            "primary": [StrategyTheme.GROWTH, StrategyTheme.VALUE],
            "secondary": [StrategyTheme.MOMENTUM, StrategyTheme.CARRY],
            "avoid": [StrategyTheme.SAFE_HAVEN, StrategyTheme.DEFENSIVE],
            "equity": 0.80, "duration": 0.2, "commodity": 0.20,
            "cash": 0.08, "leverage": 1.05, "risk_budget": 1.05,
        },
        MacroRegimeState.EASING: {
            "primary": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "secondary": [StrategyTheme.VALUE, StrategyTheme.CARRY],
            "avoid": [StrategyTheme.DEFENSIVE],
            "equity": 0.75, "duration": 0.5, "commodity": 0.20,
            "cash": 0.05, "leverage": 1.05, "risk_budget": 1.05,
        },
        MacroRegimeState.TIGHTENING: {
            "primary": [StrategyTheme.VALUE, StrategyTheme.INCOME],
            "secondary": [StrategyTheme.DEFENSIVE, StrategyTheme.LONG_VOLATILITY],
            "avoid": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "equity": 0.45, "duration": -0.3, "commodity": 0.15,
            "cash": 0.20, "leverage": 0.85, "risk_budget": 0.8,
        },
        MacroRegimeState.LIQUIDITY_SURGE: {
            "primary": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM],
            "secondary": [StrategyTheme.CARRY, StrategyTheme.SHORT_VOLATILITY],
            "avoid": [StrategyTheme.DEFENSIVE, StrategyTheme.SAFE_HAVEN],
            "equity": 0.90, "duration": -0.2, "commodity": 0.25,
            "cash": 0.03, "leverage": 1.2, "risk_budget": 1.15,
        },
        MacroRegimeState.LIQUIDITY_CRUNCH: {
            "primary": [StrategyTheme.SAFE_HAVEN, StrategyTheme.DEFENSIVE],
            "secondary": [StrategyTheme.LONG_VOLATILITY],
            "avoid": [StrategyTheme.GROWTH, StrategyTheme.MOMENTUM, StrategyTheme.CARRY],
            "equity": 0.15, "duration": 0.5, "commodity": 0.05,
            "cash": 0.40, "leverage": 0.5, "risk_budget": 0.3,
        },
    }

    # Sector rotation by regime
    _SECTOR_ROTATION: dict[MacroRegimeState, dict[str, float]] = {
        MacroRegimeState.GOLDILOCKS: {
            "Technology": 0.3, "Consumer_Discretionary": 0.2,
            "Financials": 0.1, "Utilities": -0.2, "Consumer_Staples": -0.2,
        },
        MacroRegimeState.RECESSION: {
            "Consumer_Staples": 0.3, "Utilities": 0.3, "Healthcare": 0.2,
            "Technology": -0.2, "Consumer_Discretionary": -0.3, "Financials": -0.2,
        },
        MacroRegimeState.STAGFLATION: {
            "Energy": 0.3, "Materials": 0.2, "Healthcare": 0.1,
            "Technology": -0.2, "Consumer_Discretionary": -0.2,
        },
        MacroRegimeState.REFLATION: {
            "Financials": 0.3, "Energy": 0.2, "Industrials": 0.2,
            "Utilities": -0.1, "Consumer_Staples": -0.1,
        },
    }

    def __init__(self):
        self._adaptations: list[MacroAdaptation] = []

    def adapt(self, classification: MacroClassification) -> MacroAdaptation:
        """Generate macro-driven adaptation from classification.

        Args:
            classification: Complete macro classification result.

        Returns:
            MacroAdaptation with strategy themes and allocation biases.
        """
        regime_state = classification.regime.state
        config = self._REGIME_THEMES.get(regime_state, self._default_config())

        # Get sector rotation
        sectors = self._SECTOR_ROTATION.get(regime_state, {})

        adaptation = MacroAdaptation(
            regime_state=regime_state,
            primary_themes=config["primary"],
            secondary_themes=config.get("secondary", []),
            avoid_themes=config.get("avoid", []),
            equity_exposure=config["equity"],
            bond_duration_bias=config["duration"],
            commodity_exposure=config["commodity"],
            cash_weight=config["cash"],
            leverage_multiplier=config["leverage"],
            sector_rotation=sectors,
            risk_budget=config["risk_budget"],
            confidence=classification.regime.confidence,
            details={
                "cycle": classification.cycle_result.phase.value if classification.cycle_result else None,
                "inflation": classification.inflation_result.trend.value if classification.inflation_result else None,
                "liquidity": classification.liquidity_result.condition.value if classification.liquidity_result else None,
            },
        )

        self._adaptations.append(adaptation)
        return adaptation

    def adapt_from_regime(self, regime_state: MacroRegimeState) -> MacroAdaptation:
        """Generate adaptation directly from a regime state.

        Convenience method for testing and quick lookups.

        Args:
            regime_state: Macro regime state.

        Returns:
            MacroAdaptation for the regime.
        """
        config = self._REGIME_THEMES.get(regime_state, self._default_config())
        sectors = self._SECTOR_ROTATION.get(regime_state, {})

        adaptation = MacroAdaptation(
            regime_state=regime_state,
            primary_themes=config["primary"],
            secondary_themes=config.get("secondary", []),
            avoid_themes=config.get("avoid", []),
            equity_exposure=config["equity"],
            bond_duration_bias=config["duration"],
            commodity_exposure=config["commodity"],
            cash_weight=config["cash"],
            leverage_multiplier=config["leverage"],
            sector_rotation=sectors,
            risk_budget=config["risk_budget"],
            confidence=0.5,
        )
        self._adaptations.append(adaptation)
        return adaptation

    def get_history(self) -> list[MacroAdaptation]:
        """Get historical adaptations."""
        return list(self._adaptations)

    def get_latest(self) -> Optional[MacroAdaptation]:
        """Get the most recent adaptation."""
        return self._adaptations[-1] if self._adaptations else None

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _default_config() -> dict[str, Any]:
        """Default configuration for unknown regimes."""
        return {
            "primary": [StrategyTheme.MARKET_NEUTRAL],
            "secondary": [],
            "avoid": [],
            "equity": 0.50,
            "duration": 0.0,
            "commodity": 0.10,
            "cash": 0.15,
            "leverage": 1.0,
            "risk_budget": 0.8,
        }


__all__ = [
    "StrategyTheme",
    "MacroAdaptation",
    "MacroStrategyAdapter",
]
