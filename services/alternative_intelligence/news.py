"""News Intelligence Engine — NLP analysis of financial news for alpha signals."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeFeature,
    AlternativeRecord,
    NewsArticle,
    SentimentPolarity,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# Sector / Topic keywords for classification
# ---------------------------------------------------------------------------

_SECTOR_KEYWORDS: dict[str, list[str]] = {
    "ai_semiconductor": [
        "ai chip", "gpu", "semiconductor", "nvidia", "amd", "tsmc",
        "artificial intelligence chip", "machine learning hardware",
        "h100", "b200", "inference chip", "training chip",
    ],
    "cloud_computing": [
        "cloud", "aws", "azure", "gcp", "saas", "iaas",
        "data center", "server", "hyperscaler",
    ],
    "fintech": [
        "fintech", "payment", "digital bank", "blockchain",
        "crypto", "defi", "lending", "insurtech",
    ],
    "biotech": [
        "biotech", "pharma", "fda", "clinical trial", "drug",
        "gene therapy", "mrna", "crispr",
    ],
    "energy": [
        "oil", "gas", "solar", "wind", "renewable", "energy",
        "ev battery", "nuclear", "carbon",
    ],
    "consumer": [
        "retail", "ecommerce", "consumer", "brand", "restaurant",
        "subscription", "delivery", "luxury",
    ],
    "real_estate": [
        "real estate", "property", "reit", "mortgage", "housing",
        "commercial real estate",
    ],
    "automotive": [
        "automotive", "ev", "electric vehicle", "tesla", "autonomous",
        "battery", "charging",
    ],
}


_IMPACT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "positive": {
        "strong": [
            "record revenue", "blowout earnings", "breakthrough",
            "blockbuster", "surge", "soar", "beat estimates by",
            "raise guidance significantly",
        ],
        "moderate": [
            "beat", "outperform", "growth", "expansion", "upgrade",
            "raise guidance", "positive outlook", "momentum",
        ],
    },
    "negative": {
        "strong": [
            "crash", "collapse", "bankruptcy", "fraud", "scandal",
            "plunge", "plummet", "miss estimates by wide margin",
            "cut guidance significantly",
        ],
        "moderate": [
            "miss", "decline", "downgrade", "cut guidance",
            "negative outlook", "headwind", "risk", "warning",
            "layoff", "restructuring",
        ],
    },
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class NewsAnalysis:
    """Result of news intelligence analysis."""

    headline: str = ""
    sentiment: SentimentPolarity = SentimentPolarity.NEUTRAL
    sentiment_score: float = 0.0  # [-1, 1] where +1 = very positive
    confidence: float = 0.5
    sectors: list[str] = field(default_factory=list)
    primary_sector: str = ""
    impact_magnitude: float = 0.0  # [0, 1]
    key_entities: list[str] = field(default_factory=list)
    summary: str = ""
    features: list[AlternativeFeature] = field(default_factory=list)

    @property
    def is_positive(self) -> bool:
        return self.sentiment in (SentimentPolarity.POSITIVE, SentimentPolarity.VERY_POSITIVE)

    @property
    def is_negative(self) -> bool:
        return self.sentiment in (SentimentPolarity.NEGATIVE, SentimentPolarity.VERY_NEGATIVE)

    @property
    def is_high_impact(self) -> bool:
        return self.impact_magnitude >= 0.6


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class NewsIntelligence:
    """Analyzes financial news to extract sentiment, sectors, entities, and alpha features.

    Capabilities:
    - Multi-sector classification (AI semiconductor, cloud, fintech, etc.)
    - Sentiment scoring with confidence estimation
    - Impact magnitude assessment
    - Entity extraction
    - Feature generation for alpha discovery
    """

    def __init__(self) -> None:
        self._history: list[NewsAnalysis] = []
        self._sector_cache: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, news: str | NewsArticle | AlternativeRecord) -> NewsAnalysis:
        """Analyze news content and return structured intelligence.

        Accepts raw text, a NewsArticle, or an AlternativeRecord.
        """
        if isinstance(news, NewsArticle):
            content = f"{news.headline} {news.body}"
            headline = news.headline
            tags = news.asset_tags
        elif isinstance(news, AlternativeRecord):
            content = news.content
            headline = news.metadata.get("headline", content[:80])
            tags = news.asset_tags
        else:
            content = news
            headline = content[:80]
            tags = []

        # Sector classification
        sectors = self._classify_sectors(content)
        primary = sectors[0] if sectors else "general"

        # Sentiment analysis
        sentiment, sentiment_score, confidence = self._analyze_sentiment(content)

        # Impact magnitude
        impact = self._assess_impact(content, sentiment_score)

        # Entity extraction
        entities = self._extract_entities(content, tags)

        # Feature generation
        features = self._generate_features(
            content, sentiment_score, sectors, primary, impact, entities
        )

        result = NewsAnalysis(
            headline=headline,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            confidence=confidence,
            sectors=sectors,
            primary_sector=primary,
            impact_magnitude=impact,
            key_entities=entities,
            summary=content[:200],
            features=features,
        )
        self._history.append(result)

        # Cache sector → entities
        for s in sectors:
            for e in entities:
                if e not in self._sector_cache[s]:
                    self._sector_cache[s].append(e)

        return result

    def analyze_batch(
        self, articles: list[str | NewsArticle | AlternativeRecord]
    ) -> list[NewsAnalysis]:
        """Analyze a batch of news articles."""
        return [self.analyze(a) for a in articles]

    def get_sector_sentiment(self, sector: str) -> dict:
        """Get aggregated sentiment for a sector based on history."""
        relevant = [a for a in self._history if sector in a.sectors]
        if not relevant:
            return {"sector": sector, "count": 0, "avg_sentiment": 0.0}

        avg = sum(a.sentiment_score for a in relevant) / len(relevant)
        return {
            "sector": sector,
            "count": len(relevant),
            "avg_sentiment": round(avg, 3),
            "positive_ratio": sum(1 for a in relevant if a.is_positive) / len(relevant),
            "negative_ratio": sum(1 for a in relevant if a.is_negative) / len(relevant),
            "entities": self._sector_cache.get(sector, []),
        }

    def get_entity_sentiment(self, entity: str) -> dict:
        """Get aggregated sentiment for a specific entity."""
        relevant = [a for a in self._history if entity in a.key_entities]
        if not relevant:
            return {"entity": entity, "count": 0, "avg_sentiment": 0.0}

        avg = sum(a.sentiment_score for a in relevant) / len(relevant)
        return {
            "entity": entity,
            "count": len(relevant),
            "avg_sentiment": round(avg, 3),
            "positive_ratio": sum(1 for a in relevant if a.is_positive) / len(relevant),
        }

    @property
    def history(self) -> list[NewsAnalysis]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
        self._sector_cache.clear()

    # ------------------------------------------------------------------
    # Internal: Classification
    # ------------------------------------------------------------------

    def _classify_sectors(self, text: str) -> list[str]:
        """Classify text into one or more sectors using keyword matching."""
        text_lower = text.lower()
        matched: list[tuple[str, int]] = []

        for sector, keywords in _SECTOR_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                matched.append((sector, score))

        # Sort by match count descending
        matched.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in matched]

    # ------------------------------------------------------------------
    # Internal: Sentiment Analysis
    # ------------------------------------------------------------------

    def _analyze_sentiment(self, text: str) -> tuple[SentimentPolarity, float, float]:
        """Analyze sentiment using keyword scoring with confidence estimation."""
        text_lower = text.lower()

        positive_score = 0
        negative_score = 0
        strong_matches = 0
        total_matches = 0

        # Count positive keyword matches
        for strength, keywords in _IMPACT_KEYWORDS["positive"].items():
            weight = 2.0 if strength == "strong" else 1.0
            for kw in keywords:
                if kw in text_lower:
                    positive_score += weight
                    total_matches += 1
                    if strength == "strong":
                        strong_matches += 1

        # Count negative keyword matches
        for strength, keywords in _IMPACT_KEYWORDS["negative"].items():
            weight = 2.0 if strength == "strong" else 1.0
            for kw in keywords:
                if kw in text_lower:
                    negative_score += weight
                    total_matches += 1
                    if strength == "strong":
                        strong_matches += 1

        if total_matches == 0:
            return SentimentPolarity.NEUTRAL, 0.0, 0.3

        # Compute net sentiment score
        net = positive_score - negative_score
        max_possible = max(positive_score + negative_score, 1)
        normalized = max(-1.0, min(1.0, net / max_possible))

        # Confidence: more matches + more strong matches → higher confidence
        confidence = min(0.95, 0.4 + 0.15 * total_matches + 0.1 * strong_matches)

        # Map to polarity
        if normalized >= 0.6:
            polarity = SentimentPolarity.VERY_POSITIVE
        elif normalized > 0.1:
            polarity = SentimentPolarity.POSITIVE
        elif normalized <= -0.6:
            polarity = SentimentPolarity.VERY_NEGATIVE
        elif normalized < -0.1:
            polarity = SentimentPolarity.NEGATIVE
        else:
            polarity = SentimentPolarity.NEUTRAL

        return polarity, normalized, confidence

    # ------------------------------------------------------------------
    # Internal: Impact Assessment
    # ------------------------------------------------------------------

    def _assess_impact(self, text: str, sentiment_score: float) -> float:
        """Assess the impact magnitude of the news."""
        text_lower = text.lower()

        # High-impact indicators
        high_impact_terms = [
            "record", "historic", "unprecedented", "breakthrough",
            "crash", "collapse", "bankruptcy", "acquisition", "merger",
            "ipo", "regulation", "ban", "lawsuit", "settlement",
            "ceo", "fda approval", "clinical trial results",
        ]
        high_count = sum(1 for t in high_impact_terms if t in text_lower)

        # Base impact from sentiment strength
        base = abs(sentiment_score) * 0.5

        # Boost from high-impact terms
        boost = min(0.5, high_count * 0.12)

        return min(1.0, base + boost)

    # ------------------------------------------------------------------
    # Internal: Entity Extraction
    # ------------------------------------------------------------------

    def _extract_entities(
        self, text: str, known_tags: list[str]
    ) -> list[str]:
        """Extract key entities (companies, products, people) from text."""
        entities: list[str] = []

        # Known ticker patterns (simplified)
        ticker_pattern = re.compile(r'\b\$?([A-Z]{1,5})\b')
        matches = ticker_pattern.findall(text)
        # Filter out common non-ticker all-caps words
        stop_words = {
            "THE", "A", "AN", "IS", "IT", "BE", "TO", "OF", "IN", "ON",
            "AT", "BY", "OR", "WE", "HE", "US", "AI", "CEO", "FDA", "IPO",
            "GDP", "CPI", "PMI", "FOMC", "ECB", "ETF", "API",
        }
        for m in matches:
            if m not in stop_words and 2 <= len(m) <= 5:
                entities.append(m)

        # Add known asset tags
        for tag in known_tags:
            if tag not in entities:
                entities.append(tag)

        return list(dict.fromkeys(entities))  # deduplicate preserving order

    # ------------------------------------------------------------------
    # Internal: Feature Generation
    # ------------------------------------------------------------------

    def _generate_features(
        self,
        text: str,
        sentiment_score: float,
        sectors: list[str],
        primary_sector: str,
        impact: float,
        entities: list[str],
    ) -> list[AlternativeFeature]:
        """Generate alpha features from news analysis."""
        features: list[AlternativeFeature] = []

        # Feature 1: News sentiment
        for entity in entities:
            features.append(
                AlternativeFeature(
                    name=f"news_sentiment_{entity}",
                    value=sentiment_score,
                    category="news",
                    asset_tag=entity,
                    z_score=sentiment_score * 2.0,
                    signal_strength=(
                        SignalStrength.STRONG
                        if abs(sentiment_score) > 0.6
                        else SignalStrength.MODERATE
                        if abs(sentiment_score) > 0.2
                        else SignalStrength.WEAK
                    ),
                )
            )

        # Feature 2: News impact
        for entity in entities:
            features.append(
                AlternativeFeature(
                    name=f"news_impact_{entity}",
                    value=impact,
                    category="news",
                    asset_tag=entity,
                    z_score=impact * 1.5,
                    signal_strength=(
                        SignalStrength.STRONG
                        if impact > 0.6
                        else SignalStrength.MODERATE
                    ),
                )
            )

        # Feature 3: Sector momentum (composite)
        if sectors:
            features.append(
                AlternativeFeature(
                    name=f"sector_news_momentum_{primary_sector}",
                    value=sentiment_score * impact,
                    category="news_sector",
                    asset_tag="",
                    z_score=sentiment_score * impact * 2.0,
                    signal_strength=SignalStrength.MODERATE,
                )
            )

        return features
