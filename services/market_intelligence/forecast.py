from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ForecastDirection(str, Enum):
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    FLAT = "FLAT"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


class ForecastHorizon(str, Enum):
    SHORT_TERM = "1D"
    MEDIUM_TERM = "1W"
    LONG_TERM = "1M"
    STRATEGIC = "3M"


@dataclass
class ForecastInput:
    symbol: str
    current_price: float
    volatility: float
    trend_strength: float
    sentiment_score: int
    macro_bias: str
    regime: str


@dataclass
class ForecastScenario:
    scenario_name: str
    direction: ForecastDirection
    target_price: float
    probability: float
    key_drivers: List[str]


@dataclass
class MarketForecast:
    symbol: str
    horizon: ForecastHorizon
    base_case: ForecastScenario
    bull_case: ForecastScenario
    bear_case: ForecastScenario
    expected_return: float
    confidence: float
    risk_level: str


class MarketForecastEngine:
    """Market Forecast Engine - generates multi-scenario market forecasts."""

    def __init__(self):
        self.forecast_history: List[MarketForecast] = []

    def forecast(self, data):
        """Generate a market forecast.

        Args:
            data: Forecast input - can be ForecastInput dataclass or dict/symbol.

        Returns:
            Dict containing forecast result.
        """
        if isinstance(data, ForecastInput):
            return self._generate_forecast(data)
        return {"forecast": data}

    def _generate_forecast(self, input_data: ForecastInput) -> dict:
        base_return = input_data.trend_strength * 0.05
        expected_return = self._adjust_by_sentiment(base_return, input_data.sentiment_score)
        expected_return = self._adjust_by_macro(expected_return, input_data.macro_bias)

        base_price = input_data.current_price
        bull_price = base_price * (1 + expected_return * 1.5)
        bear_price = base_price * (1 - expected_return * 1.5)

        confidence = self._calculate_confidence(input_data)

        return {
            "forecast": {
                "symbol": input_data.symbol,
                "current_price": base_price,
                "horizon": ForecastHorizon.MEDIUM_TERM.value,
                "base_case": {
                    "direction": ForecastDirection.UP.value if expected_return > 0 else ForecastDirection.DOWN.value,
                    "target_price": round(base_price * (1 + expected_return), 2),
                    "probability": 0.5,
                    "key_drivers": self._identify_drivers(input_data),
                },
                "bull_case": {
                    "direction": ForecastDirection.STRONG_UP.value,
                    "target_price": round(bull_price, 2),
                    "probability": 0.25,
                    "key_drivers": ["Positive surprise in macro data", "Strong momentum continuation"],
                },
                "bear_case": {
                    "direction": ForecastDirection.STRONG_DOWN.value,
                    "target_price": round(bear_price, 2),
                    "probability": 0.25,
                    "key_drivers": ["Adverse macro shock", "Sentiment reversal"],
                },
                "expected_return_pct": round(expected_return * 100, 2),
                "confidence": round(confidence, 2),
                "volatility": round(input_data.volatility, 4),
                "regime": input_data.regime,
            }
        }

    def _adjust_by_sentiment(self, base_return: float, sentiment_score: int) -> float:
        """Adjust return forecast by sentiment (contrarian adjustment at extremes)."""
        if sentiment_score >= 80:
            return base_return * 0.7
        elif sentiment_score <= 20:
            return base_return * 1.3
        return base_return

    def _adjust_by_macro(self, base_return: float, macro_bias: str) -> float:
        """Adjust return forecast by macro bias."""
        macro_multipliers = {
            "STRONGLY_BULLISH": 1.5,
            "BULLISH": 1.2,
            "NEUTRAL": 1.0,
            "BEARISH": 0.8,
            "STRONGLY_BEARISH": 0.5,
        }
        return base_return * macro_multipliers.get(macro_bias, 1.0)

    def _calculate_confidence(self, input_data: ForecastInput) -> float:
        base = 0.5
        if abs(input_data.trend_strength) > 0.3:
            base += 0.15
        if input_data.sentiment_score not in range(40, 61):
            base += 0.10
        if input_data.volatility < 0.02:
            base += 0.10
        if input_data.macro_bias in ("STRONGLY_BULLISH", "STRONGLY_BEARISH"):
            base += 0.15
        return min(1.0, base)

    def _identify_drivers(self, input_data: ForecastInput) -> List[str]:
        drivers = []
        if abs(input_data.trend_strength) > 0.3:
            drivers.append(f"Strong momentum: {input_data.trend_strength:.2f}")
        if input_data.sentiment_score > 60:
            drivers.append("Bullish sentiment supports upside")
        elif input_data.sentiment_score < 40:
            drivers.append("Bearish sentiment may limit upside")
        if "BULLISH" in input_data.macro_bias:
            drivers.append("Supportive macro environment")
        elif "BEARISH" in input_data.macro_bias:
            drivers.append("Challenging macro environment")
        if not drivers:
            drivers.append("Mixed signals - neutral outlook")
        return drivers
