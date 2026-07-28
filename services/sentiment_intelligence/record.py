"""Sentiment Intelligence data models.

Defines the core data structures for sentiment analysis including:
- SentimentRecord: raw sentiment data point
- SentimentEvent: detected sentiment event
- SentimentDivergence: price-sentiment divergence signal
- SentimentAlphaSignal: sentiment-derived alpha factor
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SentimentSource(str, Enum):
    """Data source for sentiment signals."""

    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    FORUM = "forum"
    ANALYST_REPORT = "analyst_report"
    OPTIONS_FLOW = "options_flow"
    MARKET_DATA = "market_data"
    FUND_FLOW = "fund_flow"
    CORPORATE_FILING = "corporate_filing"


class SentimentLabel(str, Enum):
    """Sentiment classification label."""

    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    SLIGHTLY_BULLISH = "slightly_bullish"
    NEUTRAL = "neutral"
    SLIGHTLY_BEARISH = "slightly_bearish"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class EmotionState(str, Enum):
    """Market emotion states for crowd psychology detection."""

    EUPHORIA = "euphoria"
    OPTIMISM = "optimism"
    NEUTRAL = "neutral"
    ANXIETY = "anxiety"
    FEAR = "fear"
    PANIC = "panic"
    CAPITULATION = "capitulation"
    DESPAIR = "despair"
    HOPE = "hope"
    RELIEF = "relief"


class FearGreedZone(str, Enum):
    """Fear & Greed index zones."""

    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class SentimentRecord:
    """A single sentiment data point from any source.

    Attributes:
        source: Origin of the sentiment data (news, social, options, etc.)
        content: Raw text content or data payload.
        timestamp: When the sentiment was captured.
        score: Normalized sentiment score [-1.0, 1.0] where positive=bullish.
        label: Classified sentiment label.
        confidence: Confidence level [0.0, 1.0] of the sentiment analysis.
        symbol: Optional associated trading symbol.
        metadata: Additional source-specific metadata.
        entity: Optional detected entity (company, sector, person).
        language: Language code of the content.
    """

    source: SentimentSource
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    score: float = 0.0
    label: SentimentLabel = SentimentLabel.NEUTRAL
    confidence: float = 0.5
    symbol: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    entity: str | None = None
    language: str = "en"

    def __post_init__(self) -> None:
        if self.score < -1.0:
            self.score = -1.0
        elif self.score > 1.0:
            self.score = 1.0
        if self.confidence < 0.0:
            self.confidence = 0.0
        elif self.confidence > 1.0:
            self.confidence = 1.0

    @property
    def is_positive(self) -> bool:
        return self.score > 0.0

    @property
    def is_negative(self) -> bool:
        return self.score < 0.0

    @property
    def is_extreme(self) -> bool:
        return abs(self.score) >= 0.8

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.6

    @property
    def strength(self) -> float:
        """Composite signal strength = score * confidence."""
        return self.score * self.confidence


@dataclass
class SentimentEvent:
    """A significant sentiment event detected in the market.

    Attributes:
        event_id: Unique event identifier.
        event_type: Type of sentiment event (spike, reversal, accumulation, etc.).
        description: Human-readable description of the event.
        timestamp: When the event was detected.
        intensity: Event intensity [0.0, 1.0].
        records: Associated sentiment records.
        affected_symbols: Symbols impacted by this event.
        expected_impact: Expected directional impact on prices.
        duration_estimate: Estimated duration of the sentiment effect (hours).
    """

    event_id: str
    event_type: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    intensity: float = 0.5
    records: list[SentimentRecord] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    expected_impact: str = "neutral"
    duration_estimate: float = 24.0

    @property
    def is_high_impact(self) -> bool:
        return self.intensity >= 0.7

    @property
    def record_count(self) -> int:
        return len(self.records)


@dataclass
class SentimentDivergence:
    """Price-sentiment divergence signal.

    Attributes:
        symbol: Trading symbol.
        divergence_type: "bullish" (price down, sentiment up) or "bearish" (price up, sentiment down).
        price_trend: Recent price movement description.
        sentiment_trend: Recent sentiment movement description.
        strength: Divergence strength [0.0, 1.0].
        confidence: Detection confidence [0.0, 1.0].
        timestamp: Detection time.
        window: Look-back window in days.
        expected_action: Suggested trading action.
    """

    symbol: str
    divergence_type: str
    price_trend: str = ""
    sentiment_trend: str = ""
    strength: float = 0.0
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    window: int = 5
    expected_action: str = ""

    @property
    def is_bullish_divergence(self) -> bool:
        return self.divergence_type == "bullish"

    @property
    def is_bearish_divergence(self) -> bool:
        return self.divergence_type == "bearish"

    @property
    def is_significant(self) -> bool:
        return self.strength >= 0.5 and self.confidence >= 0.5


@dataclass
class SentimentAlphaSignal:
    """Sentiment-derived alpha factor signal.

    Attributes:
        signal_id: Unique signal identifier.
        symbol: Target symbol.
        factor_name: Name of the sentiment factor.
        value: Signal value (z-score normalized typically).
        direction: Expected price direction (1=bullish, -1=bearish, 0=neutral).
        confidence: Signal confidence [0.0, 1.0].
        horizon: Expected signal horizon in days.
        components: Contributing sentiment sub-factors.
        metadata: Additional context.
    """

    signal_id: str
    symbol: str
    factor_name: str
    value: float = 0.0
    direction: int = 0
    confidence: float = 0.5
    horizon: int = 5
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.5 and self.direction != 0

    @property
    def absolute_strength(self) -> float:
        return abs(self.value) * self.confidence
