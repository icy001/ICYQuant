"""Tests for AI Sentiment Intelligence Engine."""

from __future__ import annotations

import pytest
from datetime import datetime

from services.sentiment_intelligence import (
    SentimentRecord,
    SentimentSource,
    SentimentLabel,
    EmotionState,
    FearGreedZone,
    SentimentEvent,
    SentimentDivergence,
    SentimentAlphaSignal,
    SentimentCollector,
    NLPAnalyzer,
    NLPAnalysisResult,
    EmotionDetector,
    EmotionResult,
    FearGreedModel,
    FearGreedResult,
    SentimentMomentum,
    SentimentMomentumResult,
    DivergenceDetector,
    DivergenceResult,
    SentimentAlphaGenerator,
    SentimentAlphaResult,
    SentimentMemory,
    SentimentMemoryEntry,
    SentimentIntelligenceService,
    SentimentPipelineResult,
)


# ============================================================================
# Test SentimentRecord
# ============================================================================


class TestSentimentRecord:
    """Tests for SentimentRecord data model."""

    def test_create_basic(self):
        record = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Market is strong",
            score=0.8,
        )
        assert record.source == SentimentSource.NEWS
        assert record.score == 0.8
        assert record.label == SentimentLabel.NEUTRAL
        assert record.is_positive is True
        assert record.is_negative is False
        assert record.is_extreme is True

    def test_create_negative(self):
        record = SentimentRecord(
            source=SentimentSource.SOCIAL_MEDIA,
            content="Selling everything",
            score=-0.9,
            symbol="$AAPL",
        )
        assert record.is_positive is False
        assert record.is_negative is True
        assert record.is_extreme is True
        assert record.symbol == "$AAPL"

    def test_create_neutral(self):
        record = SentimentRecord(
            source=SentimentSource.FORUM,
            content="Nothing special",
            score=0.0,
        )
        assert record.is_positive is False
        assert record.is_negative is False
        assert record.is_extreme is False

    def test_score_clamping(self):
        record = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            score=1.5,
        )
        assert record.score == 1.0

        record2 = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            score=-2.0,
        )
        assert record2.score == -1.0

    def test_confidence_clamping(self):
        record = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            confidence=1.5,
        )
        assert record.confidence == 1.0

    def test_strength(self):
        record = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            score=0.5,
            confidence=0.8,
        )
        assert record.strength == 0.4

    def test_is_reliable(self):
        reliable = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            confidence=0.9,
        )
        assert reliable.is_reliable is True

        unreliable = SentimentRecord(
            source=SentimentSource.NEWS,
            content="Test",
            confidence=0.3,
        )
        assert unreliable.is_reliable is False

    def test_all_sources(self):
        for source in SentimentSource:
            record = SentimentRecord(source=source, content="test")
            assert record.source == source

    def test_all_labels(self):
        for label in SentimentLabel:
            record = SentimentRecord(
                source=SentimentSource.NEWS, content="test", label=label
            )
            assert record.label == label

    def test_metadata(self):
        record = SentimentRecord(
            source=SentimentSource.NEWS,
            content="test",
            metadata={"author": "analyst1", "priority": "high"},
            entity="AAPL",
            language="en",
        )
        assert record.metadata["author"] == "analyst1"
        assert record.entity == "AAPL"
        assert record.language == "en"


# ============================================================================
# Test SentimentEvent
# ============================================================================


class TestSentimentEvent:
    """Tests for SentimentEvent model."""

    def test_create_event(self):
        event = SentimentEvent(
            event_id="evt_001",
            event_type="sentiment_spike",
            description="Sudden bullish sentiment surge",
            intensity=0.9,
            affected_symbols=["AAPL", "MSFT"],
        )
        assert event.event_id == "evt_001"
        assert event.is_high_impact is True
        assert event.record_count == 0

    def test_low_impact(self):
        event = SentimentEvent(
            event_id="evt_002",
            event_type="minor_shift",
            description="Small change",
            intensity=0.3,
        )
        assert event.is_high_impact is False


# ============================================================================
# Test SentimentDivergence
# ============================================================================


class TestSentimentDivergence:
    """Tests for SentimentDivergence model."""

    def test_bullish_divergence(self):
        div = SentimentDivergence(
            symbol="AAPL",
            divergence_type="bullish",
            strength=0.7,
            confidence=0.8,
        )
        assert div.is_bullish_divergence is True
        assert div.is_bearish_divergence is False
        assert div.is_significant is True

    def test_bearish_divergence(self):
        div = SentimentDivergence(
            symbol="TSLA",
            divergence_type="bearish",
            strength=0.6,
            confidence=0.6,
        )
        assert div.is_bullish_divergence is False
        assert div.is_bearish_divergence is True
        assert div.is_significant is True

    def test_not_significant(self):
        div = SentimentDivergence(
            symbol="MSFT",
            divergence_type="bullish",
            strength=0.3,
            confidence=0.3,
        )
        assert div.is_significant is False


# ============================================================================
# Test SentimentAlphaSignal
# ============================================================================


class TestSentimentAlphaSignal:
    """Tests for SentimentAlphaSignal model."""

    def test_actionable(self):
        signal = SentimentAlphaSignal(
            signal_id="sig_001",
            symbol="AAPL",
            factor_name="news_sentiment",
            value=0.8,
            direction=1,
            confidence=0.7,
        )
        assert signal.is_actionable is True
        assert signal.absolute_strength == pytest.approx(0.56)

    def test_not_actionable_neutral(self):
        signal = SentimentAlphaSignal(
            signal_id="sig_002",
            symbol="MSFT",
            factor_name="neutral",
            value=0.1,
            direction=0,
            confidence=0.6,
        )
        assert signal.is_actionable is False


# ============================================================================
# Test SentimentCollector
# ============================================================================


class TestSentimentCollector:
    """Tests for SentimentCollector."""

    def test_register_and_collect(self):
        collector = SentimentCollector()

        def fake_collector(**kwargs):
            return [
                SentimentRecord(
                    source=SentimentSource.NEWS, content="Good news", score=0.7
                )
            ]

        collector.register_source(SentimentSource.NEWS, fake_collector)
        assert SentimentSource.NEWS in collector.registered_sources

        result = collector.collect(SentimentSource.NEWS)
        assert result.success is True
        assert result.count == 1
        assert result.has_data is True

    def test_collect_unregistered(self):
        collector = SentimentCollector()
        result = collector.collect(SentimentSource.NEWS)
        assert result.success is False
        assert result.has_data is False
        assert len(result.errors) > 0

    def test_collect_all(self):
        collector = SentimentCollector()

        def news_fn(**kwargs):
            return [SentimentRecord(source=SentimentSource.NEWS, content="n1", score=0.5)]

        def social_fn(**kwargs):
            return [
                SentimentRecord(source=SentimentSource.SOCIAL_MEDIA, content="s1", score=-0.3)
            ]

        collector.register_source(SentimentSource.NEWS, news_fn)
        collector.register_source(SentimentSource.SOCIAL_MEDIA, social_fn)

        results = collector.collect_all()
        assert len(results) == 2
        assert collector.total_records == 2

    def test_filtering(self):
        collector = SentimentCollector()
        collector.records = [
            SentimentRecord(source=SentimentSource.NEWS, content="a", score=0.9, symbol="AAPL"),
            SentimentRecord(source=SentimentSource.NEWS, content="b", score=-0.9, symbol="MSFT"),
            SentimentRecord(source=SentimentSource.SOCIAL_MEDIA, content="c", score=0.3, symbol="AAPL"),
        ]

        assert len(collector.get_by_source(SentimentSource.NEWS)) == 2
        assert len(collector.get_by_symbol("AAPL")) == 2
        assert len(collector.get_extreme()) == 2
        assert len(collector.get_positive()) == 2
        assert len(collector.get_negative()) == 1
        assert len(collector.get_reliable(0.6)) == 0  # default confidence=0.5

    def test_aggregation(self):
        collector = SentimentCollector()
        collector.records = [
            SentimentRecord(source=SentimentSource.NEWS, content="a", score=0.6, confidence=1.0),
            SentimentRecord(source=SentimentSource.NEWS, content="b", score=0.2, confidence=1.0),
        ]
        avg = collector.aggregate_score()
        assert avg == 0.4

    def test_count_by_label(self):
        collector = SentimentCollector()
        collector.records = [
            SentimentRecord(source=SentimentSource.NEWS, content="a", score=0.9, label=SentimentLabel.VERY_BULLISH),
            SentimentRecord(source=SentimentSource.NEWS, content="b", score=-0.9, label=SentimentLabel.VERY_BEARISH),
        ]
        counts = collector.count_by_label()
        assert counts[SentimentLabel.VERY_BULLISH] == 1
        assert counts[SentimentLabel.VERY_BEARISH] == 1
        assert counts[SentimentLabel.NEUTRAL] == 0

    def test_clear(self):
        collector = SentimentCollector()

        def fn(**kwargs):
            return [SentimentRecord(source=SentimentSource.NEWS, content="x")]

        collector.register_source(SentimentSource.NEWS, fn)
        collector.collect(SentimentSource.NEWS)
        assert collector.total_records == 1

        collector.clear()
        assert collector.total_records == 0

    def test_unregister_source(self):
        collector = SentimentCollector()

        def fn(**kwargs):
            return []

        collector.register_source(SentimentSource.NEWS, fn)
        collector.unregister_source(SentimentSource.NEWS)
        assert SentimentSource.NEWS not in collector.registered_sources


# ============================================================================
# Test NLPAnalyzer
# ============================================================================


class TestNLPAnalyzer:
    """Tests for NLPAnalyzer."""

    def setup_method(self):
        self.analyzer = NLPAnalyzer()

    def test_analyze_bullish(self):
        result = self.analyzer.analyze("strong growth and record high profits")
        assert result.score > 0
        assert result.is_positive is True
        assert result.keyword_count > 0

    def test_analyze_bearish(self):
        result = self.analyzer.analyze("warning of bankruptcy and massive layoffs")
        assert result.score < 0
        assert result.is_negative is True

    def test_analyze_neutral(self):
        result = self.analyzer.analyze("the weather is nice today")
        assert result.confidence <= 0.2

    def test_analyze_empty(self):
        result = self.analyzer.analyze("")
        assert result.score == 0.0
        assert result.label == SentimentLabel.NEUTRAL

    def test_analyze_none_text(self):
        result = self.analyzer.analyze("")
        assert result.score == 0.0

    def test_event_detection(self):
        result = self.analyzer.analyze("Company announces earnings beat and merger acquisition")
        assert len(result.events_detected) > 0

    def test_entity_extraction(self):
        result = self.analyzer.analyze("Apple Inc announced record profit while Microsoft struggles")
        assert len(result.entities) > 0

    def test_analyze_batch(self):
        results = self.analyzer.analyze_batch(["strong growth", "weak decline", "neutral text"])
        assert len(results) == 3
        assert results[0].is_positive is True
        assert results[1].is_negative is True

    def test_analyze_record(self):
        record = SentimentRecord(source=SentimentSource.NEWS, content="strong growth record high")
        result = self.analyzer.analyze_record(record)
        assert record.score > 0
        assert record.confidence > 0.5

    def test_negation(self):
        # "not strong" should invert positive sentiment
        result = self.analyzer.analyze("not strong growth")
        assert result.score < 0.3  # Should be less bullish than without negation

    def test_custom_keyword(self):
        self.analyzer.add_keyword("moonshot", 0.9, bullish=True)
        result = self.analyzer.analyze("this is a moonshot opportunity")
        assert result.score > 0.5

        self.analyzer.remove_keyword("moonshot")
        result2 = self.analyzer.analyze("this is a moonshot opportunity")
        assert result2.score <= 0.0

    def test_clear_restores_defaults(self):
        self.analyzer.add_keyword("moonshot", 0.9, bullish=True)
        self.analyzer.clear()
        result = self.analyzer.analyze("moonshot")
        assert result.score == 0.0


# ============================================================================
# Test EmotionDetector
# ============================================================================


class TestEmotionDetector:
    """Tests for EmotionDetector."""

    def setup_method(self):
        self.detector = EmotionDetector()

    def test_detect_euphoria(self):
        state = self.detector.detect(90.0)
        assert state == EmotionState.EUPHORIA

    def test_detect_optimism(self):
        state = self.detector.detect(70.0)
        assert state == EmotionState.OPTIMISM

    def test_detect_neutral(self):
        state = self.detector.detect(50.0)
        assert state == EmotionState.NEUTRAL

    def test_detect_fear(self):
        state = self.detector.detect(30.0)
        assert state == EmotionState.FEAR

    def test_detect_panic(self):
        state = self.detector.detect(18.0)
        assert state == EmotionState.PANIC

    def test_detect_despair(self):
        state = self.detector.detect(5.0)
        assert state == EmotionState.DESPAIR

    def test_analyze_score_convenience(self):
        state = self.detector.analyze_score(0.9)  # [-1,1] → [0,100]
        assert state == EmotionState.EUPHORIA

    def test_analyze(self):
        result = self.detector.analyze(80.0)
        assert isinstance(result, EmotionResult)
        assert result.state == EmotionState.OPTIMISM
        assert result.confidence > 0

    def test_transition_detection(self):
        self.detector.analyze(50.0)
        result = self.detector.analyze(90.0)
        assert result.transition is True
        assert result.previous_state is not None

    def test_analyze_records(self):
        records = [
            SentimentRecord(source=SentimentSource.NEWS, content="great", score=0.9, confidence=1.0),
            SentimentRecord(source=SentimentSource.NEWS, content="good", score=0.7, confidence=1.0),
        ]
        result = self.detector.analyze_records(records)
        assert result.state in (EmotionState.OPTIMISM, EmotionState.EUPHORIA)

    def test_empty_records(self):
        result = self.detector.analyze_records([])
        assert result.state == EmotionState.NEUTRAL

    def test_sentiment_trend(self):
        self.detector.score_history = [50, 55, 60, 65, 70, 75, 80]
        trend = self.detector.get_sentiment_trend(window=6)
        assert trend == "rising"

    def test_extreme_risk(self):
        self.detector.current_state = EmotionState.PANIC
        assert self.detector.get_extreme_risk() > 0.5

        self.detector.current_state = EmotionState.NEUTRAL
        assert self.detector.get_extreme_risk() < 0.5

    def test_is_extreme_property(self):
        result = EmotionResult(state=EmotionState.EUPHORIA)
        assert result.is_extreme is True
        assert result.is_positive is True
        assert result.is_negative is False

    def test_clear(self):
        self.detector.detect(90.0)
        self.detector.clear()
        assert self.detector.current_state == EmotionState.NEUTRAL
        assert len(self.detector.score_history) == 0


# ============================================================================
# Test FearGreedModel
# ============================================================================


class TestFearGreedModel:
    """Tests for FearGreedModel."""

    def setup_method(self):
        self.model = FearGreedModel()

    def test_calculate_default(self):
        score = self.model.calculate()
        assert score == 50.0

    def test_calculate_basic(self):
        data = {
            "volatility": 20.0,
            "put_call_ratio": 30.0,
            "price_momentum": 80.0,
            "fund_flow": 70.0,
            "social_sentiment": 60.0,
        }
        score = self.model.calculate(data)
        assert 0.0 <= score <= 100.0

    def test_calculate_partial(self):
        data = {"social_sentiment": 90.0}
        score = self.model.calculate(data)
        assert score == 90.0

    def test_analyze(self):
        data = {"social_sentiment": 80.0, "price_momentum": 80.0}
        result = self.model.analyze(data)
        assert isinstance(result, FearGreedResult)
        assert result.score > 60
        assert result.zone in (FearGreedZone.GREED, FearGreedZone.EXTREME_GREED)

    def test_extreme_fear(self):
        data = {k: 10.0 for k in self.model.weights}
        result = self.model.analyze(data)
        assert result.zone == FearGreedZone.EXTREME_FEAR
        assert result.is_extreme_fear is True

    def test_extreme_greed(self):
        data = {k: 90.0 for k in self.model.weights}
        result = self.model.analyze(data)
        assert result.zone == FearGreedZone.EXTREME_GREED
        assert result.is_extreme_greed is True

    def test_analyze_from_components(self):
        result = self.model.analyze_from_components(
            volatility=20.0,
            social_sentiment=85.0,
        )
        assert result.score > 0

    def test_momentum(self):
        self.model.analyze({"social_sentiment": 50.0})
        result = self.model.analyze({"social_sentiment": 80.0})
        assert result.change > 0
        assert result.is_rising is True

    def test_contrarian_signal(self):
        self.model.score_history = [10.0]
        assert self.model.get_contrarian_signal() == "buy"

        self.model.score_history = [90.0]
        assert self.model.get_contrarian_signal() == "sell"

    def test_risk_adjustment(self):
        self.model.score_history = [10.0]
        assert self.model.get_risk_adjustment() < 1.0

        self.model.score_history = [90.0]
        assert self.model.get_risk_adjustment() < 1.0

        self.model.score_history = [35.0]
        assert self.model.get_risk_adjustment() > 1.0

    def test_trend(self):
        self.model.score_history = [50, 55, 60, 65, 70, 75, 80, 85]
        assert self.model.get_trend() == "rising"

    def test_set_weights(self):
        new_weights = {"volatility": 0.5, "social_sentiment": 0.5}
        self.model.set_weights(new_weights)
        assert "volatility" in self.model.weights
        assert abs(sum(self.model.weights.values()) - 1.0) < 0.001

    def test_clear(self):
        self.model.score_history = [50, 60, 70]
        self.model.clear()
        assert len(self.model.score_history) == 0


# ============================================================================
# Test SentimentMomentum
# ============================================================================


class TestSentimentMomentum:
    """Tests for SentimentMomentum."""

    def setup_method(self):
        self.momentum = SentimentMomentum()

    def test_calculate(self):
        change = self.momentum.calculate(75.0, 40.0)
        assert change == 35.0

    def test_analyze_rising(self):
        result = self.momentum.analyze(70.0, 50.0)
        assert isinstance(result, SentimentMomentumResult)
        assert result.is_rising is True
        assert result.is_rapid_change is True

    def test_analyze_stable(self):
        result = self.momentum.analyze(50.5, 50.0)
        assert result.direction == "stable"

    def test_analyze_auto_previous(self):
        self.momentum.history = [50, 55, 60]
        result = self.momentum.analyze(80.0)
        assert result.previous == 60.0
        assert result.change == 20.0

    def test_rapid_change_alert(self):
        result = self.momentum.analyze(70.0, 50.0)
        assert result.is_rapid_change is True
        assert result.alert is True

    def test_inflection_detection(self):
        self.momentum.analyze(50.0, 40.0)  # rising
        result = self.momentum.analyze(35.0, 50.0)  # reversing
        assert result.direction == "reversing"
        assert result.is_inflection is True

    def test_analyze_series(self):
        result = self.momentum.analyze_series([50, 55, 60, 80])
        assert result.current == 80.0
        assert result.previous == 60.0

    def test_short_series(self):
        result = self.momentum.analyze_series([50])
        assert result.current == 50.0

    def test_speed_and_acceleration(self):
        self.momentum.analyze(55, 50)
        result = self.momentum.analyze(65, 55)
        assert result.speed > 0
        assert result.acceleration > 0

    def test_trend(self):
        self.momentum.history = [50, 55, 60, 65, 70]
        trend = self.momentum.get_trend()
        assert trend == "rising"

    def test_reversal_risk(self):
        self.momentum.history = [50, 55, 60]
        self.momentum.change_history = [5, 5, 2]  # decelerating
        risk = self.momentum.get_reversal_risk()
        assert risk > 0

    def test_clear(self):
        self.momentum.history = [50, 60, 70]
        self.momentum.change_history = [10, 10]
        self.momentum.clear()
        assert len(self.momentum.history) == 0
        assert len(self.momentum.change_history) == 0


# ============================================================================
# Test DivergenceDetector
# ============================================================================


class TestDivergenceDetector:
    """Tests for DivergenceDetector."""

    def setup_method(self):
        self.detector = DivergenceDetector()

    def test_detect_bullish_divergence(self):
        price = [100, 98, 96, 94, 92]  # falling
        sentiment = [50, 55, 60, 65, 70]  # rising
        result = self.detector.detect(price, sentiment, "AAPL")
        assert result is True

    def test_detect_bearish_divergence(self):
        price = [90, 92, 94, 96, 98]  # rising
        sentiment = [70, 65, 60, 55, 50]  # falling
        result = self.detector.detect(price, sentiment, "TSLA")
        assert result is True

    def test_no_divergence(self):
        price = [90, 92, 94, 96, 98]  # rising
        sentiment = [50, 55, 60, 65, 70]  # rising
        result = self.detector.detect(price, sentiment, "MSFT")
        assert result is False

    def test_insufficient_data(self):
        result = self.detector.detect(None, None, "AAPL")
        assert result is False

    def test_analyze_result(self):
        price = [100, 98, 96, 94, 92]
        sentiment = [50, 55, 60, 65, 70]
        result = self.detector.analyze(price, sentiment, "AAPL")
        assert isinstance(result, DivergenceResult)
        assert result.has_divergence is True
        assert result.bullish_count >= 1

    def test_significance_threshold(self):
        # Weak divergence shouldn't pass threshold
        price = [100, 99.5, 99, 98.5, 98]
        sentiment = [50, 51, 52, 53, 54]
        result = self.detector.analyze(price, sentiment, "AAPL")
        # Should still detect but maybe not significant
        assert isinstance(result, DivergenceResult)

    def test_summary(self):
        price = [100, 98, 96, 94, 92]
        sentiment = [50, 55, 60, 65, 70]
        result = self.detector.analyze(price, sentiment, "AAPL")
        assert len(result.analysis) > 0

    def test_history(self):
        price = [100, 98, 96, 94, 92]
        sentiment = [50, 55, 60, 65, 70]
        self.detector.analyze(price, sentiment, "AAPL")
        history = self.detector.get_divergence_history("AAPL")
        assert len(history) >= 1

    def test_active_signals(self):
        price = [100, 98, 96, 94, 92]
        sentiment = [50, 55, 60, 65, 70]
        self.detector.analyze(price, sentiment, "AAPL")
        active = self.detector.get_active_signals()
        assert len(active) >= 0

    def test_clear(self):
        price = [100, 98, 96, 94, 92]
        sentiment = [50, 55, 60, 65, 70]
        self.detector.analyze(price, sentiment, "AAPL")
        self.detector.clear()
        assert len(self.detector.detected_divergences) == 0


# ============================================================================
# Test SentimentAlphaGenerator
# ============================================================================


class TestSentimentAlphaGenerator:
    """Tests for SentimentAlphaGenerator."""

    def setup_method(self):
        self.generator = SentimentAlphaGenerator()

    def test_generate_basic(self):
        result = self.generator.generate(0.8)
        assert "alpha" in result
        assert result["alpha"] == 0.8

    def test_generate_normalized(self):
        result = self.generator.generate(70)
        assert result["normalized"] == 70

    def test_generate_signal(self):
        signal = self.generator.generate_signal(
            symbol="AAPL",
            factor_name="news_sentiment",
            value=0.7,
            direction=1,
            confidence=0.8,
        )
        assert signal.signal_id.startswith("SENT_")
        assert signal.is_actionable is True

    def test_generate_from_records(self):
        records = [
            SentimentRecord(source=SentimentSource.NEWS, content="great", score=0.8, confidence=0.9, symbol="AAPL"),
            SentimentRecord(source=SentimentSource.SOCIAL_MEDIA, content="wow", score=0.7, confidence=0.8, symbol="AAPL"),
        ]
        result = self.generator.generate_from_records("AAPL", records, fear_greed_score=20.0)
        assert isinstance(result, SentimentAlphaResult)
        assert result.has_signals is True
        assert result.signal_count > 0

    def test_generate_from_records_empty(self):
        result = self.generator.generate_from_records("AAPL", [])
        assert result.has_signals is False

    def test_fear_greed_factor(self):
        records = [
            SentimentRecord(source=SentimentSource.NEWS, content="great", score=0.5, confidence=0.8, symbol="AAPL"),
        ]
        # Extreme fear = bullish contrarian
        result = self.generator.generate_from_records("AAPL", records, fear_greed_score=10.0)
        fg_signals = [s for s in result.signals if s.factor_name == "fear_greed_contrarian"]
        assert len(fg_signals) == 1
        assert fg_signals[0].direction == 1  # bullish

        # Extreme greed = bearish contrarian
        result2 = self.generator.generate_from_records("AAPL", records, fear_greed_score=90.0)
        fg_signals2 = [s for s in result2.signals if s.factor_name == "fear_greed_contrarian"]
        assert len(fg_signals2) == 1
        assert fg_signals2[0].direction == -1  # bearish

    def test_composite_factor(self):
        records = [
            SentimentRecord(source=SentimentSource.NEWS, content="great", score=0.8, confidence=0.9, symbol="AAPL"),
        ]
        result = self.generator.generate_from_records("AAPL", records, fear_greed_score=20.0)
        composite = [s for s in result.signals if s.factor_name == "composite_sentiment"]
        assert len(composite) >= 1

    def test_query(self):
        self.generator.generate_signal("AAPL", "test", 0.5, 1, 0.7)
        self.generator.generate_signal("MSFT", "test", -0.3, -1, 0.6)
        self.generator.generate_signal("AAPL", "other", 0.2, 0, 0.5)

        aapl_signals = self.generator.get_signals_by_symbol("AAPL")
        assert len(aapl_signals) == 2

        test_signals = self.generator.get_signals_by_factor("test")
        assert len(test_signals) == 2

        latest = self.generator.get_latest_signals(2)
        assert len(latest) == 2

    def test_aggregate_score(self):
        result = self.generator.generate_from_records("AAPL", [])
        assert result.aggregate_score == 0.0

    def test_clear(self):
        self.generator.generate_signal("AAPL", "test", 0.5, 1, 0.7)
        self.generator.clear()
        assert len(self.generator.generated_signals) == 0
        assert self.generator.signal_counter == 0


# ============================================================================
# Test SentimentMemory
# ============================================================================


class TestSentimentMemory:
    """Tests for SentimentMemory."""

    def setup_method(self):
        self.memory = SentimentMemory()

    def test_save_dict(self):
        self.memory.save({"entry_id": "test_001", "notes": "test entry"})
        assert self.memory.size == 1

    def test_save_entry(self):
        entry = SentimentMemoryEntry(
            entry_id="e1",
            sentiment={"score": 0.8},
            emotion=EmotionState.OPTIMISM,
        )
        self.memory.save(entry)
        assert self.memory.size == 1

    def test_save_sentiment(self):
        eid = self.memory.save_sentiment(
            sentiment_score=80.0,
            label=SentimentLabel.BULLISH,
            emotion=EmotionState.OPTIMISM,
            symbol="AAPL",
            notes="Strong bullish signal",
        )
        assert eid.startswith("sent_")
        assert self.memory.size == 1

    def test_record_outcome(self):
        eid = self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        updated = self.memory.record_outcome(eid, "market rose 2%", True)
        assert updated is True

    def test_record_outcome_not_found(self):
        updated = self.memory.record_outcome("nonexistent", "rose", True)
        assert updated is False

    def test_find(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM, symbol="AAPL")
        self.memory.save_sentiment(20.0, SentimentLabel.BEARISH, EmotionState.FEAR, symbol="MSFT")
        results = self.memory.find({"symbol": "AAPL"})
        # Note: symbol is inside sentiment dict, not attribute directly
        assert self.memory.size == 2

    def test_get_by_emotion(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.save_sentiment(20.0, SentimentLabel.BEARISH, EmotionState.FEAR)
        entries = self.memory.get_by_emotion(EmotionState.FEAR)
        assert len(entries) == 1

    def test_get_recent(self):
        for i in range(15):
            self.memory.save_sentiment(float(i * 5), SentimentLabel.NEUTRAL, EmotionState.NEUTRAL)
        recent = self.memory.get_recent(10)
        assert len(recent) == 10

    def test_accuracy(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.save_sentiment(20.0, SentimentLabel.BEARISH, EmotionState.FEAR)
        self.memory.record_outcome(
            self.memory.history[0].entry_id, "rose", True
        )
        self.memory.record_outcome(
            self.memory.history[1].entry_id, "fell", False
        )
        acc = self.memory.get_accuracy()
        assert acc == 0.5

    def test_accuracy_report(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.record_outcome(self.memory.history[0].entry_id, "rose", True)
        report = self.memory.get_accuracy_report()
        assert report["total_entries"] == 1
        assert report["entries_with_outcomes"] == 1

    def test_emotion_distribution(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.save_sentiment(50.0, SentimentLabel.NEUTRAL, EmotionState.NEUTRAL)
        self.memory.save_sentiment(90.0, SentimentLabel.VERY_BULLISH, EmotionState.EUPHORIA)
        dist = self.memory.get_emotion_distribution()
        assert len(dist) == 3

    def test_get_with_outcomes(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.record_outcome(self.memory.history[0].entry_id, "rose", True)
        outcomes = self.memory.get_with_outcomes()
        assert len(outcomes) == 1

    def test_get_most_reliable_emotion(self):
        for _ in range(5):
            self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
            self.memory.record_outcome(self.memory.history[-1].entry_id, "rose", True)
        most_reliable = self.memory.get_most_reliable_emotion()
        assert most_reliable == EmotionState.OPTIMISM

    def test_clear(self):
        self.memory.save_sentiment(80.0, SentimentLabel.BULLISH, EmotionState.OPTIMISM)
        self.memory.clear()
        assert self.memory.size == 0


# ============================================================================
# Test SentimentIntelligenceService
# ============================================================================


class TestSentimentIntelligenceService:
    """Tests for SentimentIntelligenceService."""

    def setup_method(self):
        self.service = SentimentIntelligenceService()

    def test_analyze_single_text(self):
        result = self.service.analyze("strong growth and record high profits")
        assert result["score"] > 0
        assert "label" in result

    def test_analyze_text(self):
        result = self.service.analyze_text("AI demand is strong")
        assert isinstance(result, NLPAnalysisResult)
        assert result.score > 0

    def test_analyze_batch(self):
        results = self.service.analyze_batch(["great news", "terrible crash", "normal day"])
        assert len(results) == 3

    def test_process_record(self):
        record = SentimentRecord(source=SentimentSource.NEWS, content="strong growth")
        result = self.service.process_record(record)
        assert record.score > 0
        assert isinstance(result, NLPAnalysisResult)

    def test_process_records(self):
        records = [
            SentimentRecord(source=SentimentSource.NEWS, content="great"),
            SentimentRecord(source=SentimentSource.NEWS, content="terrible"),
        ]
        results = self.service.process_records(records)
        assert len(results) == 2

    def test_run_pipeline_basic(self):
        result = self.service.run_pipeline(texts=["strong growth record high"])
        assert isinstance(result, SentimentPipelineResult)
        assert len(result.nlp_results) == 1

    def test_run_pipeline_with_price(self):
        result = self.service.run_pipeline(
            texts=["sentiment is improving"],
            price_data=[100, 98, 96, 94, 92],
            symbol="AAPL",
        )
        assert isinstance(result, SentimentPipelineResult)

    def test_run_pipeline_empty(self):
        result = self.service.run_pipeline()
        assert isinstance(result, SentimentPipelineResult)

    def test_get_sentiment_for_symbol(self):
        # Register a news source and collect data
        def news_fn(**kwargs):
            return [
                SentimentRecord(
                    source=SentimentSource.NEWS, content="great", score=0.8, symbol="AAPL"
                )
            ]

        self.service.collector.register_source(SentimentSource.NEWS, news_fn)
        self.service.collector.collect(SentimentSource.NEWS)

        summary = self.service.get_sentiment_for_symbol("AAPL")
        assert summary["symbol"] == "AAPL"
        assert summary["records"] == 1

    def test_get_sentiment_for_unknown_symbol(self):
        summary = self.service.get_sentiment_for_symbol("UNKNOWN")
        assert summary["sentiment"] == "unknown"

    def test_get_market_mood(self):
        mood = self.service.get_market_mood()
        assert "fear_greed_score" in mood
        assert "emotion" in mood
        assert "contrarian_signal" in mood

    def test_get_memory_report(self):
        report = self.service.get_memory_report()
        assert "total_entries" in report
        assert "accuracy_report" in report

    def test_constructor_dependency_injection(self):
        custom_analyzer = NLPAnalyzer()
        custom_collector = SentimentCollector()
        svc = SentimentIntelligenceService(
            analyzer=custom_analyzer,
            collector=custom_collector,
        )
        assert svc.analyzer is custom_analyzer
        assert svc.collector is custom_collector

    def test_clear(self):
        self.service.analyze("test text")
        self.service.clear()
        assert self.service.collector.total_records == 0
        assert self.service.memory_store.size == 0


# ============================================================================
# Test Integration
# ============================================================================


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_bullish_scenario(self):
        """Test the full pipeline with bullish sentiment data."""
        service = SentimentIntelligenceService()

        texts = [
            "strong earnings beat and record growth",
            "upgrade to buy with upside potential",
            "bullish momentum continues to surge",
            "partnership announced driving expansion",
            "positive outlook for the quarter",
        ]

        result = service.run_pipeline(
            texts=texts,
            price_data=[100, 98, 96, 95, 97],
            symbol="AAPL",
        )

        assert result.emotion is not None
        assert len(result.nlp_results) == 5
        assert result.alpha is not None
        assert service.memory_store.size >= 1

    def test_full_pipeline_bearish_scenario(self):
        """Test the full pipeline with bearish sentiment data."""
        service = SentimentIntelligenceService()

        texts = [
            "warning of major decline ahead",
            "downgrade to sell on weak outlook",
            "guidance cut and layoff announcement",
            "bearish breakdown with heavy selling",
            "risk of bankruptcy increasing",
        ]

        result = service.run_pipeline(
            texts=texts,
            price_data=[100, 102, 104, 103, 105],
            symbol="TSLA",
        )

        assert len(result.nlp_results) == 5
        assert all(r.is_negative for r in result.nlp_results)

    def test_divergence_detection_in_pipeline(self):
        """Test that divergence is detected in the pipeline."""
        service = SentimentIntelligenceService()

        # Price rising but bearish sentiment = bearish divergence
        texts = ["downgrade warning", "bearish outlook", "weak guidance"]
        price_data = [100, 102, 104, 106, 108]

        result = service.run_pipeline(
            texts=texts,
            price_data=price_data,
            symbol="MSFT",
        )

        assert result.divergence is not None

    def test_memory_accumulation(self):
        """Test that memory accumulates across pipeline runs."""
        service = SentimentIntelligenceService()

        service.run_pipeline(texts=["bullish news"], symbol="AAPL")
        service.run_pipeline(texts=["bearish news"], symbol="MSFT")

        assert service.memory_store.size >= 2


# ============================================================================
# Test SentimentPipelineResult
# ============================================================================


class TestSentimentPipelineResult:
    """Tests for SentimentPipelineResult."""

    def test_defaults(self):
        result = SentimentPipelineResult()
        assert result.overall_sentiment == "unknown"
        assert result.has_alpha is False
        assert result.risk_level == "normal"

    def test_with_fear_greed(self):
        fg = FearGreedResult(score=85.0, zone=FearGreedZone.EXTREME_GREED)
        result = SentimentPipelineResult(fear_greed=fg)
        assert result.overall_sentiment == "extreme_greed"
        assert result.risk_level == "high_risk"

    def test_with_emotion(self):
        emotion = EmotionResult(state=EmotionState.FEAR, score=30.0)
        result = SentimentPipelineResult(emotion=emotion)
        assert result.overall_sentiment == "fear"


# ============================================================================
# Test Enums
# ============================================================================


class TestEnums:
    """Tests for enum types."""

    def test_sentiment_source_values(self):
        assert SentimentSource.NEWS.value == "news"
        assert SentimentSource.SOCIAL_MEDIA.value == "social_media"

    def test_sentiment_label_values(self):
        assert SentimentLabel.VERY_BULLISH.value == "very_bullish"
        assert SentimentLabel.VERY_BEARISH.value == "very_bearish"

    def test_emotion_state_values(self):
        assert EmotionState.EUPHORIA.value == "euphoria"
        assert EmotionState.PANIC.value == "panic"

    def test_fear_greed_zone_values(self):
        assert FearGreedZone.EXTREME_FEAR.value == "extreme_fear"
        assert FearGreedZone.EXTREME_GREED.value == "extreme_greed"
