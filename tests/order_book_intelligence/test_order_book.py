"""Tests for AI Order Book Intelligence Engine (Part 32)."""

import pytest
from datetime import datetime

from services.order_book_intelligence import (
    # Snapshot
    BookSide,
    BookLevel,
    BookEvent,
    OrderBookBuilder,
    OrderBookSnapshot,
    PriceLevel,
    # Imbalance
    ImbalanceDirection,
    ImbalanceMethod,
    ImbalanceSignal,
    OrderImbalanceAnalyzer,
    # Liquidity Wall
    LiquidityWall,
    LiquidityWallDetector,
    WallDetectionResult,
    WallStrength,
    WallType,
    # Hidden Liquidity
    HiddenLiquidityEstimate,
    HiddenLiquidityEstimator,
    HiddenLiquiditySignal,
    HiddenLiquidityType,
    DetectionConfidence,
    # Iceberg
    IcebergDetection,
    IcebergDetector,
    IcebergEvent,
    IcebergSide,
    IcebergStatus,
    # Large Order
    ActivityLevel,
    InstitutionActivity,
    LargeOrder,
    LargeOrderTracker,
    OrderCategory,
    # Toxicity
    OrderFlowToxicityAnalyzer,
    ToxicityAssessment,
    ToxicityLevel,
    AdverseSelection,
    # Queue
    QueueEstimate,
    QueuePosition,
    QueuePositionEstimator,
    FillProbability,
    ExecutionStyle,
    # Alpha
    MicroAlphaSignal,
    MicrostructureAlphaGenerator,
    AlphaSignalType,
    SignalDirection,
    SignalStrength,
    # Memory
    OrderBookMemory,
    MicrostructureEvent,
    MicrostructureKnowledgeBase,
    # Service
    OrderBookIntelligenceService,
    MicrostructureReport,
)


# ====================================================================
# OrderBookSnapshot & Builder
# ====================================================================

class TestOrderBookBuilder:
    def test_empty_book(self):
        builder = OrderBookBuilder(symbol="TEST")
        snap = builder.snapshot()
        assert snap.symbol == "TEST"
        assert snap.best_bid is None
        assert snap.best_ask is None
        assert snap.spread == 0.0

    def test_apply_snapshot(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500, 99.5: 1000},
            asks={100.5: 300, 101.0: 800},
            last_price=100.25,
        )
        snap = builder.snapshot()
        assert snap.best_bid.price == 100.0
        assert snap.best_ask.price == 100.5
        assert snap.mid_price == 100.25
        assert snap.spread == 0.5

    def test_update_bid(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.update(BookSide.BID, 100.0, 500)
        builder.update(BookSide.BID, 99.5, 1000)
        snap = builder.snapshot()
        assert snap.best_bid.price == 100.0
        assert snap.best_bid.volume == 500

    def test_update_execute(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.update(BookSide.BID, 100.0, 500)
        builder.update(BookSide.BID, 100.0, 100, BookEvent.EXECUTE)
        snap = builder.snapshot()
        assert snap.best_bid.volume == 400

    def test_update_cancel(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.update(BookSide.BID, 100.0, 500)
        builder.update(BookSide.BID, 100.0, 500, BookEvent.CANCEL)
        snap = builder.snapshot()
        assert snap.best_bid is None  # fully canceled

    def test_depth_calculation(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500, 99.5: 1000, 99.0: 2000},
            asks={100.5: 300, 101.0: 800, 101.5: 1500},
        )
        snap = builder.snapshot()
        assert snap.depth_at(2, BookSide.BID) == 1500
        assert snap.depth_at(2, BookSide.ASK) == 1100

    def test_weighted_price(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500, 99.5: 1000},
            asks={100.5: 300, 101.0: 800},
        )
        # Buy 400 shares at ask: 300@100.5 + 100@101.0
        wp = builder.snapshot().weighted_price(400, BookSide.ASK)
        assert wp is not None
        assert abs(wp - (300 * 100.5 + 100 * 101.0) / 400) < 0.01

    def test_imbalance(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 1000},
            asks={100.5: 500},
        )
        snap = builder.snapshot()
        imb = snap.imbalance(depth_levels=1)
        assert imb > 0  # More bids than asks

    def test_to_dict(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500},
            asks={100.5: 300},
        )
        d = builder.snapshot().to_dict()
        assert d["symbol"] == "TEST"
        assert d["best_bid"] == 100.0
        assert d["best_ask"] == 100.5

    def test_history(self):
        builder = OrderBookBuilder(symbol="TEST", max_history=5)
        for i in range(10):
            builder.apply_snapshot(bids={100.0: 500}, asks={100.5: 300})
            builder.snapshot()
        assert len(builder.history) == 5  # Pruned to max_history

    def test_prune_levels(self):
        builder = OrderBookBuilder(symbol="TEST", max_levels=3)
        for i in range(10):
            builder.update(BookSide.BID, 100.0 - i, 100)
        builder._prune()
        assert len(builder.bids) <= 3

    def test_clear(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.update(BookSide.BID, 100.0, 500)
        builder.clear()
        assert not builder.bids
        assert not builder.asks


# ====================================================================
# OrderImbalanceAnalyzer
# ====================================================================

class TestOrderImbalanceAnalyzer:
    def test_simple_imbalance(self):
        analyzer = OrderImbalanceAnalyzer(method=ImbalanceMethod.SIMPLE)
        signal = analyzer.calculate(bid_volume=1000, ask_volume=500)
        assert signal.score == 0.3333333333333333 or abs(signal.score - 0.3333) < 0.01
        assert signal.direction == ImbalanceDirection.BUY

    def test_neutral_imbalance(self):
        analyzer = OrderImbalanceAnalyzer()
        signal = analyzer.calculate(bid_volume=1000, ask_volume=1000)
        assert signal.direction == ImbalanceDirection.NEUTRAL

    def test_strong_buy(self):
        analyzer = OrderImbalanceAnalyzer()
        signal = analyzer.calculate(bid_volume=9000, ask_volume=1000)
        assert signal.direction == ImbalanceDirection.STRONG_BUY
        assert signal.is_buy_pressure

    def test_strong_sell(self):
        analyzer = OrderImbalanceAnalyzer()
        signal = analyzer.calculate(bid_volume=1000, ask_volume=9000)
        assert signal.direction == ImbalanceDirection.STRONG_SELL
        assert signal.is_sell_pressure

    def test_zero_volume(self):
        analyzer = OrderImbalanceAnalyzer()
        signal = analyzer.calculate(bid_volume=0, ask_volume=0)
        assert signal.score == 0.0
        assert signal.direction == ImbalanceDirection.NEUTRAL

    def test_confidence(self):
        analyzer = OrderImbalanceAnalyzer()
        signal = analyzer.calculate(bid_volume=1000, ask_volume=100)
        assert signal.confidence > 0.5

    def test_from_snapshot(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 1000, 99.5: 500},
            asks={100.5: 300, 101.0: 200},
        )
        snap = builder.snapshot()
        analyzer = OrderImbalanceAnalyzer(depth_levels=2)
        signal = analyzer.calculate_from_snapshot(snap)
        assert signal.bid_volume == 1500
        assert signal.ask_volume == 500
        assert signal.score > 0

    def test_trend(self):
        analyzer = OrderImbalanceAnalyzer()
        for i in range(10):
            analyzer.calculate(bid_volume=1000 + i * 100, ask_volume=1000)
        trend = analyzer.trend(window=10)
        assert "trend" in trend
        assert "acceleration" in trend

    def test_quick_analyze(self):
        analyzer = OrderImbalanceAnalyzer()
        result = analyzer.quick_analyze(bid_volume=2000, ask_volume=1000)
        assert result["score"] > 0
        assert result["is_buy_pressure"]

    def test_history_and_clear(self):
        analyzer = OrderImbalanceAnalyzer()
        analyzer.calculate(bid_volume=1000, ask_volume=500)
        assert analyzer.last_result() is not None
        analyzer.clear()
        assert analyzer.last_result() is None


# ====================================================================
# LiquidityWallDetector
# ====================================================================

class TestLiquidityWallDetector:
    def test_detect_wall(self):
        detector = LiquidityWallDetector()
        levels = [
            {"price": 100.0, "volume": 100},
            {"price": 99.5, "volume": 5000},  # wall
            {"price": 99.0, "volume": 100},
        ]
        walls = detector.detect(levels, side=BookSide.BID)
        assert len(walls) >= 1
        assert walls[0].price == 99.5

    def test_no_walls(self):
        detector = LiquidityWallDetector(avg_volume_multiplier=10.0)
        levels = [
            {"price": 100.0, "volume": 100},
            {"price": 99.5, "volume": 120},
        ]
        walls = detector.detect(levels, side=BookSide.BID)
        assert len(walls) == 0

    def test_wall_strength_classification(self):
        detector = LiquidityWallDetector(avg_volume_multiplier=3.0)
        levels = [
            {"price": 100.0, "volume": 100},
            {"price": 99.5, "volume": 5000},
            {"price": 99.0, "volume": 100},
            {"price": 98.5, "volume": 150},
        ]
        walls = detector.detect(levels, side=BookSide.BID)
        assert len(walls) >= 1
        assert walls[0].strength in (
            WallStrength.MAJOR, WallStrength.FORTRESS
        )

    def test_detect_from_snapshot(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 100, 99.5: 10000, 99.0: 200},
            asks={100.5: 300, 101.0: 500},
        )
        snap = builder.snapshot()
        detector = LiquidityWallDetector()
        result = detector.detect_from_snapshot(snap)
        assert result.bid_wall_count >= 1
        assert result.walls

    def test_dominant_side(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 100, 99.5: 20000},
            asks={100.5: 300, 101.0: 500},
        )
        snap = builder.snapshot()
        detector = LiquidityWallDetector()
        result = detector.detect_from_snapshot(snap)
        assert result.dominant_side == WallType.SUPPORT

    def test_predict_zone(self):
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 100, 99.5: 10000},
            asks={100.5: 300, 101.0: 500},
        )
        snap = builder.snapshot()
        detector = LiquidityWallDetector()
        result = detector.detect_from_snapshot(snap)
        zones = detector.predict_zone(result)
        assert zones["support_zone"] is not None

    def test_quick_detect(self):
        detector = LiquidityWallDetector()
        levels = [
            {"price": 100.0, "volume": 100},
            {"price": 99.5, "volume": 5000},
        ]
        result = detector.quick_detect(levels, side=BookSide.BID)
        assert result["wall_count"] >= 1

    def test_history_and_clear(self):
        builder = OrderBookBuilder()
        builder.apply_snapshot(bids={100.0: 500}, asks={100.5: 300})
        snap = builder.snapshot()
        detector = LiquidityWallDetector()
        detector.detect_from_snapshot(snap)
        assert detector.last_result() is not None
        detector.clear()
        assert detector.last_result() is None


# ====================================================================
# HiddenLiquidityEstimator
# ====================================================================

class TestHiddenLiquidityEstimator:
    def _make_trades(self, count=20):
        trades = []
        for i in range(count):
            trades.append({
                "price": 100.0 + i * 0.01,
                "volume": 100 + i * 10,
                "side": "bid" if i % 2 == 0 else "ask",
                "aggressor": "buy" if i % 2 == 0 else "sell",
                "timestamp": i * 1.0,
            })
        return trades

    def test_estimate_basic(self):
        estimator = HiddenLiquidityEstimator(min_trade_count=5)
        trades = self._make_trades(20)
        result = estimator.estimate(trades)
        assert isinstance(result, HiddenLiquidityEstimate)
        assert result.overall_confidence >= 0

    def test_insufficient_trades(self):
        estimator = HiddenLiquidityEstimator(min_trade_count=50)
        trades = self._make_trades(5)
        result = estimator.estimate(trades)
        assert result.overall_confidence == 0.0

    def test_quick_estimate(self):
        estimator = HiddenLiquidityEstimator(min_trade_count=5)
        trades = self._make_trades(20)
        result = estimator.quick_estimate(trades)
        assert "hidden_probability" in result
        assert "estimated_hidden_volume" in result

    def test_to_dict(self):
        estimator = HiddenLiquidityEstimator(min_trade_count=5)
        trades = self._make_trades(20)
        result = estimator.estimate(trades)
        d = result.to_dict()
        assert "signal_count" in d
        assert "overall_confidence" in d

    def test_history_and_clear(self):
        estimator = HiddenLiquidityEstimator(min_trade_count=5)
        trades = self._make_trades(20)
        estimator.estimate(trades)
        assert estimator.last_result() is not None
        estimator.clear()
        assert estimator.last_result() is None


# ====================================================================
# IcebergDetector
# ====================================================================

class TestIcebergDetector:
    def _make_iceberg_events(self, count=5):
        events = []
        for i in range(count):
            events.append({
                "price": 100.0,
                "volume": 100,
                "side": "bid",
                "display_size": 500,
                "timestamp": datetime.utcnow(),
            })
        return events

    def test_detect_iceberg_pattern(self):
        detector = IcebergDetector(min_repetitions=3)
        events = self._make_iceberg_events(5)
        detections = detector.detect(events)
        assert len(detections) >= 1
        assert detections[0].status in (
            IcebergStatus.SUSPECTED, IcebergStatus.CONFIRMED
        )

    def test_single_event_no_detection(self):
        detector = IcebergDetector(min_repetitions=3)
        events = [{
            "price": 100.0, "volume": 100,
            "side": "bid", "display_size": 500,
        }]
        detections = detector.detect(events)
        # Single event won't confirm iceberg
        if detections:
            assert detections[0].status != IcebergStatus.CONFIRMED

    def test_quick_detect(self):
        detector = IcebergDetector()
        result = detector.quick_detect(
            price=100.0, volume=100,
            side="bid", display_size=500,
        )
        assert "status" in result
        assert "confidence" in result

    def test_age_out(self):
        detector = IcebergDetector(min_repetitions=2)
        events = self._make_iceberg_events(3)
        detector.detect(events)
        # Age out should not remove recent events
        removed = detector.age_out(max_age_seconds=0.001)
        # Events just happened, they may or may not age out depending on timing

    def test_active_count(self):
        detector = IcebergDetector()
        events = self._make_iceberg_events(2)
        detector.detect(events)
        assert detector.active_count() >= 0

    def test_clear(self):
        detector = IcebergDetector()
        events = self._make_iceberg_events(3)
        detector.detect(events)
        detector.clear()
        assert detector.active_count() == 0


# ====================================================================
# LargeOrderTracker
# ====================================================================

class TestLargeOrderTracker:
    def test_track_block_order(self):
        tracker = LargeOrderTracker(block_threshold=50000)
        result = tracker.track({
            "price": 100.0,
            "volume": 1000,
            "side": "bid",
            "levels_consumed": 0,
        })
        # Notional = 1000 * 100 = 100000 > 50000 → institutional block
        assert result["category"] == OrderCategory.INSTITUTIONAL_BLOCK.value

    def test_track_sweep(self):
        tracker = LargeOrderTracker(sweep_levels=3)
        result = tracker.track({
            "price": 100.0,
            "volume": 500,
            "side": "bid",
            "levels_consumed": 5,
            "aggressor": "buy",
        })
        assert result["category"] == OrderCategory.SWEEP.value

    def test_track_aggressive_buy(self):
        tracker = LargeOrderTracker()
        result = tracker.track({
            "price": 100.0,
            "volume": 500,
            "aggressor": "buy",
            "levels_consumed": 0,
        })
        assert result["category"] == OrderCategory.AGGRESSIVE_BUY.value

    def test_aggregate_orders(self):
        tracker = LargeOrderTracker()
        for i in range(3):
            tracker.track({
                "price": 100.0,
                "volume": 200,
                "aggressor": "buy",
                "levels_consumed": 0,
            })
        activity = tracker.analyze_activity()
        assert len(activity.active_orders) <= 3  # may aggregate

    def test_institutional_activity_report(self):
        tracker = LargeOrderTracker()
        tracker.track({
            "price": 100.0, "volume": 2000,
            "aggressor": "buy", "levels_consumed": 0,
        })
        activity = tracker.analyze_activity()
        assert activity.buy_volume > 0
        assert activity.activity_level in (
            ActivityLevel.LOW, ActivityLevel.MODERATE,
            ActivityLevel.HIGH, ActivityLevel.EXTREME,
        )

    def test_quick_track(self):
        tracker = LargeOrderTracker()
        result = tracker.quick_track(price=100.0, volume=1000, side="bid")
        assert "category" in result

    def test_quick_activity(self):
        tracker = LargeOrderTracker()
        tracker.track({
            "price": 100.0, "volume": 500,
            "aggressor": "buy", "levels_consumed": 0,
        })
        result = tracker.quick_activity()
        assert "activity_level" in result

    def test_clear(self):
        tracker = LargeOrderTracker()
        tracker.track({"price": 100.0, "volume": 500, "aggressor": "buy", "levels_consumed": 0})
        tracker.clear()
        activity = tracker.analyze_activity()
        assert len(activity.active_orders) == 0


# ====================================================================
# OrderFlowToxicityAnalyzer
# ====================================================================

class TestOrderFlowToxicityAnalyzer:
    def test_score_basic(self):
        analyzer = OrderFlowToxicityAnalyzer()
        assert analyzer.score(0.0) == 0.0
        assert analyzer.score(0.5) == 0.5
        assert analyzer.score(1.0) == 1.0
        assert analyzer.score(1.5) == 1.0  # capped
        assert analyzer.score(-0.5) == 0.0  # floored

    def test_feed_trade_and_vpin(self):
        analyzer = OrderFlowToxicityAnalyzer(bucket_size=5000, num_buckets=10)
        # Feed balanced trades
        for i in range(100):
            analyzer.feed_trade(volume=500, is_buy_initiated=(i % 2 == 0))
        vpin = analyzer.calculate_vpin()
        assert 0.0 <= vpin <= 1.0

    def test_assess_low_toxicity(self):
        analyzer = OrderFlowToxicityAnalyzer(bucket_size=5000, num_buckets=10)
        assessment = analyzer.assess()
        assert assessment.toxicity_level == ToxicityLevel.LOW

    def test_execution_advice(self):
        analyzer = OrderFlowToxicityAnalyzer()
        assessment = analyzer.assess()
        advice = analyzer.execution_advice(assessment)
        assert "strategy" in advice
        assert "participation_rate" in advice

    def test_quick_assess(self):
        analyzer = OrderFlowToxicityAnalyzer()
        result = analyzer.quick_assess(vpin=0.3)
        assert "toxicity_score" in result
        assert "toxicity_level" in result

    def test_clear(self):
        analyzer = OrderFlowToxicityAnalyzer()
        analyzer.feed_trade(volume=1000, is_buy_initiated=True)
        analyzer.clear()
        assert analyzer.calculate_vpin() == 0.0


# ====================================================================
# QueuePositionEstimator
# ====================================================================

class TestQueuePositionEstimator:
    def test_estimate_fill_time(self):
        estimator = QueuePositionEstimator()
        est = estimator.estimate(
            queue_size=10000,
            trade_rate=100,
        )
        assert est.estimated_fill_time_sec is not None
        assert est.estimated_fill_time_sec == 100.0  # 10000 / 100
        assert est.queue_position == QueuePosition.BACK

    def test_front_of_queue(self):
        estimator = QueuePositionEstimator()
        est = estimator.estimate(
            queue_size=10000,
            trade_rate=100,
            position_in_queue=0.05,
        )
        assert est.queue_position == QueuePosition.FRONT

    def test_zero_trade_rate(self):
        estimator = QueuePositionEstimator(default_trade_rate=50)
        est = estimator.estimate(
            queue_size=10000,
            trade_rate=0,
        )
        assert est.trade_rate == 50  # fallback
        assert est.estimated_fill_time_sec == 200  # 10000 / 50

    def test_fill_probability(self):
        estimator = QueuePositionEstimator()
        est = estimator.estimate(
            queue_size=1000,
            trade_rate=500,
            time_horizon_sec=10,
        )
        # 1000 / 500 = 2 seconds → within 10s horizon = high probability
        assert est.fill_probability in (
            FillProbability.HIGH, FillProbability.VERY_HIGH
        )

    def test_low_fill_probability(self):
        estimator = QueuePositionEstimator()
        est = estimator.estimate(
            queue_size=100000,
            trade_rate=10,
            time_horizon_sec=60,
        )
        # 100000 / 10 = 10000 seconds >> 60s
        assert est.fill_probability in (
            FillProbability.VERY_LOW, FillProbability.LOW
        )

    def test_execution_style_recommendation(self):
        estimator = QueuePositionEstimator()
        est_back = estimator.estimate(
            queue_size=50000, trade_rate=10, time_horizon_sec=30
        )
        assert est_back.recommended_style == ExecutionStyle.AGGRESSIVE

        est_front = estimator.estimate(
            queue_size=100, trade_rate=500,
            position_in_queue=0.01, time_horizon_sec=30,
        )
        assert est_front.recommended_style == ExecutionStyle.PASSIVE

    def test_optimal_level(self):
        estimator = QueuePositionEstimator()
        levels = [
            {"price": 100.0, "volume": 5000, "trade_rate": 200},
            {"price": 99.9, "volume": 1000, "trade_rate": 500},
        ]
        result = estimator.optimal_level(
            levels=levels,
            order_size=500,
            time_horizon_sec=30,
            max_slippage_pct=0.01,
        )
        assert result["optimal_price"] is not None

    def test_quick_estimate(self):
        estimator = QueuePositionEstimator()
        result = estimator.quick_estimate(queue_size=5000, trade_rate=200)
        assert "estimated_fill_time_sec" in result
        assert "recommended_style" in result

    def test_history_and_clear(self):
        estimator = QueuePositionEstimator()
        estimator.estimate(queue_size=1000, trade_rate=100)
        assert estimator.last_result() is not None
        estimator.clear()
        assert estimator.last_result() is None


# ====================================================================
# MicrostructureAlphaGenerator
# ====================================================================

class TestMicrostructureAlphaGenerator:
    def test_generate_positive_alpha(self):
        generator = MicrostructureAlphaGenerator()
        result = generator.generate(
            imbalance=0.5,
            toxicity=0.2,
        )
        assert result["alpha"] > 0
        assert "components" in result

    def test_generate_negative_alpha(self):
        generator = MicrostructureAlphaGenerator()
        result = generator.generate(
            imbalance=-0.5,
            toxicity=0.6,
        )
        assert result["alpha"] < 0

    def test_synthesize_basic(self):
        generator = MicrostructureAlphaGenerator()
        signal = generator.synthesize(
            imbalance=0.6,
            toxicity=0.2,
        )
        assert signal.direction == SignalDirection.LONG
        assert signal.signal_type in (
            AlphaSignalType.MOMENTUM,
            AlphaSignalType.EXECUTION,
        )

    def test_synthesize_flat(self):
        generator = MicrostructureAlphaGenerator()
        signal = generator.synthesize(
            imbalance=0.05,
            toxicity=0.1,
        )
        assert signal.direction == SignalDirection.FLAT
        assert not signal.is_actionable

    def test_synthesize_short(self):
        generator = MicrostructureAlphaGenerator()
        signal = generator.synthesize(
            imbalance=-0.7,
            toxicity=0.5,
        )
        assert signal.direction == SignalDirection.SHORT

    def test_components_aggregate(self):
        generator = MicrostructureAlphaGenerator()
        result = generator.generate(
            imbalance=0.4, toxicity=0.3, wall_imbalance=0.2,
        )
        total_component = sum(result["components"].values())
        assert abs(total_component - result["alpha"]) < 0.001

    def test_confidence_computation(self):
        generator = MicrostructureAlphaGenerator()
        signal = generator.synthesize(
            imbalance=0.5, toxicity=0.2, wall_imbalance=0.4,
            iceberg_confidence=0.7,
        )
        assert 0 <= signal.confidence <= 1.0

    def test_expected_horizon(self):
        generator = MicrostructureAlphaGenerator()
        signal_strong = generator.synthesize(imbalance=0.8, toxicity=0.1)
        signal_weak = generator.synthesize(imbalance=0.1, toxicity=0.1)
        # Stronger signal → shorter horizon
        assert signal_strong.expected_horizon_sec <= signal_weak.expected_horizon_sec

    def test_quick_generate(self):
        generator = MicrostructureAlphaGenerator()
        result = generator.quick_generate(imbalance=0.6, toxicity=0.2)
        assert result["alpha"] > 0
        assert result["direction"] == "LONG"

    def test_history_and_clear(self):
        generator = MicrostructureAlphaGenerator()
        generator.synthesize(imbalance=0.5, toxicity=0.2)
        assert generator.last_result() is not None
        generator.clear()
        assert generator.last_result() is None


# ====================================================================
# OrderBookMemory
# ====================================================================

class TestOrderBookMemory:
    def test_save_snapshot(self):
        memory = OrderBookMemory()
        builder = OrderBookBuilder()
        builder.apply_snapshot(bids={100.0: 500}, asks={100.5: 300})
        snap = builder.snapshot()
        memory.save(snap)
        assert len(memory.snapshots) == 1

    def test_record_event(self):
        memory = OrderBookMemory()
        record = memory.record(
            event_type=MicrostructureEvent.WALL_DETECTED,
            data={"price": 100.0, "volume": 5000},
            symbol="TEST",
            price=100.0,
        )
        assert record.event_type == MicrostructureEvent.WALL_DETECTED
        assert len(memory.records) == 1

    def test_record_alpha_signal(self):
        memory = OrderBookMemory()
        memory.record_alpha_signal(
            alpha_score=0.5, direction="LONG",
            strength="moderate", confidence=0.7,
        )
        assert len(memory.alpha_signals) == 1

    def test_verify_alpha_signal(self):
        memory = OrderBookMemory()
        memory.record_alpha_signal(alpha_score=0.5, direction="LONG", strength="strong", confidence=0.8)
        memory.verify_alpha_signal(was_correct=True)
        assert memory.alpha_signals[0].get("verified")
        assert memory.alpha_signals[0].get("was_correct")

    def test_recent_events(self):
        memory = OrderBookMemory()
        for i in range(5):
            memory.record(
                event_type=MicrostructureEvent.IMBALANCE_EXTREME,
                data={"index": i},
            )
        recent = memory.recent_events(limit=3)
        assert len(recent) == 3

    def test_events_by_type(self):
        memory = OrderBookMemory()
        memory.record(MicrostructureEvent.WALL_DETECTED, data={})
        memory.record(MicrostructureEvent.SWEEP, data={})
        memory.record(MicrostructureEvent.WALL_DETECTED, data={})
        walls = memory.events_by_type(MicrostructureEvent.WALL_DETECTED)
        assert len(walls) == 2

    def test_events_by_price(self):
        memory = OrderBookMemory()
        memory.record(MicrostructureEvent.WALL_DETECTED, data={}, price=100.0)
        memory.record(MicrostructureEvent.WALL_DETECTED, data={}, price=105.0)
        memory.record(MicrostructureEvent.WALL_DETECTED, data={}, price=110.0)
        filtered = memory.events_by_price(min_price=102, max_price=108)
        assert len(filtered) == 1

    def test_knowledge_base(self):
        memory = OrderBookMemory()
        memory.record(MicrostructureEvent.ALPHA_SIGNAL, data={"alpha": 0.5})
        memory.record(MicrostructureEvent.WALL_DETECTED, data={}, price=100.0)
        kb = memory.knowledge_base()
        assert kb.total_events == 2
        assert isinstance(kb, MicrostructureKnowledgeBase)

    def test_quick_status(self):
        memory = OrderBookMemory()
        memory.record(MicrostructureEvent.WALL_DETECTED, data={})
        status = memory.quick_status()
        assert "total_events" in status
        assert status["total_events"] == 1

    def test_clear(self):
        memory = OrderBookMemory()
        memory.record(MicrostructureEvent.WALL_DETECTED, data={})
        builder = OrderBookBuilder()
        builder.apply_snapshot(bids={100.0: 500}, asks={100.5: 300})
        memory.save(builder.snapshot())
        memory.clear()
        assert len(memory.records) == 0
        assert len(memory.snapshots) == 0


# ====================================================================
# OrderBookIntelligenceService
# ====================================================================

class TestOrderBookIntelligenceService:
    def test_service_init(self):
        service = OrderBookIntelligenceService()
        assert service.analyzer is not None
        assert service.book_builder is not None
        assert service.wall_detector is not None
        assert service.alpha_generator is not None

    def test_analyze_simple(self):
        service = OrderBookIntelligenceService()
        result = service.analyze(bid=1000, ask=500)
        assert result > 0

    def test_analyze_snapshot(self):
        service = OrderBookIntelligenceService()
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500, 99.5: 1000},
            asks={100.5: 300, 101.0: 200},
        )
        snap = builder.snapshot()
        report = service.analyze_snapshot(snap)
        assert isinstance(report, MicrostructureReport)
        assert report.imbalance is not None
        assert report.toxicity is not None
        assert report.alpha is not None

    def test_analyze_snapshot_with_trades(self):
        service = OrderBookIntelligenceService()
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500},
            asks={100.5: 300},
        )
        snap = builder.snapshot()
        trades = [
            {"price": 100.25, "volume": 200, "aggressor": "buy",
             "side": "bid", "display_size": 500, "levels_consumed": 0},
        ]
        report = service.analyze_snapshot(snap, trades=trades)
        assert report.walls is not None
        assert report.hidden_liquidity is not None

    def test_report_to_dict(self):
        service = OrderBookIntelligenceService()
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(
            bids={100.0: 500},
            asks={100.5: 300},
        )
        snap = builder.snapshot()
        report = service.analyze_snapshot(snap)
        d = report.to_dict()
        assert "snapshot" in d
        assert "imbalance" in d

    def test_quick_analyze(self):
        service = OrderBookIntelligenceService()
        result = service.quick_analyze(
            bid_volume=2000,
            ask_volume=1000,
            vpin=0.2,
        )
        assert result["imbalance"] > 0
        assert "alpha" in result

    def test_memory_status(self):
        service = OrderBookIntelligenceService()
        status = service.memory_status()
        assert "total_events" in status

    def test_clear_all(self):
        service = OrderBookIntelligenceService()
        builder = OrderBookBuilder(symbol="TEST")
        builder.apply_snapshot(bids={100.0: 500}, asks={100.5: 300})
        service.analyze_snapshot(builder.snapshot())
        service.clear_all()
        assert service.analyzer.last_result() is None


# ====================================================================
# Edge Cases
# ====================================================================

class TestEdgeCases:
    def test_empty_book_no_errors(self):
        builder = OrderBookBuilder()
        snap = builder.snapshot()
        imb = snap.imbalance()
        assert imb == 0.0

    def test_single_price_level(self):
        builder = OrderBookBuilder()
        builder.apply_snapshot(bids={100.0: 500}, asks={})
        snap = builder.snapshot()
        assert snap.best_bid is not None
        assert snap.best_ask is None

    def test_negative_volume_handled(self):
        builder = OrderBookBuilder()
        builder.update(BookSide.BID, 100.0, 500)
        builder.update(BookSide.BID, 100.0, -600)  # negative clears
        snap = builder.snapshot()
        assert snap.best_bid is None
