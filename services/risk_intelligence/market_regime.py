"""ICYQuant Market Regime Detector.

Automatic market regime identification from price/volume data.
Regimes: BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY, LOW_LIQUIDITY, RISK_OFF, CRISIS.

Usage::

    detector = MarketRegimeDetector(MarketRegimeConfig())
    regime = detector.detect(prices, returns, volume, volatility)
    max_pos = detector.get_max_position_pct(regime)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.risk_intelligence.config import (
    MarketRegimeConfig,
    MarketRegime,
)


@dataclass
class RegimeResult:
    """Market regime detection result."""

    regime: MarketRegime
    confidence: float  # 0.0 - 1.0
    bull_score: float = 0.0
    bear_score: float = 0.0
    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    trend_strength: float = 0.0
    detected_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 4),
            "bull_score": round(self.bull_score, 4),
            "bear_score": round(self.bear_score, 4),
            "volatility_score": round(self.volatility_score, 4),
            "liquidity_score": round(self.liquidity_score, 4),
            "trend_strength": round(self.trend_strength, 4),
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class RegimeHistory:
    """Market regime transition history."""

    current: RegimeResult
    previous: Optional[RegimeResult] = None
    changed: bool = False
    duration_in_regime_days: int = 0
    transition_history: List[RegimeResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": self.current.to_dict(),
            "previous": self.previous.to_dict() if self.previous else None,
            "changed": self.changed,
            "duration_in_regime_days": self.duration_in_regime_days,
        }


class MarketRegimeDetector:
    """Market Regime Detector.

    Identifies the current market regime using multi-factor analysis:
    trend, volatility, liquidity, breadth, and risk appetite.

    Usage::

        detector = MarketRegimeDetector(MarketRegimeConfig())
        regime = detector.detect(prices, returns, volume, volatility)
        if regime.regime == MarketRegime.CRISIS:
            # Tighten risk limits
            ...
    """

    def __init__(self, config: Optional[MarketRegimeConfig] = None) -> None:
        self.config = config or MarketRegimeConfig()
        self._history: List[RegimeResult] = []
        self._current_regime: Optional[RegimeResult] = None

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(
        self,
        prices: List[float],
        returns: Optional[List[float]] = None,
        volume: Optional[List[float]] = None,
        volatility: Optional[float] = None,
        spread: Optional[float] = None,
        breadth: Optional[float] = None,
    ) -> RegimeResult:
        """Detect the current market regime.

        Args:
            prices: Historical price series.
            returns: Return series (computed if not provided).
            volume: Volume series.
            volatility: Current volatility estimate.
            spread: Bid-ask spread.
            breadth: Market breadth indicator.

        Returns:
            RegimeResult with regime and confidence.
        """
        if returns is None and len(prices) >= 2:
            returns = [
                (prices[i] - prices[i - 1]) / prices[i - 1]
                for i in range(1, len(prices))
            ]

        # Compute regime scores
        bull_score = self._compute_trend_score(prices, returns)
        bear_score = 1.0 - bull_score
        vol_score = self._compute_volatility_score(returns, volatility)
        liq_score = self._compute_liquidity_score(volume, spread)

        # Determine regime
        regime, confidence = self._classify_regime(
            bull_score, bear_score, vol_score, liq_score
        )

        # Trend strength
        trend_strength = abs(bull_score - 0.5) * 2

        result = RegimeResult(
            regime=regime,
            confidence=confidence,
            bull_score=bull_score,
            bear_score=bear_score,
            volatility_score=vol_score,
            liquidity_score=liq_score,
            trend_strength=trend_strength,
        )

        # Track history
        prev = self._current_regime
        self._current_regime = result
        self._history.append(result)

        # Keep bounded history
        if len(self._history) > self.config.detection_window * 2:
            self._history = self._history[-self.config.detection_window * 2:]

        return result

    def _compute_trend_score(
        self, prices: List[float], returns: Optional[List[float]]
    ) -> float:
        """Compute bullish trend score (0=bearish, 1=bullish)."""
        if len(prices) < self.config.trend_lookback:
            return 0.5

        n = min(len(prices), self.config.trend_lookback)
        recent = prices[-n:]

        # SMA crossover signals
        short_n = min(20, n // 3)
        long_n = min(50, n // 2)
        if short_n < 2 or long_n < 3:
            return 0.5

        sma_short = sum(recent[-short_n:]) / short_n
        sma_long = sum(recent[-long_n:]) / long_n

        # Price momentum
        momentum = (prices[-1] / prices[-min(n, n)]) - 1

        # Positive return ratio
        if returns and len(returns) >= 20:
            recent_rets = returns[-20:]
            pos_ratio = sum(1 for r in recent_rets if r > 0) / len(recent_rets)
        else:
            pos_ratio = 0.5

        # Composite score
        sma_signal = 1.0 if sma_short > sma_long else 0.0
        momentum_signal = min(1.0, max(0.0, (momentum + 0.2) / 0.4))
        score = (sma_signal * 0.3 + momentum_signal * 0.4 + pos_ratio * 0.3)

        return score

    def _compute_volatility_score(
        self,
        returns: Optional[List[float]],
        current_vol: Optional[float],
    ) -> float:
        """Compute volatility score (0=low vol, 1=extreme vol)."""
        if current_vol is not None:
            # Normalize: 15% vol = 0.3, 40% vol = 0.8
            return min(1.0, max(0.0, current_vol / 0.5))

        if returns and len(returns) >= self.config.volatility_lookback:
            recent = returns[-self.config.volatility_lookback:]
            mean = sum(recent) / len(recent)
            var = sum((r - mean) ** 2 for r in recent) / len(recent)
            vol = math.sqrt(var * 252)  # Annualized
            return min(1.0, max(0.0, vol / 0.5))

        return 0.3

    def _compute_liquidity_score(
        self,
        volume: Optional[List[float]],
        spread: Optional[float],
    ) -> float:
        """Compute liquidity score (0=high liquidity, 1=no liquidity)."""
        score = 0.3  # Default

        if volume and len(volume) >= 20:
            recent_vol = volume[-20:]
            avg_vol = sum(recent_vol) / len(recent_vol)
            if avg_vol > 0 and len(recent_vol) >= 5:
                vol_ratio = sum(recent_vol[-5:]) / 5 / avg_vol
                # Low volume = high score
                score = 1.0 - min(1.0, max(0.0, vol_ratio))

        if spread is not None:
            spread_score = min(1.0, spread / 0.01)  # 1% spread = 1.0
            score = max(score, spread_score)

        return score

    def _classify_regime(
        self,
        bull_score: float,
        bear_score: float,
        vol_score: float,
        liq_score: float,
    ) -> Tuple[MarketRegime, float]:
        """Classify regime from individual scores."""
        # Crisis: extreme vol + low liquidity
        if vol_score > 0.8 and liq_score > 0.7:
            return MarketRegime.CRISIS, max(vol_score, liq_score)

        # Risk-off: high vol + limited liquidity + bearish
        if vol_score > 0.6 and liq_score > 0.5 and bull_score < 0.4:
            return MarketRegime.RISK_OFF, max(vol_score, 1 - bull_score)

        # High volatility
        if vol_score > 0.6:
            return MarketRegime.HIGH_VOLATILITY, vol_score

        # Low liquidity
        if liq_score > 0.7:
            return MarketRegime.LOW_LIQUIDITY, liq_score

        # Bull
        if bull_score > 0.6:
            return MarketRegime.BULL, bull_score

        # Bear
        if bull_score < 0.4:
            return MarketRegime.BEAR, 1 - bull_score

        # Sideways
        return MarketRegime.SIDEWAYS, 0.6

    # ------------------------------------------------------------------
    # Regime-Based Parameters
    # ------------------------------------------------------------------

    def get_max_position_pct(self, regime: Optional[MarketRegime] = None) -> float:
        """Get the maximum position size for a given regime.

        Args:
            regime: Market regime (defaults to current).

        Returns:
            Maximum position size percentage.
        """
        regime = regime or (self._current_regime.regime if self._current_regime else None)
        if regime is None:
            return self.config.default_max_position_pct

        mapping = {
            MarketRegime.BULL: self.config.bull_max_position_pct,
            MarketRegime.BEAR: self.config.bear_max_position_pct,
            MarketRegime.CRISIS: self.config.crisis_max_position_pct,
            MarketRegime.RISK_OFF: self.config.risk_off_max_position_pct,
        }
        return mapping.get(regime, self.config.default_max_position_pct)

    def get_leverage_multiplier(self, regime: Optional[MarketRegime] = None) -> float:
        """Get leverage multiplier for a given regime."""
        multipliers = {
            MarketRegime.BULL: 1.0,
            MarketRegime.SIDEWAYS: 0.8,
            MarketRegime.BEAR: 0.5,
            MarketRegime.HIGH_VOLATILITY: 0.4,
            MarketRegime.LOW_LIQUIDITY: 0.3,
            MarketRegime.RISK_OFF: 0.25,
            MarketRegime.CRISIS: 0.1,
        }
        r = regime or (self._current_regime.regime if self._current_regime else MarketRegime.UNKNOWN)
        return multipliers.get(r, 0.5)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def get_current_regime(self) -> Optional[RegimeResult]:
        """Get the current regime result."""
        return self._current_regime

    def get_history(self, limit: int = 50) -> List[RegimeResult]:
        """Get recent regime detection history."""
        return self._history[-limit:]

    def was_regime_recently(
        self, regime: MarketRegime, within_days: int = 5
    ) -> bool:
        """Check if a regime was detected recently."""
        recent = self._history[-within_days:]
        return any(r.regime == regime for r in recent)

    def get_regime_change_count(self, within_days: int = 30) -> int:
        """Count the number of regime changes in the given window."""
        if len(self._history) < 2:
            return 0

        recent = self._history[-within_days:]
        changes = sum(
            1 for i in range(1, len(recent))
            if recent[i].regime != recent[i - 1].regime
        )
        return changes
