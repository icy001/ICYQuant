"""Alternative Intelligence Service — orchestrates all alternative data intelligence modules."""

from __future__ import annotations

from dataclasses import dataclass, field

from .alpha import AlternativeAlphaDiscovery, AlphaDiscoveryResult
from .collector import AlternativeDataCollector
from .fusion import AlternativeDataFusion, FusionReport
from .memory import AlternativeMemory
from .news import NewsAnalysis, NewsIntelligence
from .record import (
    AlternativeFeature,
    AlternativeRecord,
    NewsArticle,
    SatelliteObservation,
    SocialPost,
    WebMetric,
)
from .satellite import SatelliteIntelligenceEngine, SatelliteResult
from .sentiment import AssetSentiment, SentimentResult, SocialSentimentEngine
from .web import AssetWebProfile, WebIntelligenceEngine, WebIntelligenceResult


# ---------------------------------------------------------------------------
# Service-level result
# ---------------------------------------------------------------------------


@dataclass
class AlternativeIntelligenceReport:
    """Complete report from the Alternative Intelligence Service.

    Aggregates results from all sub-engines into a single structured output.
    """

    # News intelligence
    news_analyses: list[NewsAnalysis] = field(default_factory=list)
    news_sector_sentiment: dict = field(default_factory=dict)

    # Social sentiment
    sentiment_results: list[SentimentResult] = field(default_factory=list)
    asset_sentiments: dict[str, AssetSentiment] = field(default_factory=dict)
    trending_topics: list[tuple[str, int]] = field(default_factory=list)

    # Web intelligence
    web_results: list[WebIntelligenceResult] = field(default_factory=list)
    web_profiles: dict[str, AssetWebProfile] = field(default_factory=dict)

    # Satellite intelligence
    satellite_results: list[SatelliteResult] = field(default_factory=list)

    # Alpha discovery
    alpha_discovery: AlphaDiscoveryResult | None = None

    # Data fusion
    fusion_report: FusionReport | None = None

    # Summary
    summary: str = ""
    actionable_signals: int = 0

    @property
    def has_alpha_signals(self) -> bool:
        return (
            self.alpha_discovery is not None
            and self.alpha_discovery.has_actionable
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AlternativeIntelligenceService:
    """Orchestrates all alternative data intelligence engines.

    Provides a unified interface for:
    - News intelligence analysis
    - Social sentiment analysis
    - Web intelligence analysis
    - Satellite intelligence analysis
    - Alpha discovery from alternative features
    - Multi-source data fusion
    - Memory storage and retrieval

    Usage:
        service = AlternativeIntelligenceService()
        report = service.analyze(news_articles=[...], social_posts=[...], ...)
    """

    def __init__(
        self,
        news_engine: NewsIntelligence | None = None,
        sentiment_engine: SocialSentimentEngine | None = None,
        web_engine: WebIntelligenceEngine | None = None,
        satellite_engine: SatelliteIntelligenceEngine | None = None,
        alpha_discovery: AlternativeAlphaDiscovery | None = None,
        fusion_engine: AlternativeDataFusion | None = None,
        memory: AlternativeMemory | None = None,
    ) -> None:
        self.news_engine = news_engine or NewsIntelligence()
        self.sentiment_engine = sentiment_engine or SocialSentimentEngine()
        self.web_engine = web_engine or WebIntelligenceEngine()
        self.satellite_engine = satellite_engine or SatelliteIntelligenceEngine()
        self.alpha_discovery = alpha_discovery or AlternativeAlphaDiscovery()
        self.fusion_engine = fusion_engine or AlternativeDataFusion()
        self.memory = memory or AlternativeMemory()
        self.collector = AlternativeDataCollector()

    # ------------------------------------------------------------------
    # Public API: analyze() — single news item
    # ------------------------------------------------------------------

    def analyze(self, news: str | NewsArticle | AlternativeRecord) -> NewsAnalysis:
        """Analyze a single news item (backward compatible with spec).

        Returns the news sentiment analysis result.
        """
        return self.news_engine.analyze(news)

    # ------------------------------------------------------------------
    # Public API: analyze_full() — comprehensive analysis
    # ------------------------------------------------------------------

    def analyze_full(
        self,
        *,
        news_articles: list[str | NewsArticle | AlternativeRecord] | None = None,
        social_posts: list[str | SocialPost | AlternativeRecord] | None = None,
        web_metrics: list[WebMetric | AlternativeRecord | dict] | None = None,
        satellite_observations: list[SatelliteObservation | AlternativeRecord | dict] | None = None,
        traditional_alphas: dict[str, float] | None = None,
        macro_alphas: dict[str, float] | None = None,
        regime: str = "normal",
        store_in_memory: bool = True,
    ) -> AlternativeIntelligenceReport:
        """Run comprehensive alternative intelligence analysis across all sources.

        Args:
            news_articles: News articles to analyze.
            social_posts: Social media posts to analyze.
            web_metrics: Web metrics to analyze.
            satellite_observations: Satellite observations to analyze.
            traditional_alphas: Price-based alpha scores per asset.
            macro_alphas: Macro alpha scores per asset.
            regime: Market regime for fusion weight selection.
            store_in_memory: Whether to persist results in memory.

        Returns:
            AlternativeIntelligenceReport with all results aggregated.
        """
        all_features: list[AlternativeFeature] = []

        # --- News Analysis ---
        news_analyses: list[NewsAnalysis] = []
        if news_articles:
            news_analyses = self.news_engine.analyze_batch(news_articles)
            for na in news_analyses:
                all_features.extend(na.features)
                if store_in_memory:
                    for tag in na.key_entities:
                        record = AlternativeRecord(
                            source="news",
                            content=na.summary,
                            asset_tags=[tag],
                            metadata={"sentiment": na.sentiment.value},
                            confidence=na.confidence,
                        )
                        self.collector.ingest_raw(
                            source="news", content=na.summary, asset_tags=[tag]
                        )
                        self.memory.save_analysis(
                            record=record,
                            analysis_result={
                                "sentiment": na.sentiment.value,
                                "score": na.sentiment_score,
                                "sectors": na.sectors,
                            },
                        )

        # Sector-level news sentiment
        news_sector_sentiment: dict = {}
        if news_analyses:
            all_sectors: set[str] = set()
            for na in news_analyses:
                all_sectors.update(na.sectors)
            for sector in all_sectors:
                news_sector_sentiment[sector] = self.news_engine.get_sector_sentiment(sector)

        # --- Social Sentiment ---
        sentiment_results: list[SentimentResult] = []
        asset_sentiments: dict[str, AssetSentiment] = {}
        if social_posts:
            sentiment_results = self.sentiment_engine.analyze_batch(social_posts)
            for sr in sentiment_results:
                all_features.extend(sr.features)

            # Aggregate per asset
            all_tags: set[str] = set()
            for sr in sentiment_results:
                for f in sr.features:
                    if f.asset_tag:
                        all_tags.add(f.asset_tag)
            for tag in all_tags:
                asset_sentiments[tag] = self.sentiment_engine.get_asset_sentiment(tag)

        # Trending topics
        trending_topics = self.sentiment_engine.get_trending_topics()

        # --- Web Intelligence ---
        web_results: list[WebIntelligenceResult] = []
        web_profiles: dict[str, AssetWebProfile] = {}
        if web_metrics:
            web_results = self.web_engine.analyze_batch(web_metrics)
            for wr in web_results:
                all_features.extend(wr.features)

            # Aggregate per asset
            web_assets: set[str] = set()
            for wr in web_results:
                for f in wr.features:
                    if f.asset_tag:
                        web_assets.add(f.asset_tag)
            for tag in web_assets:
                web_profiles[tag] = self.web_engine.get_asset_profile(tag)

        # --- Satellite Intelligence ---
        satellite_results: list[SatelliteResult] = []
        if satellite_observations:
            satellite_results = self.satellite_engine.analyze_batch(satellite_observations)
            for sr in satellite_results:
                all_features.extend(sr.features)

        # --- Alpha Discovery ---
        alpha_result = None
        if all_features:
            alpha_result = self.alpha_discovery.generate(all_features)

        # --- Data Fusion ---
        fusion_report = None
        if alpha_result and alpha_result.candidates:
            fusion_report = self.fusion_engine.combine_from_candidates(
                candidates=alpha_result.candidates,
                traditional_alphas=traditional_alphas,
                macro_alphas=macro_alphas,
                regime=regime,
            )

        # --- Summary ---
        actionable = alpha_result.actionable_candidates if alpha_result else 0
        summary = (
            f"Alternative Intelligence Report: "
            f"{len(news_analyses)} news, {len(sentiment_results)} social, "
            f"{len(web_results)} web, {len(satellite_results)} satellite → "
            f"{len(all_features)} features → {actionable} actionable signals"
        )

        return AlternativeIntelligenceReport(
            news_analyses=news_analyses,
            news_sector_sentiment=news_sector_sentiment,
            sentiment_results=sentiment_results,
            asset_sentiments=asset_sentiments,
            trending_topics=trending_topics,
            web_results=web_results,
            web_profiles=web_profiles,
            satellite_results=satellite_results,
            alpha_discovery=alpha_result,
            fusion_report=fusion_report,
            summary=summary,
            actionable_signals=actionable,
        )

    # ------------------------------------------------------------------
    # Public API: analyze_quick() — fast path
    # ------------------------------------------------------------------

    def analyze_quick(
        self,
        news_text: str = "",
        social_text: str = "",
        web_metric_type: str = "",
        web_value: float = 0.0,
        web_change: float = 0.0,
    ) -> AlternativeIntelligenceReport:
        """Quick analysis with minimal inputs — good for testing and demos."""
        news_articles = [news_text] if news_text else []
        social_posts = [social_text] if social_text else []
        web_metrics = None
        if web_metric_type:
            web_metrics = [
                WebMetric(
                    metric_type=web_metric_type,
                    value=web_value,
                    change_pct=web_change,
                )
            ]

        return self.analyze_full(
            news_articles=news_articles or None,
            social_posts=social_posts or None,
            web_metrics=web_metrics,
        )

    # ------------------------------------------------------------------
    # Public API: memory utilities
    # ------------------------------------------------------------------

    def search_memory(self, query: str, limit: int = 10) -> list:
        """Search alternative intelligence memory for similar past analyses."""
        result = self.memory.search_similar(query, limit=limit)
        return result.entries

    def get_memory_stats(self) -> dict:
        """Get alternative intelligence memory statistics."""
        return self.memory.get_stats()

    # ------------------------------------------------------------------
    # Clear all state
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.news_engine.clear_history()
        self.sentiment_engine.clear()
        self.web_engine.clear()
        self.satellite_engine.clear()
        self.alpha_discovery.clear()
        self.fusion_engine.clear()
        self.memory.clear()
        self.collector.clear()
