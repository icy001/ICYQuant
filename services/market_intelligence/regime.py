from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MarketRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRISIS = "CRISIS"
    RECOVERY = "RECOVERY"
    BUBBLE = "BUBBLE"


class VolatilityRegime(str, Enum):
    LOW_VOL = "LOW_VOL"
    NORMAL = "NORMAL"
    HIGH_VOL = "HIGH_VOL"
    EXTREME = "EXTREME"


@dataclass
class RegimeIndicators:
    trend_strength: float  # -1 to 1
    volatility: float
    volume_trend: str  # RISING / FALLING / STABLE
    breadth: float  # 0 to 1, % of stocks above MA
    momentum: float
    vix_level: float
    credit_spread: float


@dataclass
class RegimeReport:
    regime: MarketRegime
    volatility_regime: VolatilityRegime
    confidence: float  # 0-1
    indicators: RegimeIndicators
    transition_probability: float = 0.0
    description: str = ""
    recommendations: List[str] = field(default_factory=list)


class MarketRegimeDetector:
    """Market Regime Detection Engine - identifies the current market regime."""

    def __init__(self):
        self.history: List[MarketRegime] = []
        self.bull_threshold = 0.3
        self.bear_threshold = -0.3

    def detect(self, data):
        """Detect the current market regime.

        Args:
            data: Market data - can be RegimeIndicators dataclass or dict/symbol.

        Returns:
            Dict containing regime detection result.
        """
        if isinstance(data, RegimeIndicators):
            return self._detect_regime(data)
        return {"regime": data}

    def _detect_regime(self, indicators: RegimeIndicators) -> dict:
        regime = self._classify_regime(indicators)
        vol_regime = self._classify_volatility(indicators.volatility)
        confidence = self._calculate_confidence(indicators)

        self.history.append(regime)

        return {
            "regime": {
                "regime": regime.value,
                "volatility_regime": vol_regime.value,
                "confidence": round(confidence, 2),
                "trend_strength": round(indicators.trend_strength, 2),
                "volatility": round(indicators.volatility, 4),
                "momentum": round(indicators.momentum, 2),
                "breadth": round(indicators.breadth, 2),
                "vix_level": round(indicators.vix_level, 2),
                "description": self._describe_regime(regime),
                "recommendations": self._generate_recommendations(regime, indicators),
            }
        }

    def _classify_regime(self, indicators: RegimeIndicators) -> MarketRegime:
        if indicators.vix_level > 40:
            return MarketRegime.CRISIS

        if indicators.volatility > 0.04:
            return MarketRegime.HIGH_VOLATILITY

        if indicators.trend_strength > self.bull_threshold:
            if indicators.momentum > 0.8:
                return MarketRegime.BUBBLE
            return MarketRegime.BULL

        if indicators.trend_strength < self.bear_threshold:
            return MarketRegime.BEAR

        if abs(indicators.trend_strength) < 0.1:
            return MarketRegime.SIDEWAYS

        return MarketRegime.RECOVERY if indicators.trend_strength > 0 else MarketRegime.BEAR

    def _classify_volatility(self, vol: float) -> VolatilityRegime:
        if vol < 0.01:
            return VolatilityRegime.LOW_VOL
        elif vol < 0.02:
            return VolatilityRegime.NORMAL
        elif vol < 0.04:
            return VolatilityRegime.HIGH_VOL
        return VolatilityRegime.EXTREME

    def _calculate_confidence(self, indicators: RegimeIndicators) -> float:
        base = 0.5
        if abs(indicators.trend_strength) > 0.5:
            base += 0.2
        if indicators.breadth > 0.7 or indicators.breadth < 0.3:
            base += 0.15
        if abs(indicators.momentum) > 0.5:
            base += 0.15
        return min(1.0, base)

    def _describe_regime(self, regime: MarketRegime) -> str:
        descriptions = {
            MarketRegime.BULL: "Broad market uptrend with positive momentum",
            MarketRegime.BEAR: "Broad market downtrend with negative momentum",
            MarketRegime.SIDEWAYS: "Range-bound market with no clear direction",
            MarketRegime.HIGH_VOLATILITY: "Elevated volatility with large price swings",
            MarketRegime.CRISIS: "Extreme market stress with panic selling",
            MarketRegime.RECOVERY: "Market recovering from a downturn",
            MarketRegime.BUBBLE: "Unsustainable rally with extreme momentum",
        }
        return descriptions.get(regime, "Unknown market regime")

    def _generate_recommendations(self, regime: MarketRegime, indicators: RegimeIndicators) -> List[str]:
        recs = []
        if regime == MarketRegime.BULL:
            recs.append("Favor risk-on positions")
            recs.append("Consider increasing equity exposure")
        elif regime == MarketRegime.BEAR:
            recs.append("Reduce risk exposure")
            recs.append("Consider hedging strategies")
        elif regime == MarketRegime.CRISIS:
            recs.append("Move to cash or safe havens")
            recs.append("Halt all new positions")
        elif regime == MarketRegime.HIGH_VOLATILITY:
            recs.append("Reduce position sizes")
            recs.append("Tighten stop-loss levels")
        elif regime == MarketRegime.SIDEWAYS:
            recs.append("Focus on relative value strategies")
            recs.append("Consider options premium strategies")
        return recs
