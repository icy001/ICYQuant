"""Regime Detector — Identifies and tracks market regime states.

Classifies market conditions into discrete regimes that inform
research prioritization and strategy selection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regime classifications."""

    TRENDING_BULL = "trending_bull"
    TRENDING_BEAR = "trending_bear"
    MEAN_REVERTING_LOW_VOL = "mean_reverting_low_vol"
    MEAN_REVERTING_HIGH_VOL = "mean_reverting_high_vol"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    TRANSITION = "transition"
    SIDEWAYS = "sideways"


class RegimeDetector:
    """Regime Detector — identifies market state.

    Classifies the market into regimes based on:
        - Trend analysis (bull/bear/sideways)
        - Volatility levels (high/low)
        - Risk appetite (risk-on/risk-off)
        - Transition probability (regime change detection)

    Regime information feeds into:
        - Opportunity prioritization
        - Strategy selection
        - Risk adjustment
    """

    def __init__(self) -> None:
        self.current_regime: MarketRegime = MarketRegime.TRENDING_BULL
        self.regime_history: List[Dict[str, Any]] = []
        self._regime_duration: int = 0
        self._last_regime_change: Optional[datetime] = None

    async def detect(
        self,
        observations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Detect current market regime from observations.

        Args:
            observations: Market observations.

        Returns:
            Dict with regimes list and metadata.
        """
        regimes: List[Dict[str, Any]] = []

        # Analyze observations to determine regime
        new_regime = self._classify_regime(observations)

        # Check for regime transition
        if new_regime != self.current_regime:
            prev_regime = self.current_regime
            self.current_regime = new_regime
            self._regime_duration = 0
            self._last_regime_change = datetime.now(timezone.utc)

            logger.info(
                "Regime transition: %s → %s",
                prev_regime.value,
                new_regime.value,
            )

        self._regime_duration += 1

        transition_prob = self._estimate_transition_probability(observations)

        regimes.append({
            "regime_id": f"reg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "current_regime": self.current_regime.value,
            "previous_regime": (
                self.regime_history[-1]["current_regime"] if self.regime_history else None
            ),
            "regime_duration": self._regime_duration,
            "transition_probability": transition_prob,
            "confidence": 0.75,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "characteristics": self._regime_characteristics(self.current_regime),
        })

        self.regime_history.append(regimes[-1])

        return {
            "regimes": regimes,
            "current_regime": self.current_regime.value,
            "duration": self._regime_duration,
        }

    # ------------------------------------------------------------------
    # Regime Classification
    # ------------------------------------------------------------------

    def _classify_regime(
        self,
        observations: List[Dict[str, Any]],
    ) -> MarketRegime:
        """Classify market regime from observations.

        In production, this would use ML models, statistical tests,
        and technical indicators on full time series data.
        """
        # Count observation categories for regime hints
        price_signal = 0
        vol_signal = 0
        corr_normal = True

        for obs in observations:
            category = obs.get("category", "")
            details = obs.get("details", {})

            if category == "price":
                direction = details.get("direction", "")
                if direction == "bullish":
                    price_signal += 1
                elif direction == "bearish":
                    price_signal -= 1

            elif category == "volatility":
                level = details.get("level", "")
                if level in ("elevated", "extreme"):
                    vol_signal += 1
                elif level == "suppressed":
                    vol_signal -= 1

            elif category == "correlation":
                breakdowns = details.get("breakdowns", [])
                if breakdowns:
                    corr_normal = False

        # Determine regime
        if vol_signal >= 1:
            if price_signal > 0:
                return MarketRegime.TRENDING_BULL
            return MarketRegime.HIGH_VOLATILITY
        elif vol_signal <= -1:
            return MarketRegime.LOW_VOLATILITY

        if price_signal > 1:
            return MarketRegime.RISK_ON
        elif price_signal < -1:
            return MarketRegime.RISK_OFF
        elif price_signal == 0:
            return MarketRegime.SIDEWAYS

        if not corr_normal:
            return MarketRegime.TRANSITION

        return MarketRegime.TRENDING_BULL

    def _estimate_transition_probability(
        self,
        observations: List[Dict[str, Any]],
    ) -> float:
        """Estimate probability of regime transition."""
        # Higher probability when indicators are mixed
        signals = 0
        for obs in observations:
            details = obs.get("details", {})
            category = obs.get("category", "")

            if category == "cross_asset" and details.get("status") != "normal":
                signals += 1
            if category == "correlation" and details.get("breakdowns"):
                signals += 1

        return min(0.1 + signals * 0.15, 0.8)

    def _regime_characteristics(self, regime: MarketRegime) -> Dict[str, Any]:
        """Get characteristics for a given regime."""
        characteristics = {
            MarketRegime.TRENDING_BULL: {
                "momentum_favorable": True,
                "vol_targeting": "adaptive",
                "preferred_factors": ["momentum", "growth", "quality"],
                "risk_appetite": "high",
            },
            MarketRegime.TRENDING_BEAR: {
                "momentum_favorable": False,
                "vol_targeting": "tight",
                "preferred_factors": ["low_vol", "quality", "value"],
                "risk_appetite": "low",
            },
            MarketRegime.HIGH_VOLATILITY: {
                "momentum_favorable": False,
                "vol_targeting": "reduced",
                "preferred_factors": ["low_vol", "momentum", "quality"],
                "risk_appetite": "cautious",
            },
            MarketRegime.LOW_VOLATILITY: {
                "momentum_favorable": True,
                "vol_targeting": "expanded",
                "preferred_factors": ["carry", "value", "momentum"],
                "risk_appetite": "moderate",
            },
            MarketRegime.TRANSITION: {
                "momentum_favorable": False,
                "vol_targeting": "conservative",
                "preferred_factors": ["quality", "low_vol"],
                "risk_appetite": "defensive",
            },
            MarketRegime.SIDEWAYS: {
                "momentum_favorable": False,
                "vol_targeting": "neutral",
                "preferred_factors": ["mean_reversion", "pairs"],
                "risk_appetite": "neutral",
            },
        }
        return characteristics.get(regime, {})
