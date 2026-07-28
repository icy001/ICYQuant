"""Social Sentiment Engine — analyzes investor sentiment from social media and community discussions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeFeature,
    AlternativeRecord,
    SentimentPolarity,
    SignalStrength,
    SocialPost,
)


# ---------------------------------------------------------------------------
# Sentiment keyword dictionaries
# ---------------------------------------------------------------------------

_BULLISH_KEYWORDS: dict[str, float] = {
    # Extreme bullish
    "to the moon": 0.95,
    "diamond hands": 0.9,
    "rocket ship": 0.9,
    "yolo": 0.85,
    "all in": 0.9,
    # Strong bullish
    "bullish": 0.8,
    "buy": 0.7,
    "long": 0.65,
    "undervalued": 0.7,
    "breakout": 0.75,
    "momentum": 0.65,
    "accumulation": 0.6,
    "green": 0.55,
    "upgrade": 0.7,
    "beat": 0.65,
    "surge": 0.7,
    "rally": 0.7,
    # Moderate bullish
    "growth": 0.55,
    "opportunity": 0.55,
    "catalyst": 0.6,
    "positive": 0.6,
    "outperform": 0.65,
    "strong": 0.5,
    "gain": 0.55,
}

_BEARISH_KEYWORDS: dict[str, float] = {
    # Extreme bearish
    "going to zero": 0.95,
    "rug pull": 0.9,
    "ponzi": 0.95,
    "scam": 0.85,
    # Strong bearish
    "bearish": 0.8,
    "sell": 0.7,
    "short": 0.75,
    "overvalued": 0.7,
    "crash": 0.85,
    "dump": 0.75,
    "downgrade": 0.7,
    "red": 0.55,
    "collapse": 0.85,
    "plunge": 0.8,
    "plummet": 0.8,
    # Moderate bearish
    "decline": 0.6,
    "risk": 0.55,
    "headwind": 0.6,
    "negative": 0.6,
    "underperform": 0.65,
    "weak": 0.5,
    "loss": 0.55,
    "warning": 0.6,
}

_VOLUME_SURGE_KEYWORDS: list[str] = [
    "everyone talking about", "trending", "viral", "exploding",
    "hottest", "breaking", "all over", "can't stop",
    "everywhere", "going crazy", "blowing up",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SentimentResult:
    """Result of social sentiment analysis."""

    platform: str = ""
    sentiment_score: float = 0.0  # [-1, 1] where +1 = extreme bullish
    polarity: SentimentPolarity = SentimentPolarity.NEUTRAL
    confidence: float = 0.5
    volume_signal: bool = False  # True if discussion volume is surging
    buzz_score: float = 0.0  # [0, 1] relative discussion intensity
    top_topics: list[str] = field(default_factory=list)
    features: list[AlternativeFeature] = field(default_factory=list)

    @property
    def is_bullish(self) -> bool:
        return self.sentiment_score > 0.15

    @property
    def is_bearish(self) -> bool:
        return self.sentiment_score < -0.15

    @property
    def is_extreme(self) -> bool:
        return abs(self.sentiment_score) > 0.7


@dataclass
class AssetSentiment:
    """Aggregated sentiment for a specific asset across platforms."""

    asset_tag: str
    overall_score: float = 0.0
    polarity: SentimentPolarity = SentimentPolarity.NEUTRAL
    post_count: int = 0
    platform_breakdown: dict[str, dict] = field(default_factory=dict)
    buzz_score: float = 0.0
    volume_surge: bool = False
    top_topics: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SocialSentimentEngine:
    """Analyzes social media and community discussions for investor sentiment signals.

    Capabilities:
    - Multi-platform sentiment scoring
    - Buzz/volume surge detection
    - Asset-level sentiment aggregation
    - Topic extraction
    - Contrarian signal detection (extreme sentiment → reversal)
    """

    def __init__(self) -> None:
        self._results: list[SentimentResult] = []
        self._asset_sentiment: dict[str, list[SentimentResult]] = defaultdict(list)
        self._topic_tracker: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, text: str | SocialPost | AlternativeRecord) -> SentimentResult:
        """Analyze a social media post / discussion text for sentiment."""
        if isinstance(text, SocialPost):
            content = text.content
            platform = text.platform
            tags = text.asset_tags
            engagement = text.engagement
        elif isinstance(text, AlternativeRecord):
            content = text.content
            platform = text.metadata.get("platform", "unknown")
            tags = text.asset_tags
            engagement = text.metadata.get("engagement", {})
        else:
            content = text
            platform = "unknown"
            tags = []
            engagement = {}

        # Sentiment scoring
        score = self._score_sentiment(content)
        polarity = self._score_to_polarity(score)

        # Volume / buzz detection
        volume_signal = self._detect_volume_surge(content)
        buzz = self._compute_buzz(content, engagement)

        # Topic extraction
        topics = self._extract_topics(content, tags)

        # Confidence estimation
        confidence = self._estimate_confidence(content, score, engagement)

        # Feature generation
        features = self._generate_features(
            tags, score, volume_signal, buzz, confidence
        )

        result = SentimentResult(
            platform=platform,
            sentiment_score=score,
            polarity=polarity,
            confidence=confidence,
            volume_signal=volume_signal,
            buzz_score=buzz,
            top_topics=topics,
            features=features,
        )
        self._results.append(result)

        # Track per asset
        for tag in tags:
            self._asset_sentiment[tag].append(result)

        # Track topics
        for t in topics:
            self._topic_tracker[t] += 1

        return result

    def analyze_batch(
        self, posts: list[str | SocialPost | AlternativeRecord]
    ) -> list[SentimentResult]:
        """Analyze a batch of social media posts."""
        return [self.analyze(p) for p in posts]

    def get_asset_sentiment(self, asset_tag: str) -> AssetSentiment:
        """Get aggregated sentiment for a specific asset across all platforms."""
        results = self._asset_sentiment.get(asset_tag, [])
        if not results:
            return AssetSentiment(asset_tag=asset_tag)

        scores = [r.sentiment_score for r in results]
        avg_score = sum(scores) / len(scores)

        # Platform breakdown
        platform_data: dict[str, dict] = defaultdict(lambda: {"count": 0, "scores": []})
        for r in results:
            platform_data[r.platform]["count"] += 1
            platform_data[r.platform]["scores"].append(r.sentiment_score)

        platform_breakdown = {}
        for plat, data in platform_data.items():
            platform_breakdown[plat] = {
                "count": data["count"],
                "avg_sentiment": sum(data["scores"]) / len(data["scores"]),
            }

        # Aggregate buzz
        avg_buzz = sum(r.buzz_score for r in results) / len(results)
        any_surge = any(r.volume_signal for r in results)

        # Aggregate topics
        all_topics: dict[str, int] = defaultdict(int)
        for r in results:
            for t in r.top_topics:
                all_topics[t] += 1
        top_topics = sorted(all_topics, key=all_topics.get, reverse=True)[:10]

        return AssetSentiment(
            asset_tag=asset_tag,
            overall_score=round(avg_score, 3),
            polarity=self._score_to_polarity(avg_score),
            post_count=len(results),
            platform_breakdown=platform_breakdown,
            buzz_score=round(avg_buzz, 3),
            volume_surge=any_surge,
            top_topics=top_topics,
        )

    def get_trending_topics(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the most discussed topics."""
        return sorted(self._topic_tracker.items(), key=lambda x: x[1], reverse=True)[:limit]

    def detect_contrarian_signal(self, asset_tag: str) -> dict:
        """Detect contrarian signal: extreme bullish → potential top, extreme bearish → potential bottom."""
        results = self._asset_sentiment.get(asset_tag, [])
        if not results:
            return {"asset": asset_tag, "signal": None}

        avg = sum(r.sentiment_score for r in results) / len(results)
        extreme_count = sum(1 for r in results if r.is_extreme)

        if avg > 0.7 and extreme_count > len(results) * 0.5:
            return {
                "asset": asset_tag,
                "signal": "CONTRARIAN_BEARISH",
                "reason": "Extreme bullish consensus — potential reversal risk",
                "sentiment": round(avg, 3),
                "extreme_ratio": extreme_count / len(results),
            }
        elif avg < -0.7 and extreme_count > len(results) * 0.5:
            return {
                "asset": asset_tag,
                "signal": "CONTRARIAN_BULLISH",
                "reason": "Extreme bearish consensus — potential mean reversion",
                "sentiment": round(avg, 3),
                "extreme_ratio": extreme_count / len(results),
            }
        else:
            return {"asset": asset_tag, "signal": "NO_CONTRARIAN", "sentiment": round(avg, 3)}

    @property
    def history(self) -> list[SentimentResult]:
        return list(self._results)

    def clear(self) -> None:
        self._results.clear()
        self._asset_sentiment.clear()
        self._topic_tracker.clear()

    # ------------------------------------------------------------------
    # Internal: Sentiment Scoring
    # ------------------------------------------------------------------

    def _score_sentiment(self, text: str) -> float:
        """Score sentiment on [-1, 1] scale using keyword matching."""
        text_lower = text.lower()
        bullish_score = 0.0
        bearish_score = 0.0
        bullish_count = 0
        bearish_count = 0

        for kw, weight in _BULLISH_KEYWORDS.items():
            if kw in text_lower:
                bullish_score += weight
                bullish_count += 1

        for kw, weight in _BEARISH_KEYWORDS.items():
            if kw in text_lower:
                bearish_score += weight
                bearish_count += 1

        total = bullish_count + bearish_count
        if total == 0:
            return 0.0

        net = bullish_score - bearish_score
        # Normalize: max possible per side is ~2.0
        return max(-1.0, min(1.0, net / max(total, 2.0)))

    def _score_to_polarity(self, score: float) -> SentimentPolarity:
        """Map numeric score to sentiment polarity."""
        if score >= 0.6:
            return SentimentPolarity.VERY_POSITIVE
        elif score > 0.15:
            return SentimentPolarity.POSITIVE
        elif score <= -0.6:
            return SentimentPolarity.VERY_NEGATIVE
        elif score < -0.15:
            return SentimentPolarity.NEGATIVE
        return SentimentPolarity.NEUTRAL

    # ------------------------------------------------------------------
    # Internal: Volume & Buzz
    # ------------------------------------------------------------------

    def _detect_volume_surge(self, text: str) -> bool:
        """Detect if the post indicates a discussion volume surge."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in _VOLUME_SURGE_KEYWORDS)

    def _compute_buzz(self, text: str, engagement: dict[str, int]) -> float:
        """Compute buzz score based on engagement metrics and content intensity."""
        text_lower = text.lower()

        # Engagement component
        engagement_score = 0.0
        total_engagement = sum(engagement.values())
        if total_engagement > 0:
            engagement_score = min(1.0, total_engagement / 10000.0)

        # Content intensity component
        intensity_keywords = [
            "!!!", "urgent", "breaking", "alert", "huge", "massive",
            "biggest", "important", "critical",
        ]
        intensity_count = sum(1 for kw in intensity_keywords if kw in text_lower)
        intensity_score = min(1.0, intensity_count * 0.2)

        # Caps ratio
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        caps_score = min(1.0, caps_ratio * 3.0)

        return (engagement_score * 0.3 + intensity_score * 0.4 + caps_score * 0.3)

    # ------------------------------------------------------------------
    # Internal: Topic Extraction
    # ------------------------------------------------------------------

    def _extract_topics(self, text: str, tags: list[str]) -> list[str]:
        """Extract discussion topics from text."""
        topics: list[str] = []

        topic_indicators: dict[str, list[str]] = {
            "ai": ["ai", "artificial intelligence", "machine learning", "llm", "gpt"],
            "crypto": ["crypto", "bitcoin", "ethereum", "defi", "nft", "blockchain"],
            "earnings": ["earnings", "revenue", "profit", "quarterly", "guidance"],
            "fed": ["fed", "fomc", "rate hike", "rate cut", "powell", "federal reserve"],
            "inflation": ["inflation", "cpi", "ppi", "price increase", "cost push"],
            "recession": ["recession", "downturn", "layoff", "economic slowdown"],
            "tech": ["tech", "technology", "software", "cloud", "saas"],
            "energy": ["energy", "oil", "gas", "solar", "green energy"],
        }

        text_lower = text.lower()
        for topic, indicators in topic_indicators.items():
            if any(ind in text_lower for ind in indicators):
                topics.append(topic)

        topics.extend(tags)
        return list(dict.fromkeys(topics))

    # ------------------------------------------------------------------
    # Internal: Confidence & Features
    # ------------------------------------------------------------------

    def _estimate_confidence(
        self, text: str, score: float, engagement: dict[str, int]
    ) -> float:
        """Estimate confidence in the sentiment score."""
        # Longer text → more signal
        text_len_factor = min(0.3, len(text.split()) / 100.0)

        # Stronger sentiment → more confidence
        sentiment_strength = abs(score)

        # Higher engagement → more signal
        total_eng = sum(engagement.values())
        engagement_factor = min(0.2, total_eng / 5000.0)

        base = 0.4
        return min(0.95, base + text_len_factor + sentiment_strength * 0.2 + engagement_factor)

    def _generate_features(
        self,
        tags: list[str],
        score: float,
        volume_signal: bool,
        buzz: float,
        confidence: float,
    ) -> list[AlternativeFeature]:
        """Generate alpha features from sentiment analysis."""
        features: list[AlternativeFeature] = []

        for tag in tags:
            # Feature 1: Social sentiment
            features.append(
                AlternativeFeature(
                    name=f"social_sentiment_{tag}",
                    value=score,
                    category="social",
                    asset_tag=tag,
                    z_score=score * 2.0,
                    signal_strength=(
                        SignalStrength.STRONG
                        if abs(score) > 0.6 and confidence > 0.6
                        else SignalStrength.MODERATE
                        if abs(score) > 0.2
                        else SignalStrength.WEAK
                    ),
                )
            )

            # Feature 2: Buzz / volume
            if volume_signal:
                features.append(
                    AlternativeFeature(
                        name=f"social_buzz_{tag}",
                        value=buzz,
                        category="social",
                        asset_tag=tag,
                        z_score=buzz * 2.5,
                        signal_strength=SignalStrength.STRONG if buzz > 0.5 else SignalStrength.MODERATE,
                    )
                )

        return features
