"""Sentiment Alpha Generator.

Converts sentiment intelligence signals into quantifiable alpha factors
that can feed into the Alpha Research Engine for strategy development.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .record import SentimentAlphaSignal, SentimentRecord, SentimentLabel


@dataclass
class SentimentAlphaResult:
    """Result of sentiment alpha generation.

    Attributes:
        signals: Generated alpha signals.
        signal_count: Number of signals generated.
        aggregate_score: Composite alpha score across all signals.
        metadata: Generation context and parameters.
        timestamp: Generation timestamp.
    """

    signals: list[SentimentAlphaSignal] = field(default_factory=list)
    signal_count: int = 0
    aggregate_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_signals(self) -> bool:
        return len(self.signals) > 0

    @property
    def actionable_signals(self) -> list[SentimentAlphaSignal]:
        return [s for s in self.signals if s.is_actionable]

    @property
    def bullish_count(self) -> int:
        return sum(1 for s in self.signals if s.direction > 0)

    @property
    def bearish_count(self) -> int:
        return sum(1 for s in self.signals if s.direction < 0)


class SentimentAlphaGenerator:
    """Generates alpha signals from sentiment intelligence data.

    Produces multiple sentiment factor types:
    - News Sentiment Factor
    - Social Momentum Factor
    - Fear Greed Factor
    - Divergence Factor
    - Composite Sentiment Factor

    Attributes:
        signal_counter: Auto-incrementing signal ID counter.
        generated_signals: History of all generated signals.
    """

    def __init__(self) -> None:
        self.signal_counter: int = 0
        self.generated_signals: list[SentimentAlphaSignal] = []

    # --- Generation ---

    def generate(self, sentiment: float) -> dict[str, Any]:
        """Generate alpha signal from a raw sentiment value.

        Args:
            sentiment: Sentiment score [-1.0, 1.0] or [0, 100].

        Returns:
            Dict with alpha signal details.
        """
        if -1.0 <= sentiment <= 1.0:
            normalized = (sentiment + 1.0) / 2.0 * 100.0
        else:
            normalized = sentiment

        return {
            "alpha": sentiment,
            "normalized": normalized,
            "strength": abs(sentiment) if abs(sentiment) <= 1.0 else abs(sentiment - 50.0) / 50.0,
        }

    def generate_signal(
        self,
        symbol: str,
        factor_name: str,
        value: float,
        direction: int,
        confidence: float,
        horizon: int = 5,
        components: dict[str, float] | None = None,
    ) -> SentimentAlphaSignal:
        """Generate a single alpha signal.

        Args:
            symbol: Target trading symbol.
            factor_name: Name of the factor.
            value: Signal value (z-score style).
            direction: 1=bullish, -1=bearish, 0=neutral.
            confidence: Signal confidence [0.0, 1.0].
            horizon: Expected signal horizon in days.
            components: Contributing sub-factors.

        Returns:
            SentimentAlphaSignal.
        """
        self.signal_counter += 1
        signal = SentimentAlphaSignal(
            signal_id=f"SENT_{self.signal_counter:06d}",
            symbol=symbol,
            factor_name=factor_name,
            value=value,
            direction=direction,
            confidence=confidence,
            horizon=horizon,
            components=components or {},
        )
        self.generated_signals.append(signal)
        return signal

    def generate_from_records(
        self,
        symbol: str,
        records: list[SentimentRecord],
        fear_greed_score: float | None = None,
    ) -> SentimentAlphaResult:
        """Generate alpha signals from a batch of sentiment records.

        Args:
            symbol: Target symbol.
            records: List of sentiment records.
            fear_greed_score: Optional Fear & Greed index score.

        Returns:
            SentimentAlphaResult with generated signals.
        """
        if not records:
            return SentimentAlphaResult()

        signals: list[SentimentAlphaSignal] = []

        # 1. News Sentiment Factor
        news_score = self._compute_news_factor(symbol, records)
        if news_score is not None:
            signals.append(news_score)

        # 2. Social Momentum Factor
        social_score = self._compute_social_factor(symbol, records)
        if social_score is not None:
            signals.append(social_score)

        # 3. Fear Greed Factor
        if fear_greed_score is not None:
            fg_signal = self._compute_fear_greed_factor(symbol, fear_greed_score)
            if fg_signal is not None:
                signals.append(fg_signal)

        # 4. Composite Factor
        if len(signals) >= 1:
            composite = self._compute_composite_factor(symbol, signals)
            if composite is not None:
                signals.append(composite)

        # Aggregate
        aggregate = self._aggregate_signals(signals)

        return SentimentAlphaResult(
            signals=signals,
            signal_count=len(signals),
            aggregate_score=aggregate,
            metadata={"symbol": symbol, "record_count": len(records)},
        )

    # --- Factor Computations ---

    def _compute_news_factor(
        self, symbol: str, records: list[SentimentRecord]
    ) -> SentimentAlphaSignal | None:
        """Compute news sentiment alpha factor."""
        news_records = [r for r in records if r.source.value in ("news", "analyst_report")]
        if not news_records:
            return None

        avg_score = sum(r.score for r in news_records) / len(news_records)
        avg_confidence = sum(r.confidence for r in news_records) / len(news_records)
        direction = 1 if avg_score > 0.1 else -1 if avg_score < -0.1 else 0

        return self.generate_signal(
            symbol=symbol,
            factor_name="news_sentiment",
            value=avg_score,
            direction=direction,
            confidence=avg_confidence,
            components={"avg_score": avg_score, "count": float(len(news_records))},
        )

    def _compute_social_factor(
        self, symbol: str, records: list[SentimentRecord]
    ) -> SentimentAlphaSignal | None:
        """Compute social media momentum alpha factor."""
        social_records = [
            r for r in records if r.source.value in ("social_media", "forum")
        ]
        if not social_records:
            return None

        avg_score = sum(r.score for r in social_records) / len(social_records)
        avg_confidence = sum(r.confidence for r in social_records) / len(social_records)

        # Social sentiment has higher noise, so require more conviction
        adjusted_confidence = avg_confidence * 0.85
        direction = 1 if avg_score > 0.15 else -1 if avg_score < -0.15 else 0

        return self.generate_signal(
            symbol=symbol,
            factor_name="social_momentum",
            value=avg_score,
            direction=direction,
            confidence=adjusted_confidence,
            components={"avg_score": avg_score, "count": float(len(social_records))},
        )

    def _compute_fear_greed_factor(
        self, symbol: str, fear_greed_score: float
    ) -> SentimentAlphaSignal | None:
        """Compute Fear & Greed alpha factor."""
        # Map Fear & Greed [0,100] to z-score style
        # Extreme fear (<25) = bullish contrarian, extreme greed (>75) = bearish
        if fear_greed_score <= 25.0:
            direction = 1
            value = (25.0 - fear_greed_score) / 25.0  # 0 to 1
            confidence = 0.7
        elif fear_greed_score >= 75.0:
            direction = -1
            value = -(fear_greed_score - 75.0) / 25.0  # -1 to 0
            confidence = 0.7
        else:
            direction = 0
            value = 0.0
            confidence = 0.3

        if direction == 0:
            return None

        return self.generate_signal(
            symbol=symbol,
            factor_name="fear_greed_contrarian",
            value=value,
            direction=direction,
            confidence=confidence,
            components={"fear_greed_score": fear_greed_score},
        )

    def _compute_composite_factor(
        self, symbol: str, signals: list[SentimentAlphaSignal]
    ) -> SentimentAlphaSignal | None:
        """Compute composite sentiment alpha from multiple factor signals."""
        if not signals:
            return None

        total_weight = 0.0
        weighted_value = 0.0

        # Weight by confidence
        for s in signals:
            weight = s.confidence
            weighted_value += s.value * weight
            total_weight += weight

        if total_weight == 0:
            return None

        composite_value = weighted_value / total_weight
        direction = 1 if composite_value > 0.05 else -1 if composite_value < -0.05 else 0
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return self.generate_signal(
            symbol=symbol,
            factor_name="composite_sentiment",
            value=composite_value,
            direction=direction,
            confidence=avg_confidence,
            components={s.factor_name: s.value for s in signals},
        )

    def _aggregate_signals(self, signals: list[SentimentAlphaSignal]) -> float:
        """Compute aggregate score across all signals."""
        if not signals:
            return 0.0
        actionable = [s for s in signals if s.is_actionable]
        if not actionable:
            return 0.0
        return sum(s.value * s.confidence for s in actionable) / len(actionable)

    # --- Query ---

    def get_signals_by_symbol(self, symbol: str) -> list[SentimentAlphaSignal]:
        """Get all generated signals for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Filtered list of signals.
        """
        return [s for s in self.generated_signals if s.symbol == symbol]

    def get_signals_by_factor(self, factor_name: str) -> list[SentimentAlphaSignal]:
        """Get all generated signals for a factor.

        Args:
            factor_name: Factor name.

        Returns:
            Filtered list of signals.
        """
        return [s for s in self.generated_signals if s.factor_name == factor_name]

    def get_latest_signals(self, limit: int = 10) -> list[SentimentAlphaSignal]:
        """Get the most recently generated signals.

        Args:
            limit: Maximum number to return.

        Returns:
            Most recent signals.
        """
        return self.generated_signals[-limit:]

    def clear(self) -> None:
        """Reset generator state."""
        self.signal_counter = 0
        self.generated_signals.clear()
