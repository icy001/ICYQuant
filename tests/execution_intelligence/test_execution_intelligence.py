"""Tests for AI Execution Intelligence Engine."""

import pytest
from services.execution_intelligence import (
    ExecutionOrder,
    OrderSide,
    OrderType,
    OrderStatus,
    ExecutionPlan,
    Slice,
    SmartRoutingEngine,
    Venue,
    SlippagePredictor,
    SlippageEstimate,
    MarketImpactModel,
    ImpactEstimate,
    ExecutionStrategyEngine,
    StrategyConfig,
    TransactionCostAnalyzer,
    TCAResult,
    ExecutionIntelligenceService,
)


# ======================================================================
# ExecutionOrder
# ======================================================================

class TestExecutionOrder:
    """Tests for the ExecutionOrder model."""

    def test_create_basic_order(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 100
        assert order.urgency == "normal"
        assert order.status == "pending"

    def test_create_sell_order(self):
        order = ExecutionOrder(symbol="AAPL", side="SELL", quantity=500,
                               urgency="high", order_type="LIMIT",
                               limit_price=150.0)
        assert order.side == "SELL"
        assert order.limit_price == 150.0
        assert order.urgency == "high"

    def test_notional_value(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=200)
        assert order.notional_value(100.0) == 20000.0
        assert order.notional_value(50.0) == 10000.0

    def test_fill_rate(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000)
        assert order.fill_rate() == 0.0
        order.filled_quantity = 500
        assert order.fill_rate() == 0.5
        order.filled_quantity = 1000
        assert order.fill_rate() == 1.0

    def test_is_complete(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        assert not order.is_complete()
        order.status = "filled"
        assert order.is_complete()
        order.status = "cancelled"
        assert order.is_complete()
        order.status = "rejected"
        assert order.is_complete()

    def test_to_dict(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100,
                               portfolio_id="PF-1", strategy_id="ST-1",
                               reason="Alpha signal")
        d = order.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["side"] == "BUY"
        assert d["quantity"] == 100
        assert d["portfolio_id"] == "PF-1"
        assert d["strategy_id"] == "ST-1"

    def test_order_with_metadata(self):
        order = ExecutionOrder(
            symbol="TSLA", side="SELL", quantity=1000,
            urgency="critical", parent_order_id="PARENT-001",
            reason="Risk reduction",
        )
        assert order.parent_order_id == "PARENT-001"
        assert order.reason == "Risk reduction"


# ======================================================================
# ExecutionPlan
# ======================================================================

class TestExecutionPlan:
    """Tests for the ExecutionPlan model."""

    def test_create_plan(self):
        plan = ExecutionPlan(
            order_id="ORD-001",
            symbol="NVDA",
            side="BUY",
            strategy="VWAP",
            duration=300,
        )
        assert plan.strategy == "VWAP"
        assert plan.duration == 300
        assert plan.total_quantity == 0

    def test_add_slice(self):
        plan = ExecutionPlan(strategy="TWAP", duration=600)
        s = plan.add_slice(100, strategy="TWAP")
        assert s.slice_id == 1
        assert s.quantity == 100
        assert plan.total_quantity == 100

    def test_add_multiple_slices(self):
        plan = ExecutionPlan(strategy="VWAP", duration=600)
        plan.add_slice(200, strategy="VWAP")
        plan.add_slice(300, strategy="VWAP")
        plan.add_slice(500, strategy="VWAP")
        assert plan.total_quantity == 1000
        assert len(plan.slices) == 3
        assert plan.slices[-1].slice_id == 3

    def test_remaining_quantity(self):
        plan = ExecutionPlan(strategy="VWAP")
        plan.add_slice(500)
        plan.add_slice(500)
        assert plan.remaining_quantity(0) == 1000
        assert plan.remaining_quantity(600) == 400
        assert plan.remaining_quantity(1000) == 0
        assert plan.remaining_quantity(1200) == 0

    def test_is_complete(self):
        plan = ExecutionPlan(strategy="VWAP")
        plan.add_slice(500)
        assert not plan.is_complete(0)
        assert plan.is_complete(500)
        assert plan.is_complete(1000)

    def test_to_dict(self):
        plan = ExecutionPlan(
            order_id="ORD-001",
            symbol="NVDA",
            side="BUY",
            strategy="VWAP",
            duration=300,
            estimated_slippage_bps=2.5,
            estimated_impact_bps=1.5,
        )
        plan.add_slice(500, strategy="VWAP")
        d = plan.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["strategy"] == "VWAP"
        assert len(d["slices"]) == 1
        assert d["total_quantity"] == 500

    def test_slice_to_dict(self):
        s = Slice(slice_id=1, quantity=100, strategy="VWAP", venue="auto")
        d = s.to_dict()
        assert d["slice_id"] == 1
        assert d["quantity"] == 100
        assert d["strategy"] == "VWAP"


# ======================================================================
# SmartRoutingEngine
# ======================================================================

class TestSmartRoutingEngine:
    """Tests for the SmartRoutingEngine."""

    def test_route_default(self):
        router = SmartRoutingEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        result = router.route(order)
        assert "venue" in result
        assert result["venue"] in ("Primary_Exchange", "best_market")

    def test_route_picks_best_venue(self):
        router = SmartRoutingEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        result = router.route(order)
        # Primary_Exchange should have the highest composite score
        assert result["venue"] == "Primary_Exchange"
        assert "composite_score" in result
        assert "reason" in result

    def test_route_large_order_splits(self):
        router = SmartRoutingEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=10000)
        result = router.route(order)
        assert "split" in result
        assert len(result["split"]) >= 1
        total_qty = sum(s["quantity"] for s in result["split"])
        assert total_qty == 10000

    def test_route_empty_venues(self):
        router = SmartRoutingEngine(venues=[])
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        result = router.route(order)
        assert result["venue"] == "best_market"
        assert result["split"] == []

    def test_list_venues(self):
        router = SmartRoutingEngine()
        venues = router.list_venues()
        assert len(venues) == 4
        assert all("name" in v for v in venues)
        assert all("composite_score" in v for v in venues)

    def test_add_venue(self):
        router = SmartRoutingEngine(venues=[])
        router.add_venue(Venue(name="Custom_Exchange", liquidity_score=0.99,
                               spread_bps=0.5, fee_bps=0.5,
                               latency_ms=0.5, market_depth=0.95))
        assert len(router.venues) == 1
        result = router.route(ExecutionOrder("TEST", "BUY", 100))
        assert result["venue"] == "Custom_Exchange"

    def test_venue_composite_score(self):
        best = Venue(name="Best", liquidity_score=1.0, spread_bps=0.0,
                     fee_bps=0.0, latency_ms=0.0, market_depth=1.0)
        worst = Venue(name="Worst", liquidity_score=0.0, spread_bps=100.0,
                      fee_bps=50.0, latency_ms=100.0, market_depth=0.0)
        assert best.composite_score() > worst.composite_score()

    def test_route_small_order_no_split(self):
        router = SmartRoutingEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        result = router.route(order)
        assert len(result.get("split", [])) == 0

    def test_venue_to_dict(self):
        v = Venue(name="Test", liquidity_score=0.8, spread_bps=1.5,
                  fee_bps=2.0, latency_ms=3.0, market_depth=0.7)
        d = v.to_dict()
        assert d["name"] == "Test"
        assert "composite_score" in d


# ======================================================================
# SlippagePredictor
# ======================================================================

class TestSlippagePredictor:
    """Tests for the SlippagePredictor."""

    def test_predict_basic(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000)
        result = predictor.predict(order)
        assert result >= 0

    def test_predict_sell_side(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="SELL", quantity=1000)
        result = predictor.predict(order)
        assert result >= 0

    def test_predict_large_order_more_slippage(self):
        predictor = SlippagePredictor()
        small = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        large = ExecutionOrder(symbol="NVDA", side="BUY", quantity=50000)
        assert predictor.predict(large) > predictor.predict(small)

    def test_predict_high_urgency_more_slippage(self):
        predictor = SlippagePredictor()
        normal = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000,
                                urgency="normal")
        critical = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000,
                                  urgency="critical")
        assert predictor.predict(critical) > predictor.predict(normal)

    def test_predict_detailed(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=5000)
        result = predictor.predict_detailed(order)
        assert result.symbol == "NVDA"
        assert result.estimated_bps >= 0
        assert "spread_cost_bps" in result.factors
        assert "volume_impact_bps" in result.factors
        assert "urgency_multiplier" in result.factors

    def test_slippage_estimate_is_significant(self):
        e = SlippageEstimate(symbol="NVDA", estimated_bps=5.0)
        assert e.is_significant()
        assert not e.is_significant(threshold_bps=10.0)

    def test_slippage_estimate_to_dict(self):
        e = SlippageEstimate(symbol="NVDA", estimated_bps=3.0,
                             confidence=0.8,
                             factors={"spread_cost_bps": 0.5})
        d = e.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["estimated_bps"] == 3.0
        assert d["confidence"] == 0.8

    def test_expected_fill_price_buy(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000)
        fill = predictor.expected_fill_price(order, 100.0)
        assert fill >= 100.0  # BUY: should pay at or above mid

    def test_expected_fill_price_sell(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="SELL", quantity=1000)
        fill = predictor.expected_fill_price(order, 100.0)
        assert fill <= 100.0  # SELL: should receive at or below mid

    def test_predict_with_custom_spread(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        default = predictor.predict(order)
        wide_spread = predictor.predict(order, spread_bps=10.0)
        assert wide_spread > default


# ======================================================================
# MarketImpactModel
# ======================================================================

class TestMarketImpactModel:
    """Tests for the MarketImpactModel."""

    def test_estimate_basic(self):
        model = MarketImpactModel()
        result = model.estimate(10000)
        assert result >= 0

    def test_estimate_larger_quantity_more_impact(self):
        model = MarketImpactModel()
        small = model.estimate(1000)
        large = model.estimate(1000000)
        assert large > small

    def test_estimate_detailed(self):
        model = MarketImpactModel()
        result = model.estimate_detailed(50000, avg_daily_volume=1_000_000,
                                         price=100.0)
        assert result.symbol == ""
        assert result.impact_bps >= 0
        assert result.temporary_impact_bps >= 0
        assert result.permanent_impact_bps >= 0
        assert result.recommendation in ("single", "split", "algorithmic")

    def test_estimate_small_order_single_rec(self):
        model = MarketImpactModel(eta=0.001, gamma=0.001)
        result = model.estimate_detailed(100, avg_daily_volume=10_000_000,
                                         price=100.0)
        assert result.recommendation == "single"

    def test_estimate_large_order_split_rec(self):
        model = MarketImpactModel()
        result = model.estimate_detailed(100000, avg_daily_volume=1_000_000,
                                         price=100.0)
        assert result.recommendation in ("split", "algorithmic")

    def test_impact_estimate_is_high_impact(self):
        e = ImpactEstimate(symbol="NVDA", impact_bps=10.0,
                           temporary_impact_bps=6.0, permanent_impact_bps=4.0)
        assert e.is_high_impact()
        assert not e.is_high_impact(threshold_bps=20.0)
        assert e.total_bps() == 10.0

    def test_impact_estimate_to_dict(self):
        e = ImpactEstimate(symbol="NVDA", impact_bps=5.0,
                           temporary_impact_bps=3.0, permanent_impact_bps=2.0,
                           recommendation="split")
        d = e.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["total_bps"] == 5.0
        assert d["recommendation"] == "split"

    def test_estimate_for_order(self):
        model = MarketImpactModel()
        order = ExecutionOrder(symbol="AAPL", side="BUY", quantity=50000)
        result = model.estimate_for_order(order)
        assert result.symbol == "AAPL"

    def test_optimal_slice_count(self):
        model = MarketImpactModel()
        # Very large order should recommend many slices
        slices = model.optimal_slice_count(500_000, avg_daily_volume=1_000_000)
        assert slices >= 1
        assert slices <= 50

    def test_optimal_slice_count_small_order(self):
        model = MarketImpactModel(eta=0.001, gamma=0.001)
        slices = model.optimal_slice_count(100, avg_daily_volume=10_000_000)
        assert slices == 1

    def test_cost_savings(self):
        model = MarketImpactModel()
        result = model.cost_savings(100000, avg_daily_volume=1_000_000,
                                    price=100.0)
        assert "single_impact_bps" in result
        assert "slices_recommended" in result
        assert "estimated_savings_bps" in result


# ======================================================================
# ExecutionStrategyEngine
# ======================================================================

class TestExecutionStrategyEngine:
    """Tests for the ExecutionStrategyEngine."""

    def test_choose_critical_urgency(self):
        engine = ExecutionStrategyEngine()
        assert engine.choose("critical") == "market"

    def test_choose_high_urgency_small(self):
        engine = ExecutionStrategyEngine()
        assert engine.choose("high", quantity=100, avg_daily_volume=1_000_000) == "market"

    def test_choose_high_urgency_large(self):
        engine = ExecutionStrategyEngine()
        assert engine.choose("high", quantity=100000, avg_daily_volume=1_000_000) == "POV"

    def test_choose_low_urgency(self):
        engine = ExecutionStrategyEngine()
        assert engine.choose("low") == "TWAP"

    def test_choose_normal_small(self):
        engine = ExecutionStrategyEngine()
        result = engine.choose("normal", quantity=100, avg_daily_volume=1_000_000)
        assert result == "market"

    def test_choose_normal_medium(self):
        engine = ExecutionStrategyEngine()
        result = engine.choose("normal", quantity=50000, avg_daily_volume=1_000_000)
        assert result == "VWAP"

    def test_choose_normal_large(self):
        engine = ExecutionStrategyEngine()
        result = engine.choose("normal", quantity=200000, avg_daily_volume=1_000_000)
        assert result == "POV"

    def test_choose_normal_very_large(self):
        engine = ExecutionStrategyEngine()
        result = engine.choose("normal", quantity=300000, avg_daily_volume=1_000_000)
        assert result == "adaptive"

    def test_choose_for_order(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=50000,
                               urgency="normal")
        assert engine.choose_for_order(order) == "VWAP"

    def test_create_plan_market(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000,
                               urgency="critical")
        plan = engine.create_plan(order, avg_daily_volume=1_000_000)
        assert plan.strategy == "market"
        assert plan.total_quantity == 1000
        assert len(plan.slices) == 1

    def test_create_plan_vwap(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=50000,
                               urgency="normal")
        plan = engine.create_plan(order, avg_daily_volume=1_000_000)
        assert plan.strategy == "VWAP"
        assert plan.total_quantity == 50000
        assert len(plan.slices) > 1

    def test_create_plan_with_custom_strategy(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="SELL", quantity=10000,
                               urgency="normal")
        plan = engine.create_plan(order, strategy="TWAP", duration=600, slices=10)
        assert plan.strategy == "TWAP"
        assert plan.duration == 600
        assert len(plan.slices) == 10

    def test_create_plan_slice_quantities_sum(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=1000,
                               urgency="normal")
        plan = engine.create_plan(order, strategy="TWAP", slices=10)
        total = sum(s.quantity for s in plan.slices)
        assert total == 1000

    def test_list_strategies(self):
        engine = ExecutionStrategyEngine()
        strategies = engine.list_strategies()
        assert len(strategies) >= 4
        names = [s["name"] for s in strategies]
        assert "market" in names
        assert "VWAP" in names
        assert "TWAP" in names
        assert "POV" in names
        assert "adaptive" in names

    def test_get_strategy_config(self):
        engine = ExecutionStrategyEngine()
        cfg = engine.get_strategy_config("VWAP")
        assert cfg is not None
        assert cfg.name == "VWAP"
        assert cfg.min_duration_seconds == 300

    def test_get_strategy_config_unknown(self):
        engine = ExecutionStrategyEngine()
        assert engine.get_strategy_config("nonexistent") is None


# ======================================================================
# TransactionCostAnalyzer
# ======================================================================

class TestTransactionCostAnalyzer:
    """Tests for the TransactionCostAnalyzer."""

    def test_analyze_buy_slippage(self):
        tca = TransactionCostAnalyzer()
        # BUY: actual > expected = cost
        cost = tca.analyze(100.0, 100.50, symbol="NVDA", side="BUY",
                           quantity=1000)
        assert cost > 0

    def test_analyze_sell_slippage(self):
        tca = TransactionCostAnalyzer()
        # SELL: actual < expected = cost
        cost = tca.analyze(100.0, 99.50, symbol="NVDA", side="SELL",
                           quantity=1000)
        assert cost > 0

    def test_analyze_perfect_execution(self):
        tca = TransactionCostAnalyzer()
        cost = tca.analyze(100.0, 100.0, symbol="NVDA", side="BUY",
                           quantity=1000)
        assert cost == 0.0

    def test_analyze_detailed(self):
        tca = TransactionCostAnalyzer()
        result = tca.analyze_detailed(
            expected=100.0, actual=100.30,
            symbol="NVDA", side="BUY", quantity=1000,
            arrival_price=100.10,
        )
        assert result.symbol == "NVDA"
        assert result.total_cost_bps > 0
        assert result.execution_quality in ("excellent", "good", "fair", "poor")
        assert result.spread_cost_bps >= 0
        assert result.notional_value > 0

    def test_analyze_detailed_invalid_price(self):
        tca = TransactionCostAnalyzer()
        result = tca.analyze_detailed(expected=0.0, actual=100.0)
        assert result.total_cost_bps == 0.0
        assert result.notes == "Invalid expected price."

    def test_analyze_batch(self):
        tca = TransactionCostAnalyzer()
        trades = [
            {"expected": 100.0, "actual": 100.20, "symbol": "A",
             "side": "BUY", "quantity": 1000},
            {"expected": 50.0, "actual": 49.80, "symbol": "B",
             "side": "SELL", "quantity": 500},
        ]
        results = tca.analyze_batch(trades)
        assert len(results) == 2
        assert all(isinstance(r, TCAResult) for r in results)

    def test_summary(self):
        tca = TransactionCostAnalyzer()
        results = [
            tca.analyze_detailed(100.0, 100.10, symbol="A", side="BUY", quantity=100),
            tca.analyze_detailed(50.0, 50.05, symbol="B", side="BUY", quantity=200),
        ]
        summary = tca.summary(results)
        assert summary["total_trades"] == 2
        assert "avg_cost_bps" in summary
        assert "quality_distribution" in summary
        assert "best_trade" in summary
        assert "worst_trade" in summary

    def test_summary_empty(self):
        tca = TransactionCostAnalyzer()
        summary = tca.summary([])
        assert summary["total_trades"] == 0
        assert summary["avg_cost_bps"] == 0.0

    def test_execution_quality_ratings(self):
        tca = TransactionCostAnalyzer()
        assert tca.analyze_detailed(100.0, 100.005, side="BUY",
                                    quantity=100).execution_quality == "excellent"
        assert tca.analyze_detailed(100.0, 100.03, side="BUY",
                                    quantity=100).execution_quality == "good"
        assert tca.analyze_detailed(100.0, 100.10, side="BUY",
                                    quantity=100).execution_quality == "fair"
        assert tca.analyze_detailed(100.0, 100.30, side="BUY",
                                    quantity=100).execution_quality == "poor"

    def test_timing_cost(self):
        tca = TransactionCostAnalyzer()
        # arrival > expected for BUY = adverse timing
        result = tca.analyze_detailed(
            expected=100.0, actual=100.50,
            side="BUY", arrival_price=100.20,
        )
        assert result.timing_cost_bps > 0


# ======================================================================
# ExecutionIntelligenceService
# ======================================================================

class TestExecutionIntelligenceService:
    """Integration tests for the ExecutionIntelligenceService."""

    def test_create_service(self):
        service = ExecutionIntelligenceService()
        assert service is not None

    def test_execute_plan_legacy(self):
        router = SmartRoutingEngine()
        service = ExecutionIntelligenceService(router=router)
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=100)
        result = service.execute_plan(order)
        assert result["venue"] == "best_market" or "Exchange" in result["venue"]

    def test_create_order(self):
        service = ExecutionIntelligenceService()
        order = service.create_order(
            symbol="NVDA", side="BUY", quantity=1000,
            urgency="high", portfolio_id="PF-1", reason="Test",
        )
        assert order.symbol == "NVDA"
        assert order.side == "BUY"
        assert order.quantity == 1000
        assert order.urgency == "high"

    def test_plan_order(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 5000, "normal")
        plan = service.plan_order(order)
        assert plan.symbol == "NVDA"
        assert plan.total_quantity == 5000
        assert len(plan.slices) > 0

    def test_route(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 100)
        result = service.route(order)
        assert "venue" in result

    def test_list_venues(self):
        service = ExecutionIntelligenceService()
        venues = service.list_venues()
        assert len(venues) == 4

    def test_add_venue(self):
        service = ExecutionIntelligenceService()
        service.add_venue("Test_Exchange")
        venues = service.list_venues()
        assert len(venues) == 5

    def test_predict_slippage(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 10000)
        slippage = service.predict_slippage(order)
        assert slippage >= 0

    def test_predict_slippage_detailed(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 5000, "high")
        result = service.predict_slippage_detailed(order)
        assert result.symbol == "NVDA"
        assert "factors" in result.to_dict()

    def test_expected_fill_price(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 1000)
        fill = service.expected_fill_price(order, 100.0)
        assert fill >= 100.0

    def test_estimate_impact(self):
        service = ExecutionIntelligenceService()
        impact = service.estimate_impact(50000)
        assert impact >= 0

    def test_estimate_impact_detailed(self):
        service = ExecutionIntelligenceService()
        result = service.estimate_impact_detailed(50000)
        assert "recommendation" in result.to_dict()

    def test_estimate_impact_for_order(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("AAPL", "SELL", 100000)
        result = service.estimate_impact_for_order(order)
        assert result.symbol == "AAPL"

    def test_optimal_slices(self):
        service = ExecutionIntelligenceService()
        slices = service.optimal_slices(500_000, avg_daily_volume=1_000_000)
        assert slices >= 1

    def test_cost_savings(self):
        service = ExecutionIntelligenceService()
        result = service.cost_savings(100000)
        assert "single_impact_bps" in result

    def test_choose_strategy(self):
        service = ExecutionIntelligenceService()
        assert service.choose_strategy("critical") == "market"
        assert service.choose_strategy("low") == "TWAP"

    def test_choose_strategy_for_order(self):
        service = ExecutionIntelligenceService()
        order = service.create_order("NVDA", "BUY", 50000, "normal")
        strategy = service.choose_strategy_for_order(order)
        assert strategy == "VWAP"

    def test_list_strategies(self):
        service = ExecutionIntelligenceService()
        strategies = service.list_strategies()
        assert len(strategies) >= 5

    def test_analyze_cost(self):
        service = ExecutionIntelligenceService()
        cost = service.analyze_cost(100.0, 100.50, "NVDA", "BUY", 1000)
        assert cost > 0

    def test_analyze_cost_detailed(self):
        service = ExecutionIntelligenceService()
        result = service.analyze_cost_detailed(
            100.0, 100.20, "NVDA", "BUY", 1000, arrival_price=100.10,
        )
        assert result.symbol == "NVDA"
        assert result.execution_quality in ("excellent", "good", "fair", "poor")

    def test_analyze_batch(self):
        service = ExecutionIntelligenceService()
        trades = [
            {"expected": 100.0, "actual": 100.10, "symbol": "A",
             "side": "BUY", "quantity": 100},
        ]
        results = service.analyze_batch(trades)
        assert len(results) == 1

    def test_tca_summary(self):
        service = ExecutionIntelligenceService()
        results = [
            service.analyze_cost_detailed(100.0, 100.10, "A", "BUY", 100),
            service.analyze_cost_detailed(50.0, 50.05, "B", "BUY", 200),
        ]
        summary = service.tca_summary(results)
        assert summary["total_trades"] == 2

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    def test_execute_full_pipeline(self):
        service = ExecutionIntelligenceService()
        result = service.execute(
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            urgency="normal",
            mid_price=100.0,
            portfolio_id="PF-1",
            strategy_id="ST-Alpha",
            reason="Alpha signal: momentum breakout",
        )
        assert "order" in result
        assert "strategy" in result
        assert "plan" in result
        assert "routing" in result
        assert "slippage" in result
        assert "impact" in result
        assert "expected_fill_price" in result

        assert result["order"]["symbol"] == "NVDA"
        assert result["strategy"] in ("market", "VWAP", "TWAP", "POV", "adaptive")
        assert result["routing"]["venue"] is not None

    def test_execute_high_urgency(self):
        service = ExecutionIntelligenceService()
        result = service.execute(
            symbol="TSLA", side="SELL", quantity=5000,
            urgency="critical", mid_price=200.0,
        )
        assert result["strategy"] == "market"

    def test_execute_large_order(self):
        service = ExecutionIntelligenceService()
        result = service.execute(
            symbol="AAPL", side="BUY", quantity=500000,
            urgency="normal", mid_price=150.0,
        )
        # Large order should use adaptive or POV
        assert result["strategy"] in ("adaptive", "POV")

    def test_execute_small_order(self):
        service = ExecutionIntelligenceService()
        result = service.execute(
            symbol="MSFT", side="BUY", quantity=100,
            urgency="normal", mid_price=300.0,
        )
        # Very small order should use market
        assert result["strategy"] == "market"


# ======================================================================
# End-to-End Workflow
# ======================================================================

class TestEndToEndWorkflow:
    """End-to-end execution intelligence workflow tests."""

    def test_complete_workflow(self):
        """Simulate a complete execution workflow:
        Portfolio decision → Order → Plan → Route → Predict → Execute → Analyze
        """
        service = ExecutionIntelligenceService()

        # 1. Create order from portfolio decision
        order = service.create_order(
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            urgency="normal",
            portfolio_id="PF-Growth",
            strategy_id="ST-Momentum",
            reason="Portfolio rebalance: increase NVDA by 2%",
        )
        assert order.symbol == "NVDA"

        # 2. Generate execution plan
        plan = service.plan_order(order)
        assert plan.total_quantity == 10000
        assert len(plan.slices) >= 1

        # 3. Route to best venue
        routing = service.route(order)
        assert "venue" in routing

        # 4. Predict slippage
        slippage = service.predict_slippage_detailed(order)
        assert slippage.estimated_bps >= 0

        # 5. Estimate market impact
        impact = service.estimate_impact_for_order(order)
        assert impact.impact_bps >= 0

        # 6. Expected fill price
        fill = service.expected_fill_price(order, mid_price=100.0)
        assert fill >= 100.0

        # 7. Post-trade TCA (simulated actual = expected + some slippage)
        actual_price = fill + 0.10
        tca_result = service.analyze_cost_detailed(
            expected=100.0, actual=actual_price,
            symbol="NVDA", side="BUY", quantity=10000,
        )
        assert tca_result.total_cost_bps > 0
        assert tca_result.execution_quality is not None

    def test_dual_order_workflow(self):
        """Test simultaneous buy and sell orders (rebalance scenario)."""
        service = ExecutionIntelligenceService()

        buy_result = service.execute(
            symbol="NVDA", side="BUY", quantity=5000,
            urgency="normal", mid_price=100.0,
        )
        sell_result = service.execute(
            symbol="AAPL", side="SELL", quantity=3000,
            urgency="normal", mid_price=150.0,
        )

        assert buy_result["order"]["side"] == "BUY"
        assert sell_result["order"]["side"] == "SELL"
        assert buy_result["expected_fill_price"] >= 100.0
        assert sell_result["expected_fill_price"] <= 150.0


# ======================================================================
# Edge Cases
# ======================================================================

class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_zero_quantity_order(self):
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=0)
        assert order.fill_rate() == 0.0
        assert order.notional_value(100.0) == 0.0

    def test_negative_quantity(self):
        # Should handle gracefully
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=-100)
        assert order.fill_rate() == 0.0

    def test_empty_plan_slices(self):
        plan = ExecutionPlan(strategy="VWAP")
        assert plan.total_quantity == 0
        assert plan.remaining_quantity(0) == 0
        assert plan.is_complete(0)

    def test_impact_zero_volume(self):
        model = MarketImpactModel()
        result = model.estimate(quantity=1000, avg_daily_volume=0)
        assert result >= 0

    def test_tca_zero_expected_price(self):
        tca = TransactionCostAnalyzer()
        result = tca.analyze_detailed(expected=0.0, actual=100.0)
        assert result.total_cost_bps == 0.0

    def test_slippage_zero_market_volume(self):
        predictor = SlippagePredictor()
        order = ExecutionOrder(symbol="TEST", side="BUY", quantity=1000)
        result = predictor.predict(order, market_volume=0)
        assert result >= 0

    def test_routing_single_venue(self):
        router = SmartRoutingEngine(venues=[
            Venue(name="Only_Exchange"),
        ])
        order = ExecutionOrder(symbol="TEST", side="BUY", quantity=100)
        result = router.route(order)
        assert result["venue"] == "Only_Exchange"

    def test_plan_with_zero_slices(self):
        engine = ExecutionStrategyEngine()
        order = ExecutionOrder(symbol="NVDA", side="BUY", quantity=0,
                               urgency="normal")
        plan = engine.create_plan(order, slices=0)
        assert plan.total_quantity == 0

    def test_impact_optimal_slices_zero_quantity(self):
        model = MarketImpactModel()
        slices = model.optimal_slice_count(0)
        assert slices == 1
