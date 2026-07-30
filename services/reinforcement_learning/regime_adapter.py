"""Market Regime Adapter — dynamically adapts RL policies to market regimes.

Detects market regimes (bull, bear, neutral, crisis) and adapts
RL agent behavior accordingly. Uses regime-specific policy weights
and risk parameters.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math

import numpy as np


class MarketRegime(Enum):
    """Market regime classifications."""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    CRISIS = "crisis"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    TRENDING = "trending"
    RANGING = "ranging"


@dataclass
class RegimeConfig:
    """Configuration for regime detection and adaptation."""

    # Detection parameters
    trend_lookback: int = 50
    volatility_lookback: int = 20
    correlation_lookback: int = 60
    drawdown_threshold: float = 0.20  # bear market threshold

    # Regime thresholds
    bull_threshold: float = 0.10  # 10% above MA for bull
    bear_threshold: float = -0.10  # 10% below MA for bear
    crisis_drawdown: float = 0.30  # 30% drawdown = crisis
    high_vol_threshold: float = 0.40  # 40% vol = high vol

    # Adaptation weights
    regime_policy_weights: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Smoothing
    regime_smoothing: int = 5  # periods to smooth regime detection
    min_regime_duration: int = 10  # minimum steps before regime switch

    # Default risk parameters per regime
    default_risk_params: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "bull": {"max_position": 0.30, "max_leverage": 2.0, "stop_loss": 0.10},
        "bear": {"max_position": 0.10, "max_leverage": 1.0, "stop_loss": 0.05},
        "neutral": {"max_position": 0.20, "max_leverage": 1.5, "stop_loss": 0.08},
        "crisis": {"max_position": 0.05, "max_leverage": 0.5, "stop_loss": 0.03},
        "high_vol": {"max_position": 0.10, "max_leverage": 1.0, "stop_loss": 0.07},
        "low_vol": {"max_position": 0.25, "max_leverage": 2.0, "stop_loss": 0.10},
    })


@dataclass
class RegimePolicy:
    """Policy adapted for a specific regime."""

    regime: MarketRegime
    risk_params: Dict[str, float] = field(default_factory=dict)
    policy_weights: Optional[Dict[str, float]] = None
    confidence: float = 1.0
    active_since: int = 0


class RegimeAdapter:
    """Adapts RL agent behavior to current market regime.

    Detects regime → adjusts risk params → modifies policy output.

    Usage:
        adapter = RegimeAdapter(config)
        regime = adapter.detect_regime(prices, returns, volatility)
        adapted_action = adapter.adapt_action(action, regime)
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self._current_regime: MarketRegime = MarketRegime.NEUTRAL
        self._regime_history: List[MarketRegime] = []
        self._regime_duration: int = 0
        self._price_history: List[float] = []
        self._return_history: List[float] = []
        self._volatility_history: List[float] = []

    def detect_regime(
        self,
        prices: List[float],
        returns: List[float],
        volatility: float = 0.2,
        drawdown: float = 0.0,
        vix: float = 20.0,
        correlations: Optional[float] = None,
    ) -> MarketRegime:
        """Detect current market regime from market data.

        Args:
            prices: Recent price series
            returns: Recent returns
            volatility: Current volatility
            drawdown: Current drawdown
            vix: VIX level
            correlations: Cross-asset correlation

        Returns:
            Detected MarketRegime
        """
        self._update_history(prices, returns, volatility)

        # Crisis detection (highest priority)
        if drawdown >= self.config.crisis_drawdown or vix > 50:
            regime = MarketRegime.CRISIS

        # Bear market
        elif self._is_bear_market(prices, returns):
            regime = MarketRegime.BEAR

        # High volatility
        elif volatility > self.config.high_vol_threshold:
            regime = MarketRegime.HIGH_VOL

        # Bull market
        elif self._is_bull_market(prices, returns):
            regime = MarketRegime.BULL

        # Trending vs ranging
        elif self._is_trending(returns):
            regime = MarketRegime.TRENDING

        # Low volatility
        elif volatility < 0.15:
            regime = MarketRegime.LOW_VOL

        else:
            regime = MarketRegime.NEUTRAL

        # Smooth regime transitions
        regime = self._smooth_regime(regime)

        self._current_regime = regime
        self._regime_history.append(regime)
        self._regime_duration += 1

        return regime

    def adapt_action(
        self,
        action: Dict[str, float],
        regime: Optional[MarketRegime] = None,
    ) -> Dict[str, float]:
        """Adapt action based on current market regime.

        Args:
            action: Original action weights
            regime: Current regime (uses detected if None)

        Returns:
            Adapted action weights
        """
        regime = regime or self._current_regime
        risk_params = self.get_risk_params(regime)
        max_pos = risk_params.get("max_position", 0.25)

        adapted = {}
        for symbol, weight in action.items():
            # Scale position based on regime risk limits
            adapted_weight = weight * (max_pos / 0.25)  # normalize to default 25%
            adapted_weight = max(-max_pos, min(max_pos, adapted_weight))
            adapted[symbol] = adapted_weight

        return adapted

    def get_risk_params(self, regime: Optional[MarketRegime] = None) -> Dict[str, float]:
        """Get risk parameters for current regime."""
        regime = regime or self._current_regime
        return self.config.default_risk_params.get(
            regime.value,
            self.config.default_risk_params["neutral"],
        ).copy()

    def get_current_regime(self) -> MarketRegime:
        """Get current detected regime."""
        return self._current_regime

    def get_regime_distribution(self) -> Dict[str, float]:
        """Get historical regime distribution."""
        if not self._regime_history:
            return {}
        total = len(self._regime_history)
        distribution = {}
        for regime in MarketRegime:
            count = sum(1 for r in self._regime_history if r == regime)
            distribution[regime.value] = count / total if total > 0 else 0.0
        return distribution

    def should_reduce_exposure(self) -> bool:
        """Check if current regime warrants reduced exposure."""
        high_risk_regimes = {
            MarketRegime.CRISIS,
            MarketRegime.BEAR,
            MarketRegime.HIGH_VOL,
        }
        return self._current_regime in high_risk_regimes

    def should_increase_exposure(self) -> bool:
        """Check if current regime warrants increased exposure."""
        low_risk_regimes = {
            MarketRegime.BULL,
            MarketRegime.LOW_VOL,
        }
        return self._current_regime in low_risk_regimes

    def get_regime_transition_probability(self) -> Dict[str, float]:
        """Estimate probability of regime transition."""
        if len(self._regime_history) < 5:
            return {}

        recent = self._regime_history[-5:]
        current_count = sum(1 for r in recent if r == self._current_regime)
        stability = current_count / len(recent)

        return {
            "stay": stability,
            "change": 1.0 - stability,
            "current_regime": self._current_regime.value,
        }

    def _is_bull_market(
        self, prices: List[float], returns: List[float]
    ) -> bool:
        """Check if market is in bull regime."""
        if len(prices) < self.config.trend_lookback:
            return False
        ma = np.mean(prices[-self.config.trend_lookback:])
        current = prices[-1]
        return (current - ma) / ma > self.config.bull_threshold

    def _is_bear_market(
        self, prices: List[float], returns: List[float]
    ) -> bool:
        """Check if market is in bear regime."""
        if len(prices) < self.config.trend_lookback:
            return False
        ma = np.mean(prices[-self.config.trend_lookback:])
        current = prices[-1]
        return (current - ma) / ma < self.config.bear_threshold

    def _is_trending(self, returns: List[float]) -> bool:
        """Check if market is trending."""
        if len(returns) < 10:
            return False
        # High autocorrelation = trending
        recent = returns[-20:]
        if len(recent) < 10:
            return False
        autocorr = np.corrcoef(recent[:-1], recent[1:])[0, 1]
        return abs(autocorr) > 0.3

    def _smooth_regime(self, new_regime: MarketRegime) -> MarketRegime:
        """Smooth regime detection to avoid frequent switching."""
        # Enforce minimum duration
        if (
            self._regime_duration < self.config.min_regime_duration
            and self._regime_history
        ):
            return self._current_regime

        # Use mode of recent detections
        lookback = min(self.config.regime_smoothing, len(self._regime_history))
        if lookback > 0:
            recent = self._regime_history[-lookback:] + [new_regime]
            # Count occurrences
            counts = {}
            for r in recent:
                counts[r] = counts.get(r, 0) + 1
            majority_regime = max(counts, key=counts.get)

            if majority_regime != new_regime and counts[majority_regime] > lookback / 2:
                return majority_regime

        return new_regime

    def _update_history(
        self,
        prices: List[float],
        returns: List[float],
        volatility: float,
    ):
        """Update historical data."""
        if prices:
            self._price_history.append(prices[-1])
        if returns:
            self._return_history.append(returns[-1])
        self._volatility_history.append(volatility)

        # Keep bounded
        max_len = self.config.trend_lookback * 2
        if len(self._price_history) > max_len:
            self._price_history = self._price_history[-max_len:]
        if len(self._return_history) > max_len:
            self._return_history = self._return_history[-max_len:]
        if len(self._volatility_history) > max_len:
            self._volatility_history = self._volatility_history[-max_len:]

    def reset(self):
        """Reset adapter state."""
        self._current_regime = MarketRegime.NEUTRAL
        self._regime_history = []
        self._regime_duration = 0
        self._price_history = []
        self._return_history = []
        self._volatility_history = []
