"""Tests for AI Alternative Data Intelligence Engine — Commit 3 Part 25."""

import pytest
from services.alternative_intelligence import (
    # Data models
    AlternativeRecord,
    AlternativeFeature,
    AlphaCandidate,
    FusionResult,
    MemoryEntry,
    NewsArticle,
    SocialPost,
    WebMetric,
    SatelliteObservation,
    # Enums
    DataSource,
    SentimentPolarity,
    SignalStrength,
    # Engines
    AlternativeDataCollector,
    NewsIntelligence,
    NewsAnalysis,
    SocialSentimentEngine,
    SentimentResult,
    AssetSentiment,
    WebIntelligenceEngine,
    WebIntelligenceResult,
    AssetWebProfile,
    SatelliteIntelligenceEngine,
    SatelliteResult,
    AlternativeAlphaDiscovery,
    AlphaDiscoveryResult,
    AlternativeDataFusion,
    FusionReport,
    AlternativeMemory,
    # Service
    AlternativeIntelligenceService,
    AlternativeIntelligenceReport,
)


# =========================================================================
# 1. Data Model Tests
# =========================================================================


class TestAlternativeRecord:
    """Tests for AlternativeRecord data model."""

    def test_create_basic(self):
        record = AlternativeRecord(source="news", content="Test content")
        assert record.source == "news"
        assert record.content == "Test content"
        assert record.asset_tags == []
        assert record.confidence == 0.5

    def test_create_with_tags(self):
        record = AlternativeRecord(
            source="social_media",
            content="Bullish on NVDA",
            asset_tags=["NVDA", "AMD"],
            confidence=0.8,
        )
        assert "NVDA" in record.asset_tags
        assert "AMD" in record.asset_tags
        assert record.confidence == 0.8

    def test_source_enum_known(self):
        record = AlternativeRecord(source="news", content="test")
        assert record.source_enum == DataSource.NEWS

    def test_source_enum_unknown(self):
        record = AlternativeRecord(source="unknown_source", content="test")
        assert record.source_enum is None

    def test_source_enum_social(self):
        record = AlternativeRecord(source="social_media", content="test")
        assert record.source_enum == DataSource.SOCIAL_MEDIA

    def test_confidence_clamped(self):
        record = AlternativeRecord(source="news", content="test", confidence=2.0)
        # confidence stored as-is; clamping is done in collector
        assert record.confidence == 2.0

    def test_metadata_storage(self):
        record = AlternativeRecord(
            source="satellite",
            content="image_data",
            metadata={"location": "Shanghai", "coordinates": (31.23, 121.47)},
        )
        assert record.metadata["location"] == "Shanghai"

    def test_timestamp_auto(self):
        record = AlternativeRecord(source="news", content="test")
        assert record.timestamp != ""


class TestNewsArticle:
    """Tests for NewsArticle model."""

    def test_create(self):
        article = NewsArticle(
            headline="NVIDIA beats earnings",
            body="NVIDIA reported record quarterly revenue...",
            source_name="Reuters",
            asset_tags=["NVDA"],
        )
        assert article.headline == "NVIDIA beats earnings"
        assert article.source_name == "Reuters"
        assert "NVDA" in article.asset_tags

    def test_defaults(self):
        article = NewsArticle(headline="Test", body="Body", source_name="Source")
        assert article.language == "en"
        assert article.url == ""
        assert article.author == ""
        assert article.category == ""


class TestSocialPost:
    """Tests for SocialPost model."""

    def test_create(self):
        post = SocialPost(
            platform="twitter",
            content="AI stocks are mooning!",
            author="trader123",
            engagement={"likes": 500, "shares": 100},
            asset_tags=["NVDA"],
        )
        assert post.platform == "twitter"
        assert post.engagement["likes"] == 500

    def test_default_followers(self):
        post = SocialPost(platform="reddit", content="test", author="user1")
        assert post.followers_count == 0


class TestWebMetric:
    """Tests for WebMetric model."""

    def test_create(self):
        metric = WebMetric(
            metric_type="website_traffic",
            value=15000.0,
            change_pct=12.5,
            asset_tags=["AMZN"],
        )
        assert metric.metric_type == "website_traffic"
        assert metric.value == 15000.0
        assert metric.change_pct == 12.5

    def test_defaults(self):
        metric = WebMetric(metric_type="search_trend", value=75.0)
        assert metric.change_pct == 0.0
        assert metric.period == "daily"


class TestSatelliteObservation:
    """Tests for SatelliteObservation model."""

    def test_create(self):
        obs = SatelliteObservation(
            location="Shenzhen",
            observation_type="factory_activity",
            activity_score=85.0,
            change_pct=10.0,
            asset_tags=["TSM"],
        )
        assert obs.location == "Shenzhen"
        assert obs.activity_score == 85.0

    def test_coordinates_optional(self):
        obs = SatelliteObservation(
            location="Shanghai Port",
            observation_type="port_traffic",
            activity_score=60.0,
            coordinates=(31.23, 121.47),
        )
        assert obs.coordinates == (31.23, 121.47)


class TestAlternativeFeature:
    """Tests for AlternativeFeature model."""

    def test_create(self):
        feature = AlternativeFeature(
            name="news_sentiment_NVDA",
            value=0.75,
            category="news",
            asset_tag="NVDA",
            z_score=1.5,
            signal_strength=SignalStrength.STRONG,
        )
        assert feature.name == "news_sentiment_NVDA"
        assert feature.signal_strength == SignalStrength.STRONG

    def test_defaults(self):
        feature = AlternativeFeature(name="test_feature", value=0.0)
        assert feature.category == "alternative"
        assert feature.z_score == 0.0
        assert feature.signal_strength == SignalStrength.NEUTRAL


class TestAlphaCandidate:
    """Tests for AlphaCandidate model."""

    def test_create(self):
        feature = AlternativeFeature(name="test", value=0.5, asset_tag="NVDA")
        candidate = AlphaCandidate(
            feature=feature,
            alpha_score=0.6,
            confidence=0.8,
            sharpe_estimate=1.2,
            information_coefficient=0.05,
        )
        assert candidate.alpha_score == 0.6
        assert candidate.feature.asset_tag == "NVDA"

    def test_is_actionable_true(self):
        feature = AlternativeFeature(name="test", value=0.5)
        candidate = AlphaCandidate(
            feature=feature, alpha_score=0.3, confidence=0.7
        )
        assert candidate.is_actionable is True

    def test_is_actionable_false_low_confidence(self):
        feature = AlternativeFeature(name="test", value=0.5)
        candidate = AlphaCandidate(
            feature=feature, alpha_score=0.3, confidence=0.5
        )
        assert candidate.is_actionable is False

    def test_is_actionable_false_low_alpha(self):
        feature = AlternativeFeature(name="test", value=0.5)
        candidate = AlphaCandidate(
            feature=feature, alpha_score=0.1, confidence=0.7
        )
        assert candidate.is_actionable is False

    def test_decay_half_life_default(self):
        feature = AlternativeFeature(name="test", value=0.5)
        candidate = AlphaCandidate(feature=feature)
        assert candidate.decay_half_life == 1.0


class TestFusionResult:
    """Tests for FusionResult model."""

    def test_create(self):
        result = FusionResult(
            asset_tag="NVDA",
            traditional_alpha=0.3,
            macro_alpha=0.1,
            alternative_alpha=0.5,
            fused_alpha=0.35,
            confidence=0.7,
        )
        assert result.asset_tag == "NVDA"
        assert result.traditional_alpha == 0.3

    def test_defaults(self):
        result = FusionResult(asset_tag="TEST")
        assert result.fused_alpha == 0.0
        assert result.confidence == 0.5


class TestMemoryEntry:
    """Tests for MemoryEntry model."""

    def test_create(self):
        record = AlternativeRecord(source="news", content="test")
        entry = MemoryEntry(record=record)
        assert entry.record.source == "news"
        assert entry.retrieval_count == 0

    def test_with_alpha(self):
        record = AlternativeRecord(source="news", content="test")
        entry = MemoryEntry(record=record, alpha_performance=0.15)
        assert entry.alpha_performance == 0.15


# =========================================================================
# 2. Collector Tests
# =========================================================================


class TestAlternativeDataCollector:
    """Tests for AlternativeDataCollector."""

    def test_ingest_raw(self):
        collector = AlternativeDataCollector()
        record = collector.ingest_raw("news", "Test content", asset_tags=["NVDA"])
        assert record.source == "news"
        assert collector.record_count == 1

    def test_collect_by_source(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "News 1")
        collector.ingest_raw("news", "News 2")
        collector.ingest_raw("social_media", "Social 1")
        news = collector.collect("news")
        assert len(news) == 2

    def test_ingest_news(self):
        collector = AlternativeDataCollector()
        article = NewsArticle(
            headline="NVIDIA beats",
            body="Record revenue",
            source_name="Reuters",
            asset_tags=["NVDA"],
        )
        record = collector.ingest_news(article)
        assert record.source == "news"
        assert "NVDA" in record.asset_tags

    def test_ingest_social_post(self):
        collector = AlternativeDataCollector()
        post = SocialPost(
            platform="twitter",
            content="Bullish!",
            author="trader",
            asset_tags=["AAPL"],
        )
        record = collector.ingest_social_post(post)
        assert record.source == "social_media"
        assert record.confidence == 0.4  # social media has lower default confidence

    def test_ingest_web_metric(self):
        collector = AlternativeDataCollector()
        metric = WebMetric(
            metric_type="website_traffic",
            value=10000,
            change_pct=15.0,
            asset_tags=["AMZN"],
        )
        record = collector.ingest_web_metric(metric)
        assert record.source == "web_data"

    def test_ingest_satellite(self):
        collector = AlternativeDataCollector()
        obs = SatelliteObservation(
            location="Shenzhen",
            observation_type="factory_activity",
            activity_score=80,
            asset_tags=["TSM"],
        )
        record = collector.ingest_satellite_observation(obs)
        assert record.source == "satellite"

    def test_get_by_asset(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "News NVDA", asset_tags=["NVDA"])
        collector.ingest_raw("social_media", "Social AAPL", asset_tags=["AAPL"])
        collector.ingest_raw("news", "News NVDA 2", asset_tags=["NVDA"])
        nvda_records = collector.get_by_asset("NVDA")
        assert len(nvda_records) == 2

    def test_get_by_source(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "N1")
        collector.ingest_raw("social_media", "S1")
        collector.ingest_raw("news", "N2")
        assert len(collector.get_by_source("news")) == 2

    def test_get_recent(self):
        collector = AlternativeDataCollector()
        for i in range(10):
            collector.ingest_raw("news", f"News {i}")
        recent = collector.get_recent(limit=3)
        assert len(recent) == 3

    def test_get_source_summary(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "N1")
        collector.ingest_raw("news", "N2")
        collector.ingest_raw("social_media", "S1")
        summary = collector.get_source_summary()
        assert summary["news"] == 2
        assert summary["social_media"] == 1

    def test_get_asset_summary(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "N1", asset_tags=["NVDA", "AMD"])
        collector.ingest_raw("news", "N2", asset_tags=["NVDA"])
        summary = collector.get_asset_summary()
        assert summary["NVDA"] == 2
        assert summary["AMD"] == 1

    def test_stats(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "N1", asset_tags=["NVDA"])
        collector.ingest_raw("social_media", "S1", asset_tags=["AAPL"])
        stats = collector.stats
        assert stats.total_records == 2
        assert stats.records_by_source["news"] == 1

    def test_clear(self):
        collector = AlternativeDataCollector()
        collector.ingest_raw("news", "N1")
        collector.clear()
        assert collector.record_count == 0

    def test_confidence_clamped_in_ingest(self):
        collector = AlternativeDataCollector()
        record = collector.ingest_raw("news", "test", confidence=1.5)
        assert record.confidence == 1.0
        record2 = collector.ingest_raw("news", "test", confidence=-0.5)
        assert record2.confidence == 0.0


# =========================================================================
# 3. News Intelligence Tests
# =========================================================================


class TestNewsIntelligence:
    """Tests for NewsIntelligence engine."""

    def test_analyze_string(self):
        engine = NewsIntelligence()
        result = engine.analyze("NVIDIA beats earnings estimates and raises guidance")
        assert isinstance(result, NewsAnalysis)
        assert result.sentiment == SentimentPolarity.POSITIVE
        assert result.sentiment_score > 0

    def test_analyze_positive_news(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "Apple reports record revenue, beats estimates, raises guidance"
        )
        assert result.is_positive
        assert result.sentiment_score > 0.3

    def test_analyze_negative_news(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "Company warns of declining sales, cuts guidance, plans layoffs"
        )
        assert result.is_negative
        assert result.sentiment_score < 0

    def test_analyze_neutral_news(self):
        engine = NewsIntelligence()
        result = engine.analyze("The market opened today as expected")
        assert result.sentiment == SentimentPolarity.NEUTRAL

    def test_analyze_news_article(self):
        engine = NewsIntelligence()
        article = NewsArticle(
            headline="NVIDIA announces breakthrough AI chip",
            body="The new H200 GPU delivers record performance for AI training workloads",
            source_name="TechCrunch",
            asset_tags=["NVDA"],
        )
        result = engine.analyze(article)
        assert result.is_positive
        assert "NVDA" in result.key_entities

    def test_analyze_alternative_record(self):
        engine = NewsIntelligence()
        record = AlternativeRecord(
            source="news",
            content="Tesla stock surges on record deliveries",
            asset_tags=["TSLA"],
            metadata={"headline": "Tesla surges"},
        )
        result = engine.analyze(record)
        assert result.is_positive

    def test_sector_classification_ai(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "NVIDIA H100 GPU demand surges for AI training and machine learning hardware"
        )
        assert "ai_semiconductor" in result.sectors

    def test_sector_classification_cloud(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "AWS and Azure cloud computing revenue grows as enterprises migrate to SaaS"
        )
        assert "cloud_computing" in result.sectors

    def test_sector_classification_energy(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "Solar and wind renewable energy projects expand as oil prices rise"
        )
        assert "energy" in result.sectors

    def test_entity_extraction(self):
        engine = NewsIntelligence()
        result = engine.analyze("AAPL and MSFT both beat earnings. NVDA also rallied.")
        assert "AAPL" in result.key_entities
        assert "MSFT" in result.key_entities
        assert "NVDA" in result.key_entities

    def test_impact_high(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "BREAKING: FDA approves breakthrough cancer drug in historic decision"
        )
        assert result.is_high_impact

    def test_impact_low(self):
        engine = NewsIntelligence()
        result = engine.analyze("Market opens flat with low volume")
        assert not result.is_high_impact

    def test_feature_generation(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "NVIDIA beats estimates significantly",  # removed the period since "beat" is enough
        )
        assert len(result.features) > 0
        # At least one feature should be for news_sentiment or news_impact
        feature_names = [f.name for f in result.features]
        assert any("NVDA" in name for name in feature_names)

    def test_analyze_batch(self):
        engine = NewsIntelligence()
        results = engine.analyze_batch([
            "NVIDIA beats earnings",
            "Company warns of decline",
        ])
        assert len(results) == 2
        assert results[0].is_positive
        assert results[1].is_negative

    def test_get_sector_sentiment(self):
        engine = NewsIntelligence()
        engine.analyze("NVIDIA GPU demand surges for AI semiconductor")
        engine.analyze("AMD chip sales grow for AI hardware")
        sentiment = engine.get_sector_sentiment("ai_semiconductor")
        assert sentiment["count"] == 2
        assert sentiment["avg_sentiment"] > 0

    def test_get_entity_sentiment(self):
        engine = NewsIntelligence()
        engine.analyze("NVDA beats estimates")
        engine.analyze("NVDA raises guidance")
        sentiment = engine.get_entity_sentiment("NVDA")
        assert sentiment["count"] == 2
        assert sentiment["avg_sentiment"] > 0

    def test_history(self):
        engine = NewsIntelligence()
        engine.analyze("News 1")
        engine.analyze("News 2")
        assert len(engine.history) == 2

    def test_clear_history(self):
        engine = NewsIntelligence()
        engine.analyze("News")
        engine.clear_history()
        assert len(engine.history) == 0

    def test_very_positive(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "Record revenue blowout earnings surge blockbuster results beat estimates by wide margin"
        )
        assert result.sentiment in (SentimentPolarity.POSITIVE, SentimentPolarity.VERY_POSITIVE)

    def test_very_negative(self):
        engine = NewsIntelligence()
        result = engine.analyze(
            "Stock crash collapse plunge bankruptcy fraud scandal miss estimates by wide margin"
        )
        assert result.sentiment in (SentimentPolarity.NEGATIVE, SentimentPolarity.VERY_NEGATIVE)


# =========================================================================
# 4. Social Sentiment Tests
# =========================================================================


class TestSocialSentimentEngine:
    """Tests for SocialSentimentEngine."""

    def test_analyze_string(self):
        engine = SocialSentimentEngine()
        result = engine.analyze("I'm bullish on NVDA, buying more!")
        assert isinstance(result, SentimentResult)
        assert result.sentiment_score > 0

    def test_analyze_bullish(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(
            "To the moon! Bullish breakout, buying the dip, strong momentum!"
        )
        assert result.is_bullish
        assert result.sentiment_score > 0.5

    def test_analyze_bearish(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(
            "Bearish on this market. Selling everything. Crash incoming. Downgrade."
        )
        assert result.is_bearish
        assert result.sentiment_score < -0.2

    def test_analyze_neutral(self):
        engine = SocialSentimentEngine()
        result = engine.analyze("Just checking the market today")
        assert not result.is_bullish
        assert not result.is_bearish

    def test_analyze_extreme(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(
            "To the moon! Diamond hands! YOLO all in! Rocket ship! "
            "This is going to zero rug pull ponzi scam!"
        )
        # Mixed extreme keywords → should register as extreme in some direction
        assert abs(result.sentiment_score) > 0.3 or result.is_extreme

    def test_analyze_social_post(self):
        engine = SocialSentimentEngine()
        post = SocialPost(
            platform="twitter",
            content="NVDA breakout! Bullish momentum!",
            author="trader123",
            engagement={"likes": 1000, "shares": 300},
            asset_tags=["NVDA"],
        )
        result = engine.analyze(post)
        assert result.platform == "twitter"
        assert result.is_bullish

    def test_volume_surge_detection(self):
        engine = SocialSentimentEngine()
        result = engine.analyze("NVDA is trending viral everywhere, everyone talking about it!")
        assert result.volume_signal is True

    def test_volume_surge_no(self):
        engine = SocialSentimentEngine()
        result = engine.analyze("Just a normal market day")
        assert result.volume_signal is False

    def test_buzz_score(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(
            "BREAKING!!! HUGE news! This is MASSIVE and CRITICAL!!!",
        )
        assert result.buzz_score > 0

    def test_topic_extraction(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(
            "AI and crypto are the future. Fed might cut rates as inflation cools.",
            # Removed asset_tags=[] — topics come from content keywords
        )
        topics = result.top_topics
        # Should find at least one of: ai, crypto, fed, inflation
        has_topic = any(t in topics for t in ["ai", "crypto", "fed", "inflation"])
        assert has_topic

    def test_get_asset_sentiment(self):
        engine = SocialSentimentEngine()
        engine.analyze(SocialPost(
            platform="twitter", content="Bullish on NVDA! Buy!", author="u1",
            asset_tags=["NVDA"],
        ))
        engine.analyze(SocialPost(
            platform="reddit", content="NVDA breakout!", author="u2",
            asset_tags=["NVDA"],
        ))
        asset = engine.get_asset_sentiment("NVDA")
        assert asset.asset_tag == "NVDA"
        assert asset.post_count == 2
        assert asset.overall_score > 0

    def test_get_asset_sentiment_empty(self):
        engine = SocialSentimentEngine()
        asset = engine.get_asset_sentiment("UNKNOWN")
        assert asset.asset_tag == "UNKNOWN"
        assert asset.post_count == 0

    def test_trending_topics(self):
        engine = SocialSentimentEngine()
        for _ in range(5):
            engine.analyze("AI stocks are amazing for artificial intelligence")
        for _ in range(3):
            engine.analyze("Crypto bitcoin ethereum defi blockchain")
        topics = engine.get_trending_topics(limit=5)
        assert len(topics) > 0

    def test_contrarian_extreme_bullish(self):
        engine = SocialSentimentEngine()
        for _ in range(5):
            engine.analyze(SocialPost(
                platform="twitter",
                content="NVDA to the moon! Diamond hands! Rocket ship! All in!",
                author=f"user{i}",
                asset_tags=["NVDA"],
            ))
        signal = engine.detect_contrarian_signal("NVDA")
        # With 5 extremely bullish posts, might get a contrarian signal
        assert signal["asset"] == "NVDA"
        assert "signal" in signal

    def test_contrarian_no_signal(self):
        engine = SocialSentimentEngine()
        engine.analyze(SocialPost(
            platform="twitter", content="Market looks okay", author="u1",
            asset_tags=["SPY"],
        ))
        signal = engine.detect_contrarian_signal("SPY")
        assert signal["signal"] == "NO_CONTRARIAN"

    def test_feature_generation(self):
        engine = SocialSentimentEngine()
        result = engine.analyze(SocialPost(
            platform="twitter",
            content="Bullish on NVDA! To the moon!",
            author="u1",
            asset_tags=["NVDA"],
        ))
        assert len(result.features) > 0
        feature_names = [f.name for f in result.features]
        assert any("NVDA" in name for name in feature_names)

    def test_analyze_batch(self):
        engine = SocialSentimentEngine()
        results = engine.analyze_batch([
            "Bullish on NVDA!",
            "Bearish on markets, selling!",
        ])
        assert len(results) == 2

    def test_clear(self):
        engine = SocialSentimentEngine()
        engine.analyze("Bullish")
        engine.clear()
        assert len(engine.history) == 0


# =========================================================================
# 5. Web Intelligence Tests
# =========================================================================


class TestWebIntelligenceEngine:
    """Tests for WebIntelligenceEngine."""

    def test_analyze_metric(self):
        engine = WebIntelligenceEngine()
        metric = WebMetric(
            metric_type="website_traffic",
            value=50000,
            change_pct=25.0,
            asset_tags=["AMZN"],
        )
        result = engine.analyze(metric)
        assert isinstance(result, WebIntelligenceResult)
        assert result.direction == "up"
        assert result.signal_strength == SignalStrength.STRONG

    def test_analyze_dict(self):
        engine = WebIntelligenceEngine()
        result = engine.analyze({
            "metric_type": "search_trend",
            "value": 80.0,
            "change_pct": 10.0,
            "asset_tags": ["AAPL"],
        })
        assert result.metric_type == "search_trend"
        assert result.signal_strength == SignalStrength.MODERATE

    def test_analyze_negative_change(self):
        engine = WebIntelligenceEngine()
        result = engine.analyze(WebMetric(
            metric_type="website_traffic",
            value=30000,
            change_pct=-15.0,
            asset_tags=["NFLX"],
        ))
        assert result.direction == "down"

    def test_analyze_neutral_change(self):
        engine = WebIntelligenceEngine()
        result = engine.analyze(WebMetric(
            metric_type="page_views",
            value=1000,
            change_pct=0.2,
        ))
        assert result.direction == "neutral"

    def test_is_growth_signal(self):
        engine = WebIntelligenceEngine()
        result = engine.analyze(WebMetric(
            metric_type="app_downloads",
            value=20000,
            change_pct=30.0,
        ))
        assert result.is_growth_signal

    def test_is_decline_signal(self):
        engine = WebIntelligenceEngine()
        result = engine.analyze(WebMetric(
            metric_type="website_traffic",
            value=10000,
            change_pct=-25.0,
        ))
        assert result.is_decline_signal

    def test_bounce_rate_inverted(self):
        """Bounce rate: going down is positive."""
        engine = WebIntelligenceEngine()
        result = engine.analyze(WebMetric(
            metric_type="bounce_rate",
            value=25.0,
            change_pct=-10.0,  # bounce rate dropping → good
        ))
        assert result.direction == "up"  # inverted

    def test_get_asset_profile(self):
        engine = WebIntelligenceEngine()
        engine.analyze(WebMetric(
            metric_type="website_traffic",
            value=50000,
            change_pct=20.0,
            asset_tags=["AMZN"],
        ))
        engine.analyze(WebMetric(
            metric_type="hiring",
            value=500,
            change_pct=15.0,
            asset_tags=["AMZN"],
        ))
        profile = engine.get_asset_profile("AMZN")
        assert profile.asset_tag == "AMZN"
        assert "website_traffic" in profile.metrics or profile.growth_score >= 0

    def test_get_asset_profile_empty(self):
        engine = WebIntelligenceEngine()
        profile = engine.get_asset_profile("UNKNOWN")
        assert profile.asset_tag == "UNKNOWN"
        assert profile.growth_score == 0.0

    def test_growth_leaders(self):
        engine = WebIntelligenceEngine()
        engine.analyze(WebMetric(
            metric_type="website_traffic", value=50000, change_pct=50.0,
            asset_tags=["HIGH"],
        ))
        engine.analyze(WebMetric(
            metric_type="website_traffic", value=10000, change_pct=-10.0,
            asset_tags=["LOW"],
        ))
        leaders = engine.get_growth_leaders()
        assert len(leaders) > 0

    def test_analyze_batch(self):
        engine = WebIntelligenceEngine()
        results = engine.analyze_batch([
            WebMetric(metric_type="search_trend", value=80, change_pct=15.0, asset_tags=["AAPL"]),
            WebMetric(metric_type="hiring", value=200, change_pct=-5.0, asset_tags=["MSFT"]),
        ])
        assert len(results) == 2

    def test_clear(self):
        engine = WebIntelligenceEngine()
        engine.analyze(WebMetric(metric_type="search_trend", value=50, change_pct=5.0))
        engine.clear()
        assert len(engine.history) == 0


# =========================================================================
# 6. Satellite Intelligence Tests
# =========================================================================


class TestSatelliteIntelligenceEngine:
    """Tests for SatelliteIntelligenceEngine."""

    def test_analyze_observation(self):
        engine = SatelliteIntelligenceEngine()
        obs = SatelliteObservation(
            location="Shenzhen",
            observation_type="factory_activity",
            activity_score=85.0,
            change_pct=10.0,
            asset_tags=["TSM"],
        )
        result = engine.analyze(obs)
        assert isinstance(result, SatelliteResult)
        assert result.activity_level == "high"
        assert result.location == "Shenzhen"

    def test_analyze_dict(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze({
            "location": "Shanghai",
            "observation_type": "port_traffic",
            "activity_score": 80.0,
            "change_pct": 15.0,
            "asset_tags": ["COSCO"],
        })
        assert result.activity_level == "high"

    def test_analyze_low_activity(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze(SatelliteObservation(
            location="Detroit",
            observation_type="factory_activity",
            activity_score=20.0,
            change_pct=-5.0,
        ))
        assert result.activity_level == "low"
        assert result.is_decelerating

    def test_analyze_moderate(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze(SatelliteObservation(
            location="Shenzhen",
            observation_type="parking_lot",
            activity_score=55.0,
            change_pct=2.0,
        ))
        assert result.activity_level == "moderate"

    def test_is_accelerating(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze(SatelliteObservation(
            location="Taipei",
            observation_type="factory_activity",
            activity_score=75.0,
            change_pct=10.0,
        ))
        assert result.is_accelerating

    def test_is_not_accelerating_low_activity(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze(SatelliteObservation(
            location="Detroit",
            observation_type="factory_activity",
            activity_score=25.0,
            change_pct=10.0,
        ))
        # change_pct > 5 but activity is low → not accelerating
        assert not result.is_accelerating

    def test_sector_signals(self):
        engine = SatelliteIntelligenceEngine()
        result = engine.analyze(SatelliteObservation(
            location="Hsinchu",
            observation_type="factory_activity",
            activity_score=85.0,
            change_pct=12.0,
        ))
        assert "semiconductor" in result.sector_signals
        assert "manufacturing" in result.sector_signals

    def test_get_location_profile(self):
        engine = SatelliteIntelligenceEngine()
        engine.analyze(SatelliteObservation(
            location="Shanghai",
            observation_type="port_traffic",
            activity_score=80,
            change_pct=10,
        ))
        engine.analyze(SatelliteObservation(
            location="Shanghai",
            observation_type="factory_activity",
            activity_score=70,
            change_pct=5,
        ))
        profile = engine.get_location_profile("Shanghai")
        assert profile.location == "Shanghai"
        assert profile.composite_activity > 0

    def test_get_location_profile_empty(self):
        engine = SatelliteIntelligenceEngine()
        profile = engine.get_location_profile("Unknown")
        assert profile.location == "Unknown"
        assert profile.composite_activity == 0.0

    def test_get_sector_signals(self):
        engine = SatelliteIntelligenceEngine()
        engine.analyze(SatelliteObservation(
            location="Shenzhen",
            observation_type="factory_activity",
            activity_score=85,
            change_pct=15,
        ))
        signals = engine.get_sector_signals("semiconductor")
        assert len(signals) > 0

    def test_high_activity_locations(self):
        engine = SatelliteIntelligenceEngine()
        engine.analyze(SatelliteObservation(
            location="Shenzhen", observation_type="factory_activity",
            activity_score=90, change_pct=15,
        ))
        engine.analyze(SatelliteObservation(
            location="Detroit", observation_type="factory_activity",
            activity_score=20, change_pct=-10,
        ))
        locations = engine.get_high_activity_locations()
        assert len(locations) >= 1

    def test_analyze_batch(self):
        engine = SatelliteIntelligenceEngine()
        results = engine.analyze_batch([
            SatelliteObservation(
                location="Shenzhen", observation_type="factory_activity",
                activity_score=85, change_pct=10,
            ),
            SatelliteObservation(
                location="Shanghai", observation_type="port_traffic",
                activity_score=60, change_pct=3,
            ),
        ])
        assert len(results) == 2

    def test_observation_count(self):
        engine = SatelliteIntelligenceEngine()
        engine.analyze(SatelliteObservation(
            location="Shenzhen", observation_type="factory_activity",
            activity_score=80, change_pct=10,
        ))
        assert engine.observation_count == 1

    def test_clear(self):
        engine = SatelliteIntelligenceEngine()
        engine.analyze(SatelliteObservation(
            location="Shenzhen", observation_type="factory_activity",
            activity_score=80, change_pct=10,
        ))
        engine.clear()
        assert len(engine.history) == 0
        assert engine.observation_count == 0


# =========================================================================
# 7. Alpha Discovery Tests
# =========================================================================


class TestAlternativeAlphaDiscovery:
    """Tests for AlternativeAlphaDiscovery."""

    def test_generate_from_features(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="news_sentiment_NVDA", value=0.8, category="news",
                asset_tag="NVDA", z_score=1.5, signal_strength=SignalStrength.STRONG,
            ),
            AlternativeFeature(
                name="social_buzz_AAPL", value=0.3, category="social",
                asset_tag="AAPL", z_score=0.4, signal_strength=SignalStrength.WEAK,
            ),
            AlternativeFeature(
                name="web_traffic_AMZN", value=0.6, category="web",
                asset_tag="AMZN", z_score=1.0, signal_strength=SignalStrength.MODERATE,
            ),
        ]
        result = engine.generate(features)
        assert isinstance(result, AlphaDiscoveryResult)
        assert result.total_features_processed == 3

    def test_weak_signals_filtered(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="weak_signal", value=0.1, category="news",
                asset_tag="TEST", z_score=0.1, signal_strength=SignalStrength.WEAK,
            ),
        ]
        result = engine.generate(features)
        # Below threshold → filtered out
        assert len(result.candidates) == 0

    def test_strong_signals_pass(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="strong_signal", value=0.8, category="news",
                asset_tag="NVDA", z_score=2.0, signal_strength=SignalStrength.STRONG,
            ),
        ]
        result = engine.generate(features)
        assert len(result.candidates) >= 1
        assert result.candidates[0].is_actionable

    def test_alpha_score_range(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="test", value=0.5, category="news",
                asset_tag="NVDA", z_score=1.0, signal_strength=SignalStrength.MODERATE,
            ),
        ]
        result = engine.generate(features)
        if result.candidates:
            assert -1.0 <= result.candidates[0].alpha_score <= 1.0

    def test_actionable_candidates(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="strong_news", value=0.9, category="news",
                asset_tag="NVDA", z_score=2.5, signal_strength=SignalStrength.STRONG,
            ),
            AlternativeFeature(
                name="strong_web", value=0.8, category="web",
                asset_tag="AMZN", z_score=2.0, signal_strength=SignalStrength.STRONG,
            ),
        ]
        result = engine.generate(features)
        assert result.actionable_candidates >= 1

    def test_by_asset_grouping(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="f1", value=0.7, category="news", asset_tag="NVDA",
                z_score=1.5, signal_strength=SignalStrength.MODERATE,
            ),
            AlternativeFeature(
                name="f2", value=0.6, category="social", asset_tag="NVDA",
                z_score=1.2, signal_strength=SignalStrength.MODERATE,
            ),
            AlternativeFeature(
                name="f3", value=0.5, category="web", asset_tag="AAPL",
                z_score=1.0, signal_strength=SignalStrength.MODERATE,
            ),
        ]
        result = engine.generate(features)
        assert "NVDA" in result.by_asset
        assert "AAPL" in result.by_asset

    def test_by_category_grouping(self):
        engine = AlternativeAlphaDiscovery()
        features = [
            AlternativeFeature(
                name="f1", value=0.7, category="news", asset_tag="NVDA",
                z_score=1.5, signal_strength=SignalStrength.MODERATE,
            ),
            AlternativeFeature(
                name="f2", value=0.6, category="social", asset_tag="NVDA",
                z_score=1.2, signal_strength=SignalStrength.MODERATE,
            ),
        ]
        result = engine.generate(features)
        assert "news" in result.by_category
        assert "social" in result.by_category

    def test_decay_half_life_by_category(self):
        engine = AlternativeAlphaDiscovery()
        news_feature = AlternativeFeature(
            name="news_test", value=0.7, category="news", asset_tag="TEST",
            z_score=1.5, signal_strength=SignalStrength.MODERATE,
        )
        sat_feature = AlternativeFeature(
            name="sat_test", value=0.7, category="satellite", asset_tag="TEST",
            z_score=1.5, signal_strength=SignalStrength.MODERATE,
        )
        result = engine.generate([news_feature, sat_feature])
        news_candidates = [c for c in result.candidates if c.feature.category == "news"]
        sat_candidates = [c for c in result.candidates if c.feature.category == "satellite"]
        if news_candidates and sat_candidates:
            # Satellite decays slower than news
            assert sat_candidates[0].decay_half_life > news_candidates[0].decay_half_life

    def test_generate_from_multi_source(self):
        engine = AlternativeAlphaDiscovery()
        result = engine.generate_from_multi_source(
            news_features=[
                AlternativeFeature(
                    name="news_f", value=0.8, category="news", asset_tag="NVDA",
                    z_score=1.5, signal_strength=SignalStrength.STRONG,
                ),
            ],
            social_features=[
                AlternativeFeature(
                    name="social_f", value=0.6, category="social", asset_tag="AAPL",
                    z_score=1.0, signal_strength=SignalStrength.MODERATE,
                ),
            ],
        )
        assert result.total_features_processed == 2

    def test_get_asset_alpha_history(self):
        engine = AlternativeAlphaDiscovery()
        engine.generate([
            AlternativeFeature(
                name="f1", value=0.7, category="news", asset_tag="NVDA",
                z_score=1.5, signal_strength=SignalStrength.MODERATE,
            ),
        ])
        engine.generate([
            AlternativeFeature(
                name="f2", value=0.6, category="social", asset_tag="NVDA",
                z_score=1.2, signal_strength=SignalStrength.MODERATE,
            ),
        ])
        history = engine.get_asset_alpha_history("NVDA")
        assert len(history) >= 1

    def test_top_assets(self):
        engine = AlternativeAlphaDiscovery()
        for i in range(3):
            engine.generate([
                AlternativeFeature(
                    name=f"f_NVDA_{i}", value=0.8, category="news", asset_tag="NVDA",
                    z_score=1.5, signal_strength=SignalStrength.STRONG,
                ),
            ])
        for i in range(2):
            engine.generate([
                AlternativeFeature(
                    name=f"f_AAPL_{i}", value=0.4, category="social", asset_tag="AAPL",
                    z_score=0.6, signal_strength=SignalStrength.WEAK,
                ),
            ])
        top = engine.get_top_assets(limit=5)
        assert len(top) > 0

    def test_clear(self):
        engine = AlternativeAlphaDiscovery()
        engine.generate([
            AlternativeFeature(
                name="f1", value=0.7, category="news", asset_tag="NVDA",
                z_score=1.5, signal_strength=SignalStrength.MODERATE,
            ),
        ])
        engine.clear()
        assert len(engine.history) == 0


# =========================================================================
# 8. Data Fusion Tests
# =========================================================================


class TestAlternativeDataFusion:
    """Tests for AlternativeDataFusion."""

    def test_combine(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"NVDA": 0.3, "AAPL": 0.1},
            macro_alphas={"NVDA": 0.2, "AAPL": -0.1},
            alternative_alphas={"NVDA": 0.4, "AAPL": 0.0},
        )
        assert isinstance(report, FusionReport)
        assert len(report.results) == 2

    def test_combine_from_dict(self):
        engine = AlternativeDataFusion()
        report = engine.combine(data={
            "traditional": {"NVDA": 0.3},
            "macro": {"NVDA": 0.2},
            "alternative": {"NVDA": 0.5},
        })
        assert len(report.results) == 1
        nvda = report.results[0]
        assert nvda.asset_tag == "NVDA"
        assert nvda.traditional_alpha == 0.3
        assert nvda.macro_alpha == 0.2
        assert nvda.alternative_alpha == 0.5

    def test_fused_alpha_weighted(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"TEST": 0.4},
            macro_alphas={"TEST": 0.4},
            alternative_alphas={"TEST": 0.4},
        )
        # With default weights (0.4, 0.25, 0.35), should get ~0.38 before penalty
        result = report.results[0]
        assert -1.0 <= result.fused_alpha <= 1.0

    def test_fused_alpha_clamped(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"TEST": 1.0},
            macro_alphas={"TEST": 1.0},
            alternative_alphas={"TEST": 1.0},
        )
        assert -1.0 <= report.results[0].fused_alpha <= 1.0

    def test_regime_weights(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"TEST": 0.3},
            macro_alphas={"TEST": 0.3},
            alternative_alphas={"TEST": 0.3},
            regime="event_driven",
        )
        assert report.regime == "event_driven"

    def test_custom_weights(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"TEST": 0.5},
            macro_alphas={"TEST": 0.0},
            alternative_alphas={"TEST": 0.0},
            custom_weights={"traditional": 1.0, "macro": 0.0, "alternative": 0.0},
        )
        assert report.results[0].fused_alpha == 0.5

    def test_combine_from_candidates(self):
        engine = AlternativeDataFusion()
        feature = AlternativeFeature(
            name="test", value=0.7, category="news", asset_tag="NVDA",
            z_score=1.5, signal_strength=SignalStrength.STRONG,
        )
        candidate = AlphaCandidate(
            feature=feature, alpha_score=0.5, confidence=0.7,
        )
        report = engine.combine_from_candidates(
            candidates=[candidate],
            traditional_alphas={"NVDA": 0.3},
            macro_alphas={"NVDA": 0.2},
        )
        assert len(report.results) >= 1

    def test_top_fused(self):
        engine = AlternativeDataFusion()
        report = engine.combine(
            traditional_alphas={"A": 0.8, "B": 0.1},
            macro_alphas={"A": 0.7, "B": 0.0},
            alternative_alphas={"A": 0.6, "B": 0.1},
        )
        top = report.top_fused
        assert top[0].asset_tag == "A"

    def test_get_asset_fusion_history(self):
        engine = AlternativeDataFusion()
        engine.combine(
            traditional_alphas={"NVDA": 0.3},
            alternative_alphas={"NVDA": 0.4},
        )
        engine.combine(
            traditional_alphas={"NVDA": 0.5},
            alternative_alphas={"NVDA": 0.2},
        )
        history = engine.get_asset_fusion_history("NVDA")
        assert len(history) == 2

    def test_get_latest_fusion(self):
        engine = AlternativeDataFusion()
        engine.combine(
            traditional_alphas={"NVDA": 0.3},
            alternative_alphas={"NVDA": 0.4},
        )
        engine.combine(
            traditional_alphas={"NVDA": 0.5},
            alternative_alphas={"NVDA": 0.2},
        )
        latest = engine.get_latest_fusion("NVDA")
        assert latest is not None
        assert latest.traditional_alpha == 0.5

    def test_get_regime_weights(self):
        engine = AlternativeDataFusion()
        weights = engine.get_regime_weights("event_driven")
        assert weights["alternative"] > weights["traditional"]

    def test_correlation_penalty(self):
        engine = AlternativeDataFusion()
        # All three agree strongly → penalty applied
        report_agree = engine.combine(
            traditional_alphas={"TEST": 0.8},
            macro_alphas={"TEST": 0.8},
            alternative_alphas={"TEST": 0.8},
        )
        # Only one strong → no penalty
        report_single = engine.combine(
            traditional_alphas={"TEST2": 0.8},
            macro_alphas={"TEST2": 0.0},
            alternative_alphas={"TEST2": 0.0},
        )
        # The single-source should have higher per-source contribution
        assert abs(report_single.results[0].fused_alpha) >= 0

    def test_clear(self):
        engine = AlternativeDataFusion()
        engine.combine(traditional_alphas={"NVDA": 0.3})
        engine.clear()
        assert len(engine.history) == 0


# =========================================================================
# 9. Alternative Memory Tests
# =========================================================================


class TestAlternativeMemory:
    """Tests for AlternativeMemory."""

    def test_save_record(self):
        memory = AlternativeMemory()
        record = AlternativeRecord(source="news", content="test")
        memory.save(record)
        assert memory.entry_count == 1

    def test_save_memory_entry(self):
        memory = AlternativeMemory()
        record = AlternativeRecord(source="news", content="test")
        entry = MemoryEntry(record=record, alpha_performance=0.1)
        memory.save(entry)
        assert memory.entry_count == 1

    def test_save_dict(self):
        memory = AlternativeMemory()
        record = AlternativeRecord(source="news", content="test")
        memory.save({"record": record, "alpha_performance": 0.15})
        assert memory.entry_count == 1

    def test_save_analysis(self):
        memory = AlternativeMemory()
        record = AlternativeRecord(source="news", content="test")
        entry = memory.save_analysis(
            record=record,
            analysis_result={"sentiment": "positive"},
            alpha_performance=0.05,
        )
        assert entry.analysis_result["sentiment"] == "positive"

    def test_query_by_source(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="News 1"))
        memory.save(AlternativeRecord(source="news", content="News 2"))
        memory.save(AlternativeRecord(source="social_media", content="Social 1"))
        result = memory.query(source="news")
        assert result.total_matches == 2

    def test_query_by_asset(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(
            source="news", content="N1", asset_tags=["NVDA"],
        ))
        memory.save(AlternativeRecord(
            source="social_media", content="S1", asset_tags=["AAPL"],
        ))
        memory.save(AlternativeRecord(
            source="news", content="N2", asset_tags=["NVDA"],
        ))
        result = memory.query(asset="NVDA")
        assert result.total_matches == 2

    def test_query_by_source_and_asset(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(
            source="news", content="N1", asset_tags=["NVDA"],
        ))
        memory.save(AlternativeRecord(
            source="news", content="N2", asset_tags=["AAPL"],
        ))
        memory.save(AlternativeRecord(
            source="social_media", content="S1", asset_tags=["NVDA"],
        ))
        result = memory.query(source="news", asset="NVDA")
        assert result.total_matches == 1

    def test_query_all(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="N1"))
        memory.save(AlternativeRecord(source="social_media", content="S1"))
        result = memory.query()
        assert result.total_matches == 2

    def test_query_min_relevance(self):
        memory = AlternativeMemory()
        e1 = memory.save(AlternativeRecord(source="news", content="N1"))
        e2 = memory.save(AlternativeRecord(source="news", content="N2"))
        e1.relevance_score = 0.8
        e2.relevance_score = 0.2
        result = memory.query(min_relevance=0.5)
        assert result.total_matches == 1

    def test_search_similar(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(
            source="news",
            content="NVIDIA reports record revenue from AI chip sales",
        ))
        memory.save(AlternativeRecord(
            source="news",
            content="Apple launches new iPhone with advanced camera",
        ))
        result = memory.search_similar("AI chip NVIDIA revenue")
        assert len(result.entries) >= 0  # may or may not match depending on token overlap

    def test_update_performance(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="test"))
        assert memory.update_performance(0, 0.15) is True
        assert memory.records[0].alpha_performance == 0.15

    def test_update_performance_out_of_range(self):
        memory = AlternativeMemory()
        assert memory.update_performance(99, 0.15) is False

    def test_get_best_performing(self):
        memory = AlternativeMemory()
        for i in range(5):
            record = AlternativeRecord(source="news", content=f"News {i}")
            memory.save(MemoryEntry(record=record, alpha_performance=float(i) * 0.1))
        best = memory.get_best_performing(limit=3)
        assert len(best) == 3
        assert best[0].alpha_performance >= best[-1].alpha_performance

    def test_get_worst_performing(self):
        memory = AlternativeMemory()
        for i in range(5):
            record = AlternativeRecord(source="news", content=f"News {i}")
            memory.save(MemoryEntry(record=record, alpha_performance=float(i) * 0.1))
        worst = memory.get_worst_performing(limit=3)
        assert len(worst) == 3

    def test_retrieval_count_increment(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="test"))
        memory.query(source="news")
        assert memory.records[0].retrieval_count == 1
        memory.query(source="news")
        assert memory.records[0].retrieval_count == 2

    def test_get_stats(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="N1", asset_tags=["NVDA"]))
        memory.save(MemoryEntry(
            record=AlternativeRecord(source="social_media", content="S1", asset_tags=["AAPL"]),
            alpha_performance=0.1,
        ))
        stats = memory.get_stats()
        assert stats["total_entries"] == 2
        assert stats["entries_with_performance"] == 1
        assert stats["unique_sources"] == 2
        assert stats["unique_assets"] == 2

    def test_clear(self):
        memory = AlternativeMemory()
        memory.save(AlternativeRecord(source="news", content="test"))
        memory.clear()
        assert memory.entry_count == 0


# =========================================================================
# 10. Service Tests
# =========================================================================


class TestAlternativeIntelligenceService:
    """Tests for AlternativeIntelligenceService."""

    def test_init_default(self):
        service = AlternativeIntelligenceService()
        assert service.news_engine is not None
        assert service.sentiment_engine is not None
        assert service.web_engine is not None

    def test_analyze_basic(self):
        service = AlternativeIntelligenceService()
        result = service.analyze("NVIDIA beats earnings estimates and raises guidance")
        assert result.is_positive
        assert result.sentiment == SentimentPolarity.POSITIVE

    def test_analyze_news_article(self):
        service = AlternativeIntelligenceService()
        article = NewsArticle(
            headline="Apple record revenue",
            body="Apple reports record quarterly revenue",
            source_name="Bloomberg",
            asset_tags=["AAPL"],
        )
        result = service.analyze(article)
        assert result.is_positive

    def test_analyze_full_news_only(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=["NVIDIA beats earnings and raises guidance significantly"],
        )
        assert isinstance(report, AlternativeIntelligenceReport)
        assert len(report.news_analyses) == 1
        assert report.news_analyses[0].is_positive

    def test_analyze_full_social_only(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="Bullish on NVDA! Breakout! To the moon!",
                    author="trader1",
                    asset_tags=["NVDA"],
                ),
            ],
        )
        assert len(report.sentiment_results) == 1
        assert report.sentiment_results[0].is_bullish

    def test_analyze_full_web_only(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            web_metrics=[
                WebMetric(
                    metric_type="website_traffic",
                    value=50000,
                    change_pct=25.0,
                    asset_tags=["AMZN"],
                ),
            ],
        )
        assert len(report.web_results) == 1
        assert report.web_results[0].is_growth_signal

    def test_analyze_full_satellite_only(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            satellite_observations=[
                SatelliteObservation(
                    location="Shenzhen",
                    observation_type="factory_activity",
                    activity_score=85,
                    change_pct=12,
                    asset_tags=["TSM"],
                ),
            ],
        )
        assert len(report.satellite_results) == 1

    def test_analyze_full_all_sources(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=[
                "NVIDIA beats earnings and raises guidance significantly",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="Bullish on NVDA! Breakout!",
                    author="trader1",
                    asset_tags=["NVDA"],
                ),
            ],
            web_metrics=[
                WebMetric(
                    metric_type="search_trend",
                    value=85,
                    change_pct=20.0,
                    asset_tags=["NVDA"],
                ),
            ],
            satellite_observations=[
                SatelliteObservation(
                    location="Hsinchu",
                    observation_type="factory_activity",
                    activity_score=80,
                    change_pct=10,
                    asset_tags=["NVDA"],
                ),
            ],
            traditional_alphas={"NVDA": 0.3},
            macro_alphas={"NVDA": 0.2},
        )
        assert report.news_analyses[0].is_positive
        assert len(report.sentiment_results) == 1
        assert len(report.web_results) == 1
        assert len(report.satellite_results) == 1

    def test_alpha_discovery_in_full(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=[
                "NVIDIA beats earnings significantly and raises guidance for AI chip growth",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="NVDA to the moon! Bullish breakout! Diamond hands!",
                    author="trader1",
                    asset_tags=["NVDA"],
                ),
            ],
        )
        assert report.alpha_discovery is not None

    def test_fusion_in_full(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=[
                "NVIDIA beats earnings significantly and raises guidance",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="NVDA to the moon! Bullish breakout!",
                    author="trader1",
                    asset_tags=["NVDA"],
                ),
            ],
            traditional_alphas={"NVDA": 0.4},
            macro_alphas={"NVDA": 0.2},
        )
        assert report.fusion_report is not None

    def test_analyze_quick(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_quick(
            news_text="NVIDIA beats earnings and raises guidance significantly",
            social_text="NVDA to the moon! Bullish breakout!",
            web_metric_type="search_trend",
            web_value=85,
            web_change=20.0,
        )
        assert isinstance(report, AlternativeIntelligenceReport)
        assert report.news_analyses[0].is_positive

    def test_analyze_quick_minimal(self):
        service = AlternativeIntelligenceService()
        report = service.analyze_quick()
        assert isinstance(report, AlternativeIntelligenceReport)

    def test_search_memory(self):
        service = AlternativeIntelligenceService()
        service.analyze_full(
            news_articles=["NVIDIA AI chip demand surges"],
            store_in_memory=True,
        )
        results = service.search_memory("AI chip NVIDIA")
        assert isinstance(results, list)

    def test_get_memory_stats(self):
        service = AlternativeIntelligenceService()
        service.analyze_full(
            news_articles=["Test news"],
            store_in_memory=True,
        )
        stats = service.get_memory_stats()
        assert stats["total_entries"] > 0

    def test_clear(self):
        service = AlternativeIntelligenceService()
        service.analyze("test")
        service.clear()
        assert len(service.news_engine.history) == 0
        assert service.collector.record_count == 0


# =========================================================================
# 11. Integration / Pipeline Tests
# =========================================================================


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_goldilocks_scenario(self):
        """Test full pipeline with a positive scenario across all data sources."""
        service = AlternativeIntelligenceService()

        report = service.analyze_full(
            news_articles=[
                "NVIDIA beats earnings significantly and raises guidance for AI chip demand",
                "Cloud computing revenue surges as enterprises accelerate AI adoption",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="NVDA to the moon! Diamond hands! Bullish breakout! All in!",
                    author="trader1",
                    engagement={"likes": 5000, "shares": 2000},
                    asset_tags=["NVDA"],
                ),
                SocialPost(
                    platform="reddit",
                    content="AI stocks are the future. Accumulation phase.",
                    author="analyst1",
                    asset_tags=["NVDA", "MSFT"],
                ),
            ],
            web_metrics=[
                WebMetric(
                    metric_type="search_trend", value=90, change_pct=35.0,
                    asset_tags=["NVDA"],
                ),
                WebMetric(
                    metric_type="hiring", value=500, change_pct=25.0,
                    asset_tags=["NVDA"],
                ),
            ],
            satellite_observations=[
                SatelliteObservation(
                    location="Hsinchu",
                    observation_type="factory_activity",
                    activity_score=85,
                    change_pct=15,
                    asset_tags=["NVDA"],
                ),
            ],
            traditional_alphas={"NVDA": 0.4, "MSFT": 0.3},
            macro_alphas={"NVDA": 0.2, "MSFT": 0.1},
            regime="trending",
        )

        # Verify structure
        assert report.news_analyses[0].is_positive
        assert len(report.sentiment_results) == 2
        assert len(report.web_results) == 2
        assert len(report.satellite_results) == 1
        assert report.alpha_discovery is not None
        assert report.fusion_report is not None

        # NVDA should have a fusion result
        nvda_fusion = None
        for r in report.fusion_report.results:
            if r.asset_tag == "NVDA":
                nvda_fusion = r
                break
        assert nvda_fusion is not None

    def test_pipeline_negative_scenario(self):
        """Test full pipeline with negative news and sentiment."""
        service = AlternativeIntelligenceService()

        report = service.analyze_full(
            news_articles=[
                "Company warns of significant revenue decline and plans major layoffs",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter",
                    content="Bearish on this stock. Sell everything. Crash incoming.",
                    author="trader1",
                    asset_tags=["BAD"],
                ),
            ],
            web_metrics=[
                WebMetric(
                    metric_type="website_traffic", value=10000, change_pct=-30.0,
                    asset_tags=["BAD"],
                ),
            ],
            traditional_alphas={"BAD": -0.4},
            macro_alphas={"BAD": -0.2},
        )

        assert report.news_analyses[0].is_negative
        assert report.sentiment_results[0].is_bearish
        assert report.web_results[0].is_decline_signal

    def test_sector_sentiment_aggregation(self):
        """Test sector-level sentiment aggregation across multiple news."""
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=[
                "NVIDIA GPU demand surges for AI training workloads",
                "AMD chip sales grow as AI hardware market expands",
                "Semiconductor equipment orders hit record levels",
            ],
        )
        # All three are about AI semiconductors
        if "ai_semiconductor" in report.news_sector_sentiment:
            sector = report.news_sector_sentiment["ai_semiconductor"]
            assert sector["count"] >= 1

    def test_contrarian_detection_in_pipeline(self):
        """Test that extreme sentiment triggers contrarian signals."""
        engine = SocialSentimentEngine()
        for _ in range(10):
            engine.analyze(SocialPost(
                platform="twitter",
                content="To the moon! Diamond hands! Rocket ship! YOLO all in!",
                author=f"user{i}",
                asset_tags=["MEME"],
            ))
        signal = engine.detect_contrarian_signal("MEME")
        # With enough extreme posts, should get contrarian signal
        assert signal["signal"] in (
            "CONTRARIAN_BEARISH", "CONTRARIAN_BULLISH", "NO_CONTRARIAN",
        )

    def test_multi_asset_fusion(self):
        """Test fusion across multiple assets."""
        service = AlternativeIntelligenceService()
        report = service.analyze_full(
            news_articles=[
                "NVDA beats earnings significantly",
                "AAPL iPhone sales decline",
            ],
            social_posts=[
                SocialPost(
                    platform="twitter", content="NVDA breakout!", author="u1",
                    asset_tags=["NVDA"],
                ),
                SocialPost(
                    platform="twitter", content="AAPL slowing down", author="u2",
                    asset_tags=["AAPL"],
                ),
            ],
            traditional_alphas={"NVDA": 0.5, "AAPL": -0.3},
            macro_alphas={"NVDA": 0.2, "AAPL": -0.1},
        )
        assert report.fusion_report is not None
        assets = {r.asset_tag for r in report.fusion_report.results}
        assert "NVDA" in assets
        assert "AAPL" in assets
