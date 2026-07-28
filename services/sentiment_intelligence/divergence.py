"""Sentiment Divergence Detector.

Detects divergences between price action and market sentiment,
identifying potential trend reversals and alpha opportunities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .record import SentimentDivergence


@dataclass
class DivergenceResult:
    """Result of divergence detection.

    Attributes:
        divergences: List of detected divergences.
        has_divergence: Whether any divergence was found.
        analysis: Summary analysis of detected divergences.
        timestamp: Detection timestamp.
    """

    divergences: list[SentimentDivergence] = field(default_factory=list)
    has_divergence: bool = False
    analysis: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def count(self) -> int:
        return len(self.divergences)

    @property
    def bullish_count(self) -> int:
        return sum(1 for d in self.divergences if d.is_bullish_divergence)

    @property
    def bearish_count(self) -> int:
        return sum(1 for d in self.divergences if d.is_bearish_divergence)

    @property
    def significant_count(self) -> int:
        return sum(1 for d in self.divergences if d.is_significant)


class DivergenceDetector:
    """Detects price-sentiment divergences for contrarian signals.

    Identifies two key patterns:
    - Bullish Divergence: Price falling while sentiment improving (potential bottom)
    - Bearish Divergence: Price rising while sentiment deteriorating (potential top)

    Attributes:
        min_strength: Minimum strength to flag a divergence.
        lookback_window: Default lookback window for analysis.
        detected_divergences: History of detected divergences.
    """

    def __init__(self) -> None:
        self.min_strength: float = 0.3
        self.lookback_window: int = 5
        self.detected_divergences: list[SentimentDivergence] = []

    # --- Detection ---

    def detect(
        self,
        price: list[float] | None = None,
        sentiment: list[float] | None = None,
        symbol: str = "",
    ) -> bool:
        """Quick check for divergence existence.

        Args:
            price: List of recent prices (most recent last).
            sentiment: List of recent sentiment scores (most recent last).
            symbol: Trading symbol.

        Returns:
            True if a divergence is detected, False otherwise.
        """
        result = self.analyze(price, sentiment, symbol)
        return result.has_divergence

    def analyze(
        self,
        price: list[float] | None = None,
        sentiment: list[float] | None = None,
        symbol: str = "",
    ) -> DivergenceResult:
        """Full divergence analysis.

        Args:
            price: List of recent prices (most recent last).
            sentiment: List of recent sentiment scores (most recent last).
            symbol: Trading symbol.

        Returns:
            DivergenceResult with detected divergences.
        """
        if not price or not sentiment or len(price) < 2 or len(sentiment) < 2:
            return DivergenceResult(analysis="Insufficient data for divergence analysis.")

        divergences: list[SentimentDivergence] = []

        # Compute trends
        price_trend = self._compute_trend(price)
        sentiment_trend = self._compute_trend(sentiment)

        # Bearish divergence: price up, sentiment down
        if price_trend > 0 and sentiment_trend < 0:
            strength = min(1.0, abs(price_trend) * abs(sentiment_trend) / 50.0)
            confidence = self._compute_confidence(price, sentiment, "bearish")
            if strength >= self.min_strength and confidence >= 0.3:
                divergences.append(
                    SentimentDivergence(
                        symbol=symbol,
                        divergence_type="bearish",
                        price_trend="rising",
                        sentiment_trend="falling",
                        strength=strength,
                        confidence=confidence,
                        window=len(price),
                        expected_action="reduce_long / consider_short",
                    )
                )

        # Bullish divergence: price down, sentiment up
        if price_trend < 0 and sentiment_trend > 0:
            strength = min(1.0, abs(price_trend) * abs(sentiment_trend) / 50.0)
            confidence = self._compute_confidence(price, sentiment, "bullish")
            if strength >= self.min_strength and confidence >= 0.3:
                divergences.append(
                    SentimentDivergence(
                        symbol=symbol,
                        divergence_type="bullish",
                        price_trend="falling",
                        sentiment_trend="rising",
                        strength=strength,
                        confidence=confidence,
                        window=len(price),
                        expected_action="accumulate_long / reduce_short",
                    )
                )

        # Save detected divergences
        self.detected_divergences.extend(divergences)

        analysis = self._summarize(divergences)
        return DivergenceResult(
            divergences=divergences,
            has_divergence=len(divergences) > 0,
            analysis=analysis,
        )

    # --- Analysis Helpers ---

    def get_divergence_history(
        self, symbol: str | None = None
    ) -> list[SentimentDivergence]:
        """Get historical divergences, optionally filtered by symbol.

        Args:
            symbol: Optional symbol filter.

        Returns:
            Filtered list of divergences.
        """
        if symbol:
            return [d for d in self.detected_divergences if d.symbol == symbol]
        return list(self.detected_divergences)

    def get_active_signals(self) -> list[SentimentDivergence]:
        """Get significant divergences that are actionable.

        Returns:
            List of significant divergences.
        """
        return [d for d in self.detected_divergences if d.is_significant]

    # --- Internal ---

    def _compute_trend(self, values: list[float]) -> float:
        """Compute simple trend from a series of values.

        Args:
            values: List of values in chronological order.

        Returns:
            Trend direction and magnitude.
        """
        if len(values) < 2:
            return 0.0
        mid = len(values) // 2
        first_half = sum(values[:mid]) / mid
        second_half = sum(values[mid:]) / (len(values) - mid)
        if first_half == 0:
            return 0.0
        return ((second_half - first_half) / abs(first_half)) * 100.0

    def _compute_confidence(
        self, price: list[float], sentiment: list[float], dtype: str
    ) -> float:
        """Compute confidence in divergence detection.

        Args:
            price: Price series.
            sentiment: Sentiment series.
            dtype: Divergence type ('bullish' or 'bearish').

        Returns:
            Confidence [0.0, 1.0].
        """
        confidence = 0.3  # Base confidence

        # More data points = higher confidence
        if len(price) >= 10:
            confidence += 0.2

        # Monotonic trends are more confident
        if dtype == "bearish":
            price_mono = all(price[i] >= price[i - 1] for i in range(1, len(price)))
            sent_mono = all(
                sentiment[i] <= sentiment[i - 1] for i in range(1, len(sentiment))
            )
        else:
            price_mono = all(price[i] <= price[i - 1] for i in range(1, len(price)))
            sent_mono = all(
                sentiment[i] >= sentiment[i - 1] for i in range(1, len(sentiment))
            )

        if price_mono and sent_mono:
            confidence += 0.3
        elif price_mono or sent_mono:
            confidence += 0.15

        return min(1.0, confidence)

    def _summarize(self, divergences: list[SentimentDivergence]) -> str:
        """Generate summary analysis text.

        Args:
            divergences: List of detected divergences.

        Returns:
            Summary string.
        """
        if not divergences:
            return "No price-sentiment divergence detected."

        parts: list[str] = []
        for d in divergences:
            if d.is_bullish_divergence:
                parts.append(
                    f"Bullish divergence on {d.symbol}: "
                    f"price declining while sentiment improving "
                    f"(strength={d.strength:.2f}, confidence={d.confidence:.2f})"
                )
            else:
                parts.append(
                    f"Bearish divergence on {d.symbol}: "
                    f"price rising while sentiment deteriorating "
                    f"(strength={d.strength:.2f}, confidence={d.confidence:.2f})"
                )
        return " | ".join(parts)

    def clear(self) -> None:
        """Clear detected divergence history."""
        self.detected_divergences.clear()
