from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NewsCategory(str, Enum):
    MACRO = "MACRO"
    EARNINGS = "EARNINGS"
    M_AND_A = "M_AND_A"
    REGULATORY = "REGULATORY"
    GEOPOLITICAL = "GEOPOLITICAL"
    INDUSTRY = "INDUSTRY"
    CORPORATE = "CORPORATE"
    MARKET = "MARKET"


class NewsSentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


@dataclass
class NewsArticle:
    article_id: str
    title: str
    source: str
    category: NewsCategory
    sentiment: NewsSentiment
    relevance_score: float  # 0-1
    impact_score: float  # 0-100
    symbols: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class NewsDigest:
    articles: List[NewsArticle]
    dominant_sentiment: NewsSentiment
    overall_impact_score: float
    top_themes: List[str]
    actionable_items: List[str]


class NewsIntelligenceEngine:
    """News Intelligence Engine - processes and analyzes market news."""

    def __init__(self):
        self.processed_articles: List[NewsArticle] = []
        self.theme_keywords = {
            "inflation": ["inflation", "CPI", "PPI", "price increase"],
            "recession": ["recession", "downturn", "contraction"],
            "ai": ["artificial intelligence", "AI", "machine learning", "LLM"],
            "rate_hike": ["rate hike", "tightening", "hawkish"],
            "rate_cut": ["rate cut", "easing", "dovish"],
            "earnings": ["earnings", "revenue", "profit", "guidance"],
            "geopolitical": ["war", "conflict", "sanctions", "tension"],
            "regulation": ["regulation", "compliance", "SEC", "ban"],
        }

    def analyze(self, news):
        """Analyze a news article or digest.

        Args:
            news: News data - can be NewsArticle dataclass or dict/symbol.

        Returns:
            Dict containing news analysis result.
        """
        if isinstance(news, NewsArticle):
            return self._analyze_article(news)
        if isinstance(news, NewsDigest):
            return self._analyze_digest(news)
        return {"news": news}

    def _analyze_article(self, article: NewsArticle) -> dict:
        self.processed_articles.append(article)
        themes = self._extract_themes(article)

        return {
            "news": {
                "article_id": article.article_id,
                "title": article.title,
                "source": article.source,
                "category": article.category.value,
                "sentiment": article.sentiment.value,
                "relevance_score": article.relevance_score,
                "impact_score": article.impact_score,
                "symbols": article.symbols,
                "themes": themes,
                "actionable": article.impact_score > 50,
            }
        }

    def _analyze_digest(self, digest: NewsDigest) -> dict:
        return {
            "news": {
                "article_count": len(digest.articles),
                "dominant_sentiment": digest.dominant_sentiment.value,
                "overall_impact_score": digest.overall_impact_score,
                "top_themes": digest.top_themes,
                "actionable_items": digest.actionable_items,
            }
        }

    def _extract_themes(self, article: NewsArticle) -> List[str]:
        themes = []
        title_lower = article.title.lower()
        for theme, keywords in self.theme_keywords.items():
            if any(kw.lower() in title_lower for kw in keywords):
                themes.append(theme)
        return themes if themes else ["general"]

    def aggregate_sentiment(self, articles: List[NewsArticle]) -> NewsSentiment:
        """Aggregate sentiment across multiple articles."""
        if not articles:
            return NewsSentiment.NEUTRAL

        sentiment_scores = {
            NewsSentiment.POSITIVE: 1,
            NewsSentiment.NEUTRAL: 0,
            NewsSentiment.MIXED: 0,
            NewsSentiment.NEGATIVE: -1,
        }

        weighted_score = sum(
            sentiment_scores[a.sentiment] * a.relevance_score * a.impact_score
            for a in articles
        ) / max(sum(a.relevance_score * a.impact_score for a in articles), 1)

        if weighted_score > 0.3:
            return NewsSentiment.POSITIVE
        elif weighted_score < -0.3:
            return NewsSentiment.NEGATIVE
        return NewsSentiment.NEUTRAL
