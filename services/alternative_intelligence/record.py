"""Alternative Data Model — core data structures for alternative data intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class DataSource(str, Enum):
    """Alternative data source categories."""

    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    WEB_DATA = "web_data"
    SATELLITE = "satellite"
    SUPPLY_CHAIN = "supply_chain"
    HIRING = "hiring"
    APP_DATA = "app_data"
    CONSUMER = "consumer"
    GEOLOCATION = "geolocation"
    CREDIT_CARD = "credit_card"


class SentimentPolarity(str, Enum):
    """Sentiment polarity for alternative data analysis."""

    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class SignalStrength(str, Enum):
    """Alpha signal strength classification."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEUTRAL = "neutral"
    CONTRARIAN = "contrarian"


@dataclass
class AlternativeRecord:
    """Core alternative data record — the atomic unit ingested from any alternative source.

    Attributes:
        source: Source type (news, social, web, satellite, etc.)
        content: Raw content / payload
        timestamp: When the data was observed
        asset_tags: List of tickers / asset identifiers linked to this record
        metadata: Arbitrary source-specific metadata (e.g. author, region, coordinates)
        confidence: Source reliability score [0, 1]
    """

    source: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    asset_tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5

    @property
    def source_enum(self) -> DataSource | None:
        """Map string source to DataSource enum if recognized."""
        try:
            return DataSource(self.source.lower().replace(" ", "_"))
        except ValueError:
            return None


@dataclass
class NewsArticle:
    """Structured representation of a news article."""

    headline: str
    body: str
    source_name: str
    published_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    url: str = ""
    author: str = ""
    category: str = ""
    language: str = "en"
    asset_tags: list[str] = field(default_factory=list)


@dataclass
class SocialPost:
    """Structured representation of a social media post."""

    platform: str
    content: str
    author: str
    posted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    followers_count: int = 0
    engagement: dict[str, int] = field(default_factory=dict)  # likes, shares, comments
    asset_tags: list[str] = field(default_factory=list)


@dataclass
class WebMetric:
    """Structured representation of web intelligence data point."""

    metric_type: str  # traffic, search_trend, product_rank, hiring
    value: float
    change_pct: float = 0.0
    period: str = "daily"
    source_url: str = ""
    asset_tags: list[str] = field(default_factory=list)


@dataclass
class SatelliteObservation:
    """Structured representation of satellite-derived observation."""

    location: str
    observation_type: str  # factory_activity, port_traffic, energy_consumption, parking_lot
    activity_score: float  # [0, 100]
    change_pct: float = 0.0
    observed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    coordinates: tuple[float, float] | None = None
    asset_tags: list[str] = field(default_factory=list)


@dataclass
class AlternativeFeature:
    """Engineered feature derived from alternative data, ready for alpha discovery.

    Attributes:
        name: Feature name (e.g. "news_sentiment_7d", "social_volume_surge")
        value: Current feature value
        category: Feature category for grouping
        asset_tag: Associated ticker / asset
        z_score: Normalized z-score relative to history
        signal_strength: Classification of signal quality
        metadata: Additional context
    """

    name: str
    value: float
    category: str = "alternative"
    asset_tag: str = ""
    z_score: float = 0.0
    signal_strength: SignalStrength = SignalStrength.NEUTRAL
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlphaCandidate:
    """A candidate alpha signal generated from alternative data features.

    Attributes:
        feature: The feature that generated this alpha candidate
        alpha_score: The alpha score (excess return prediction) [-1, 1]
        confidence: Model confidence [0, 1]
        sharpe_estimate: Estimated Sharpe ratio
        information_coefficient: IC estimate
        decay_half_life: Signal decay half-life in days
        metadata: Additional context (e.g. correlation with existing factors)
    """

    feature: AlternativeFeature
    alpha_score: float = 0.0
    confidence: float = 0.5
    sharpe_estimate: float = 0.0
    information_coefficient: float = 0.0
    decay_half_life: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Whether this alpha candidate exceeds the minimum confidence threshold."""
        return self.confidence >= 0.6 and abs(self.alpha_score) >= 0.2


@dataclass
class FusionResult:
    """Result of fusing alternative data with price and macro data.

    Attributes:
        asset_tag: The asset this fusion applies to
        traditional_alpha: Alpha score from traditional (price) data
        macro_alpha: Alpha score from macro data
        alternative_alpha: Alpha score from alternative data
        fused_alpha: Weighted combined alpha score
        component_weights: Weights assigned to each component
        confidence: Overall fusion confidence
    """

    asset_tag: str
    traditional_alpha: float = 0.0
    macro_alpha: float = 0.0
    alternative_alpha: float = 0.0
    fused_alpha: float = 0.0
    component_weights: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.5


@dataclass
class MemoryEntry:
    """Single entry in the alternative intelligence memory."""

    record: AlternativeRecord
    analysis_result: dict[str, Any] = field(default_factory=dict)
    alpha_performance: float | None = None  # realized alpha
    stored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    retrieval_count: int = 0
    relevance_score: float = 0.5
