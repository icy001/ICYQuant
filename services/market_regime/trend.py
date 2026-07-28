"""Trend Regime Detector – identify market trend direction and strength."""

from typing import Any, Dict, List, Optional, Tuple


class TrendDetector:
    """Detects market trend regimes using multi-dimensional signals.

    Analyzes:
    - Price-based trend (moving averages, price relative to MAs)
    - Momentum (rate of change, MACD)
    - Market breadth (advance/decline ratio)
    - Trend strength (ADX, consecutive bars)

    Outputs a trend regime classification with direction and strength.
    """

    # Trend direction thresholds
    STRONG_UP = "STRONG_UPTREND"
    UP = "UPTREND"
    WEAK_UP = "WEAK_UPTREND"
    NEUTRAL = "NEUTRAL"
    WEAK_DOWN = "WEAK_DOWNTREND"
    DOWN = "DOWNTREND"
    STRONG_DOWN = "STRONG_DOWNTREND"

    TREND_DIRECTIONS = [STRONG_UP, UP, WEAK_UP, NEUTRAL, WEAK_DOWN, DOWN, STRONG_DOWN]

    def __init__(self,
                 ma_fast: int = 20,
                 ma_slow: int = 50,
                 ma_long: int = 200,
                 adx_threshold: float = 25.0):
        self._ma_fast = ma_fast
        self._ma_slow = ma_slow
        self._ma_long = ma_long
        self._adx_threshold = adx_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, data: dict) -> dict:
        """Detect trend from market data (legacy interface).

        Returns simple dict for backward compatibility.
        """
        trend = self.classify_trend(data)
        return {"trend": trend}

    def classify_trend(self, data: dict) -> str:
        """Classify trend direction from market data.

        Args:
            data: dict with optional keys:
                - price: current price
                - ma_fast: fast moving average value
                - ma_slow: slow moving average value
                - ma_long: long moving average value
                - momentum: rate of change (positive/negative)
                - adx: average directional index value
                - breadth: advance/decline ratio
                - consecutive_up: number of consecutive up bars
                - consecutive_down: number of consecutive down bars

        Returns:
            Trend direction string (STRONG_UPTREND, UPTREND, ...)
        """
        signals = self._extract_trend_signals(data)
        score = sum(signals.values())

        # Determine direction based on composite score
        if score >= 4:
            return self.STRONG_UP
        elif score >= 2:
            return self.UP
        elif score >= 1:
            return self.WEAK_UP
        elif score <= -4:
            return self.STRONG_DOWN
        elif score <= -2:
            return self.DOWN
        elif score <= -1:
            return self.WEAK_DOWN
        else:
            return self.NEUTRAL

    def trend_strength(self, data: dict) -> float:
        """Calculate trend strength as a continuous value (-1.0 to 1.0).

        -1.0 = strongest downtrend, 1.0 = strongest uptrend, 0.0 = neutral
        """
        signals = self._extract_trend_signals(data)
        if not signals:
            return 0.0

        raw = sum(signals.values())
        # Normalize: each signal is -1/0/+1, max 6 signals
        max_possible = len(signals)
        if max_possible == 0:
            return 0.0

        normalized = raw / max_possible
        return round(max(-1.0, min(1.0, normalized)), 3)

    def detect_with_details(self, data: dict) -> dict:
        """Full trend detection with details."""
        trend = self.classify_trend(data)
        strength = self.trend_strength(data)
        signals = self._extract_trend_signals(data)
        confidence = self._confidence_from_signals(signals)

        return {
            "trend": trend,
            "strength": strength,
            "confidence": confidence,
            "signals": {k: v for k, v in signals.items() if v != 0},
            "adx_reading": data.get("adx", 0.0),
        }

    # ------------------------------------------------------------------
    # Signal extraction
    # ------------------------------------------------------------------

    def _extract_trend_signals(self, data: dict) -> Dict[str, int]:
        """Extract trend signals, each returning -1, 0, or +1."""
        signals = {}

        # 1. Price vs fast MA
        price = data.get("price")
        ma_fast = data.get("ma_fast")
        if price is not None and ma_fast is not None and ma_fast > 0:
            signals["price_vs_ma_fast"] = 1 if price > ma_fast else -1

        # 2. Price vs slow MA
        ma_slow = data.get("ma_slow")
        if price is not None and ma_slow is not None and ma_slow > 0:
            signals["price_vs_ma_slow"] = 1 if price > ma_slow else -1

        # 3. Fast MA vs Slow MA (golden/death cross)
        ma_long = data.get("ma_long")
        if ma_fast is not None and ma_slow is not None and ma_slow > 0:
            signals["ma_cross"] = 1 if ma_fast > ma_slow else -1

        # 4. Price vs long MA (bull/bear market filter)
        if price is not None and ma_long is not None and ma_long > 0:
            signals["price_vs_ma_long"] = 1 if price > ma_long else -1

        # 5. Momentum
        momentum = data.get("momentum")
        if momentum is not None:
            if momentum > 5:
                signals["momentum"] = 1
            elif momentum < -5:
                signals["momentum"] = -1
            else:
                signals["momentum"] = 0

        # 6. ADX (trend strength confirmation)
        adx = data.get("adx")
        if adx is not None:
            if adx >= self._adx_threshold:
                signals["adx_strong"] = 1  # strong trend, direction from other signals
            else:
                signals["adx_strong"] = 0  # weak/no trend → neutral (directionless)

        # 7. Market breadth
        breadth = data.get("breadth")
        if breadth is not None:
            if breadth > 1.5:
                signals["breadth"] = 1
            elif breadth < 0.67:
                signals["breadth"] = -1
            else:
                signals["breadth"] = 0

        # 8. Consecutive direction
        consecutive_up = data.get("consecutive_up", 0)
        consecutive_down = data.get("consecutive_down", 0)
        if consecutive_up >= 5:
            signals["consecutive"] = 1
        elif consecutive_down >= 5:
            signals["consecutive"] = -1
        else:
            signals["consecutive"] = 0

        return signals

    def _confidence_from_signals(self, signals: Dict[str, int]) -> float:
        """Compute confidence from signal consistency."""
        non_zero = [v for v in signals.values() if v != 0]
        if not non_zero:
            return 0.5

        # High confidence if all signals agree
        positive = sum(1 for v in non_zero if v > 0)
        negative = sum(1 for v in non_zero if v < 0)

        if positive + negative == 0:
            return 0.5

        agreement = max(positive, negative) / (positive + negative)
        return round(agreement, 2)

    # ------------------------------------------------------------------
    # Regime mapping
    # ------------------------------------------------------------------

    def to_regime(self, trend: str) -> str:
        """Map trend direction to regime state."""
        mapping = {
            self.STRONG_UP: "BULL_TREND",
            self.UP: "BULL_TREND",
            self.WEAK_UP: "BULL_TREND",
            self.NEUTRAL: "SIDEWAYS",
            self.WEAK_DOWN: "BEAR_TREND",
            self.DOWN: "BEAR_TREND",
            self.STRONG_DOWN: "BEAR_TREND",
        }
        return mapping.get(trend, "SIDEWAYS")
