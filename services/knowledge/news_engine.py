"""
News Intelligence Engine.

Processes news articles for:
- Categorization
- Sentiment tagging
- Impact scoring
- Relevance filtering
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class NewsCategory(str, Enum):
    EARNINGS = "earnings"
    PRODUCT = "product"
    MANAGEMENT = "management"
    M_AND_A = "merger_acquisition"
    REGULATION = "regulation"
    MACRO = "macro"
    INDUSTRY = "industry"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    ESG = "esg"
    CORPORATE_ACTION = "corporate_action"
    MARKET_RUMOR = "market_rumor"
    ANALYST_VIEW = "analyst_view"
    OTHER = "other"


class NewsSentiment(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class NewsImpact(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class NewsArticle:
    """Processed news article with intelligence metadata."""

    article_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""

    title: str = ""
    content: str = ""
    url: str = ""
    source: str = ""

    published_at: Optional[datetime] = None
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Intelligence
    categories: List[NewsCategory] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    sentiment: NewsSentiment = NewsSentiment.NEUTRAL
    sentiment_score: float = 0.5
    impact: NewsImpact = NewsImpact.MEDIUM
    impact_score: float = 0.5

    # Entities
    symbols: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)

    # NLP output
    keywords: List[str] = field(default_factory=list)
    summary: str = ""
    topics: List[str] = field(default_factory=list)

    # Metrics
    relevance_score: float = 0.0
    confidence: float = 0.0
    is_breaking: bool = False

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_id": self.article_id,
            "document_id": self.document_id,
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "categories": [c.value for c in self.categories],
            "category_scores": self.category_scores,
            "sentiment": self.sentiment.value,
            "sentiment_score": self.sentiment_score,
            "impact": self.impact.value,
            "impact_score": self.impact_score,
            "symbols": self.symbols,
            "entities": self.entities,
            "keywords": self.keywords,
            "summary": self.summary,
            "confidence": self.confidence,
            "is_breaking": self.is_breaking,
        }


@dataclass
class NewsConfig:
    """Configuration for news engine."""

    # Sentiment thresholds
    very_positive_threshold: float = 0.8
    positive_threshold: float = 0.6
    negative_threshold: float = 0.4
    very_negative_threshold: float = 0.2

    # Impact scoring
    high_impact_threshold: float = 0.8
    medium_impact_threshold: float = 0.5

    # Breaking news detection
    breaking_time_window_hours: int = 2
    breaking_keywords: List[str] = field(default_factory=lambda: [
        "breaking", "urgent", "alert", "just in", "flash",
    ])

    # Relevance
    min_relevance_score: float = 0.1


# ── News Engine ──────────────────────────────────────────────────────────────

class NewsEngine:
    """
    News intelligence engine for processing and enriching news articles.

    Categorizes, scores sentiment, assesses impact, and extracts
    trading-relevant metadata from financial news.
    """

    # High-impact event keywords
    HIGH_IMPACT_KEYWORDS: Dict[str, List[str]] = {
        "earnings_surprise": [
            "beat", "miss", "surprise", "shock", "record", "unexpected",
        ],
        "merger": ["acquisition", "merger", "takeover", "bid", "offer"],
        "regulation": ["fine", "penalty", "investigation", "lawsuit", "sec"],
        "bankruptcy": ["bankruptcy", "chapter 11", "default", "insolvent"],
        "product": ["launch", "recall", "approval", "fda", "breakthrough"],
        "management": ["ceo", "resign", "appoint", "restructure", "layoff"],
        "macro": ["rate hike", "rate cut", "recession", "crisis"],
    }

    def __init__(self, config: Optional[NewsConfig] = None):
        self.config = config or NewsConfig()
        self._articles: List[NewsArticle] = []

    # ── Main Processing ──────────────────────────────────────────────────────

    def process(
        self,
        document_id: str,
        title: str,
        content: str,
        source: str = "",
        url: str = "",
        published_at: Optional[datetime] = None,
        symbols: Optional[List[str]] = None,
        **kwargs,
    ) -> NewsArticle:
        """
        Process a news article and enrich with intelligence metadata.

        Args:
            document_id: Ingested document ID.
            title: Article title.
            content: Article content.
            source: News source.
            url: Article URL.
            published_at: Publication time.
            symbols: Related stock symbols.

        Returns:
            NewsArticle with full intelligence enrichment.
        """
        text_lower = (title + " " + content).lower()

        article = NewsArticle(
            document_id=document_id,
            title=title,
            content=content,
            url=url,
            source=source,
            published_at=published_at,
            symbols=symbols or [],
        )

        # Categorize
        article.categories, article.category_scores = self._categorize(text_lower)

        # Sentiment
        article.sentiment, article.sentiment_score = self._score_sentiment(
            text_lower, title
        )

        # Impact
        article.impact, article.impact_score = self._assess_impact(text_lower)

        # Breaking news
        article.is_breaking = self._detect_breaking(title, published_at)

        # Extract entities
        article.entities = self._extract_entities(text_lower)

        # Compute confidence
        article.confidence = self._compute_confidence(article)

        self._articles.append(article)
        logger.debug(
            f"News processed: {article.title[:50]}... "
            f"sentiment={article.sentiment.value}, impact={article.impact.value}"
        )
        return article

    # ── Categorization ───────────────────────────────────────────────────────

    CATEGORY_KEYWORDS: Dict[NewsCategory, List[str]] = {
        NewsCategory.EARNINGS: [
            "earnings", "revenue", "profit", "eps", "quarterly", "guidance",
        ],
        NewsCategory.PRODUCT: [
            "launch", "new product", "release", "unveiled", "recall",
        ],
        NewsCategory.MANAGEMENT: [
            "ceo", "cfo", "executive", "appointed", "resigned", "board",
        ],
        NewsCategory.M_AND_A: [
            "acquisition", "merger", "takeover", "buyout", "deal",
        ],
        NewsCategory.REGULATION: [
            "regulation", "fine", "penalty", "lawsuit", "compliance", "sec",
        ],
        NewsCategory.MACRO: [
            "gdp", "inflation", "fed", "interest rate", "central bank",
        ],
        NewsCategory.INDUSTRY: [
            "sector", "industry", "competition", "market share",
        ],
        NewsCategory.GEOPOLITICAL: [
            "war", "sanction", "tariff", "trade war", "tension",
        ],
        NewsCategory.TECHNOLOGY: [
            "ai", "artificial intelligence", "chip", "semiconductor", "blockchain",
        ],
        NewsCategory.ESG: [
            "esg", "sustainability", "carbon", "green", "emission",
        ],
        NewsCategory.CORPORATE_ACTION: [
            "dividend", "buyback", "split", "ipo", "offering",
        ],
        NewsCategory.MARKET_RUMOR: [
            "rumor", "speculation", "reportedly", "sources say", "could",
        ],
        NewsCategory.ANALYST_VIEW: [
            "upgrade", "downgrade", "target price", "rating", "analyst",
        ],
    }

    def _categorize(
        self, text: str
    ) -> tuple[List[NewsCategory], Dict[str, float]]:
        scores: Dict[NewsCategory, float] = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            if matches > 0:
                scores[category] = min(matches / max(len(keywords), 1) * 3, 1.0)

        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected = [(c, s) for c, s in sorted_cats[:3] if s > 0.05]

        if not selected:
            return [NewsCategory.OTHER], {"other": 0.1}

        return [c for c, _ in selected], {c.value: s for c, s in selected}

    # ── Sentiment Scoring ────────────────────────────────────────────────────

    POSITIVE_PHRASES = [
        "beat expectations", "exceeded", "record high", "upgrade",
        "strong growth", "positive outlook", "bullish", "surge",
        "outperform", "raised guidance", "expansion", "breakthrough",
    ]
    NEGATIVE_PHRASES = [
        "missed expectations", "decline", "downgrade", "loss",
        "negative outlook", "bearish", "plunge", "underperform",
        "lowered guidance", "layoff", "bankruptcy", "investigation",
        "warning", "risk", "concern",
    ]

    def _score_sentiment(self, text: str, title: str) -> tuple[NewsSentiment, float]:
        # Count positive/negative phrase matches
        positive_count = sum(
            1 for phrase in self.POSITIVE_PHRASES if phrase in text
        )
        negative_count = sum(
            1 for phrase in self.NEGATIVE_PHRASES if phrase in text
        )

        # Title carries extra weight
        positive_count += sum(
            2 for phrase in self.POSITIVE_PHRASES if phrase in title.lower()
        )
        negative_count += sum(
            2 for phrase in self.NEGATIVE_PHRASES if phrase in title.lower()
        )

        total = positive_count + negative_count
        if total == 0:
            return NewsSentiment.NEUTRAL, 0.5

        raw_score = positive_count / total

        if raw_score >= self.config.very_positive_threshold:
            return NewsSentiment.VERY_POSITIVE, raw_score
        elif raw_score >= self.config.positive_threshold:
            return NewsSentiment.POSITIVE, raw_score
        elif raw_score <= self.config.very_negative_threshold:
            return NewsSentiment.VERY_NEGATIVE, raw_score
        elif raw_score <= self.config.negative_threshold:
            return NewsSentiment.NEGATIVE, raw_score
        else:
            return NewsSentiment.NEUTRAL, raw_score

    # ── Impact Assessment ────────────────────────────────────────────────────

    def _assess_impact(self, text: str) -> tuple[NewsImpact, float]:
        impact_scores: Dict[str, int] = {}

        for event_type, keywords in self.HIGH_IMPACT_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                impact_scores[event_type] = min(hits * 3, 10)

        if not impact_scores:
            return NewsImpact.LOW, 0.2

        max_score = max(impact_scores.values()) / 10.0

        if max_score >= self.config.high_impact_threshold:
            return NewsImpact.HIGH, max_score
        elif max_score >= self.config.medium_impact_threshold:
            return NewsImpact.MEDIUM, max_score
        else:
            return NewsImpact.LOW, max_score

    # ── Breaking News Detection ──────────────────────────────────────────────

    def _detect_breaking(
        self, title: str, published_at: Optional[datetime] = None
    ) -> bool:
        title_lower = title.lower()

        # Check for breaking keywords in title
        has_breaking_kw = any(
            kw in title_lower for kw in self.config.breaking_keywords
        )
        if has_breaking_kw:
            return True

        # Check recency
        if published_at:
            age = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
            if age <= self.config.breaking_time_window_hours:
                return True

        return False

    # ── Entity Extraction (lightweight) ──────────────────────────────────────

    def _extract_entities(self, text: str) -> List[str]:
        """Lightweight entity extraction for common financial entities."""
        entities = []

        # Simple ticker pattern detection
        ticker_pattern = re.findall(r"\$([A-Z]{1,5})\b", text)
        entities.extend(ticker_pattern)

        # Common company names (extensible)
        common_companies = [
            "apple", "microsoft", "google", "amazon", "nvidia", "tesla",
            "meta", "netflix", "intel", "amd", "broadcom", "qualcomm",
        ]
        for company in common_companies:
            if company in text.lower():
                entities.append(company.upper())

        return list(set(entities))

    # ── Confidence ───────────────────────────────────────────────────────────

    def _compute_confidence(self, article: NewsArticle) -> float:
        scores = [
            article.sentiment_score,
            article.impact_score,
            max(article.category_scores.values()) if article.category_scores else 0.1,
        ]
        return sum(scores) / len(scores)

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_articles(
        self,
        symbols: Optional[List[str]] = None,
        category: Optional[NewsCategory] = None,
        sentiment: Optional[NewsSentiment] = None,
        impact: Optional[NewsImpact] = None,
        is_breaking: Optional[bool] = None,
        limit: int = 100,
    ) -> List[NewsArticle]:
        """Query articles with filters."""
        results = self._articles

        if symbols:
            sym_set = set(symbols)
            results = [a for a in results if sym_set & set(a.symbols)]
        if category:
            results = [a for a in results if category in a.categories]
        if sentiment:
            results = [a for a in results if a.sentiment == sentiment]
        if impact:
            results = [a for a in results if a.impact == impact]
        if is_breaking is not None:
            results = [a for a in results if a.is_breaking == is_breaking]

        return results[-limit:]

    def get_breaking_news(self, limit: int = 10) -> List[NewsArticle]:
        """Get breaking news articles."""
        return self.get_articles(is_breaking=True, limit=limit)

    def get_high_impact(
        self, symbols: Optional[List[str]] = None, limit: int = 20
    ) -> List[NewsArticle]:
        """Get high-impact news."""
        return self.get_articles(
            symbols=symbols, impact=NewsImpact.HIGH, limit=limit
        )

    def clear(self) -> None:
        """Clear all articles."""
        self._articles.clear()

