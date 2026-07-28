"""Commodity Intelligence Engine.

Analyzes major commodity markets (gold, oil, copper, natural gas)
and interprets their price signals for global economic conditions,
inflation expectations, and industrial demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CommodityResult:
    """Result of commodity intelligence analysis.

    Attributes:
        commodity: Commodity name/ticker.
        price: Current price level.
        signal: Derived trading/investment signal.
        signal_strength: Signal confidence [0.0, 1.0].
        macro_signal: Macroeconomic implication.
        description: Human-readable summary.
        confidence: Analysis confidence.
        trend: Price trend direction.
        timestamp: Analysis timestamp.
    """

    commodity: str = ""
    price: float = 0.0
    signal: str = "NEUTRAL"
    signal_strength: float = 0.5
    macro_signal: str = ""
    description: str = ""
    confidence: float = 0.5
    trend: str = "stable"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_bullish(self) -> bool:
        return self.signal == "BULLISH"

    @property
    def is_bearish(self) -> bool:
        return self.signal == "BEARISH"


class CommodityIntelligenceEngine:
    """Analyzes commodity market signals and macro implications.

    Evaluates gold, oil, copper, and natural gas prices to derive
    trading signals and macroeconomic condition assessments.

    Attributes:
        price_history: Per-commodity price history.
        trend_window: Window for trend calculation.
    """

    def __init__(self) -> None:
        self.price_history: dict[str, list[float]] = {}
        self.trend_window: int = 20

    # --- Analysis ---

    def analyze(self, commodity: str, price: float | None = None, **kwargs: Any) -> dict[str, Any]:
        """Analyze a commodity's signal and macro implications.

        Args:
            commodity: Commodity name (gold, oil, copper, natgas).
            price: Current price.
            **kwargs: Additional data (dollar_trend, etc.).

        Returns:
            Dict with signal analysis.
        """
        p = price if price is not None else 0.0
        result = self.analyze_full(commodity, p)
        return {
            "signal": result.signal,
            "commodity": commodity,
            "price": p,
            "macro_signal": result.macro_signal,
            "description": result.description,
        }

    def analyze_full(self, commodity: str, price: float) -> CommodityResult:
        """Full commodity analysis.

        Args:
            commodity: Commodity name.
            price: Current price.

        Returns:
            CommodityResult.
        """
        hist = self.price_history.setdefault(commodity, [])
        hist.append(price)
        if len(hist) > 200:
            hist = hist[-200:]
            self.price_history[commodity] = hist

        trend = self._compute_trend(commodity)
        signal = self._derive_signal(commodity, price, trend)
        macro_signal = self._derive_macro_signal(commodity, signal, trend)
        confidence = self._compute_confidence(commodity, trend)
        description = self._generate_description(commodity, signal, macro_signal, price, trend)

        return CommodityResult(
            commodity=commodity,
            price=price,
            signal=signal,
            signal_strength=confidence,
            macro_signal=macro_signal,
            description=description,
            confidence=confidence,
            trend=trend,
        )

    def analyze_gold(self, price: float, dollar_trend: str = "stable") -> CommodityResult:
        """Analyze gold with dollar context.

        Args:
            price: Gold price.
            dollar_trend: USD trend direction.

        Returns:
            CommodityResult for gold.
        """
        result = self.analyze_full("gold", price)
        if dollar_trend in ("depreciation", "strong_depreciation"):
            if result.signal == "NEUTRAL":
                result.signal = "BULLISH"
                result.macro_signal = "Risk hedging demand increasing"
        elif dollar_trend in ("appreciation", "strong_appreciation"):
            if result.signal == "NEUTRAL":
                result.signal = "BEARISH"
        return result

    def analyze_oil(self, price: float) -> CommodityResult:
        """Analyze crude oil."""
        return self.analyze_full("oil", price)

    def analyze_copper(self, price: float) -> CommodityResult:
        """Analyze copper (Dr. Copper - economic indicator)."""
        return self.analyze_full("copper", price)

    # --- Macro Signals ---

    def get_inflation_signal(self) -> str:
        """Get inflation expectation signal from commodity complex."""
        gold_trend = self._compute_trend("gold")
        oil_trend = self._compute_trend("oil")
        if gold_trend == "strong_rising" and oil_trend in ("rising", "strong_rising"):
            return "inflation_accelerating"
        elif gold_trend == "rising" and oil_trend == "rising":
            return "inflation_rising"
        elif gold_trend == "falling" and oil_trend == "falling":
            return "disinflation"
        return "stable"

    def get_growth_signal(self) -> str:
        """Get economic growth signal from industrial commodities."""
        copper_trend = self._compute_trend("copper")
        oil_trend = self._compute_trend("oil")
        if copper_trend in ("rising", "strong_rising"):
            return "growth_accelerating"
        elif copper_trend in ("falling", "strong_falling"):
            return "growth_decelerating"
        return "growth_stable"

    # --- Internal ---

    def _compute_trend(self, commodity: str) -> str:
        hist = self.price_history.get(commodity, [])
        if len(hist) < 5:
            return "stable"
        recent = hist[-self.trend_window:] if len(hist) >= self.trend_window else hist
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / (len(recent) - mid)
        if first == 0:
            return "stable"
        change = (second - first) / first * 100
        if change > 10:
            return "strong_rising"
        elif change > 3:
            return "rising"
        elif change < -10:
            return "strong_falling"
        elif change < -3:
            return "falling"
        return "stable"

    def _derive_signal(self, commodity: str, price: float, trend: str) -> str:
        if trend in ("strong_rising",):
            return "BULLISH"
        elif trend == "rising":
            return "BULLISH"
        elif trend in ("strong_falling",):
            return "BEARISH"
        elif trend == "falling":
            return "BEARISH"
        return "NEUTRAL"

    def _derive_macro_signal(self, commodity: str, signal: str, trend: str) -> str:
        macros: dict[str, dict[str, str]] = {
            "gold": {
                "BULLISH": "Risk-off / inflation hedging demand increasing",
                "BEARISH": "Risk appetite strong / real yields attractive",
            },
            "copper": {
                "BULLISH": "Global industrial demand improving",
                "BEARISH": "Global manufacturing slowing",
            },
            "oil": {
                "BULLISH": "Supply tightness or demand recovery",
                "BEARISH": "Demand weakness or supply surplus",
            },
            "natgas": {
                "BULLISH": "Energy supply concerns or seasonal demand",
                "BEARISH": "Mild weather or oversupply",
            },
        }
        return macros.get(commodity, {}).get(signal, "No clear macro signal")

    def _compute_confidence(self, commodity: str, trend: str) -> float:
        confidence = 0.4
        if trend != "stable":
            confidence += 0.2
        if trend in ("strong_rising", "strong_falling"):
            confidence += 0.2
        hist = self.price_history.get(commodity, [])
        if len(hist) > 30:
            confidence += 0.1
        return min(1.0, confidence)

    def _generate_description(self, commodity: str, signal: str, macro: str, price: float, trend: str) -> str:
        return f"{commodity.upper()}: {signal} (${price:.1f}, trend={trend}) → {macro}"

    def clear(self) -> None:
        self.price_history.clear()
