"""Tests for Market Impact Engine, Imbalance Analysis, and Liquidity Service."""

import pytest
from datetime import datetime

from services.liquidity.models import (
    OrderBook,
    PriceLevel,
    Side,
    MarketCondition,
    MarketImpactEstimate,
    ImbalanceAnalysis,
    LiquidityGrade,
)
from services.liquidity.orderbook import OrderBookManager
from services.liquidity.impact import MarketImpactEngine
from services.liquidity.estimator import ImbalanceEstimator
from services.liquidity.service import LiquidityService


# =============================================================================
# Helpers
# =============================================================================


def _make_book(
    symbol="NVDA",
    bid_price=150.0,
    bid_vol=10000,
    ask_price=150.02,
    ask_vol=8000,
    adv=5000000,
    daily_vol=1000000,
    extra_bids=None,
    extra_asks=None,
) -> OrderBook:
    manager = OrderBookManager()
    bids = [(bid_price, bid_vol)]
    asks = [(ask_price, ask_vol)]
    if extra_bids:
        bids.extend(extra_bids)
    if extra_asks:
        asks.extend(extra_asks)
    return manager.build_book(
        symbol=symbol, bids=bids, asks=asks,
        last_price=(bid_price + ask_price) / 2,
        daily_volume=daily_vol, adv=adv,
    )


# =============================================================================
# 1. Market Impact Engine Tests
# =============================================================================


class TestMarketImpactEngine:
    """Tests for MarketImpactEngine."""

    def test_estimate_basic(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        estimate = engine.estimate(book, quantity=50000, side=Side.BUY)

        assert estimate.symbol == "NVDA"
        assert estimate.order_quantity == 50000
        assert estimate.total_impact_bps >= 0
        assert estimate.participation_rate == 0.01  # 50000/5000000
        assert estimate.spread_cost_bps >= 0

    def test_estimate_with_slices(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        estimate = engine.estimate(book, quantity=100000, num_slices=10, time_fraction=1.0)

        # With 10 slices, temporary impact should be lower
        single = engine.estimate(book, quantity=100000, num_slices=1)
        assert estimate.temporary_impact_bps <= single.temporary_impact_bps + 0.01  # Allow tolerance

    def test_estimate_buy_vs_sell(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)

        buy = engine.estimate(book, quantity=50000, side=Side.BUY)
        sell = engine.estimate(book, quantity=50000, side=Side.SELL)

        # Same quantity should have same impact regardless of side
        assert abs(buy.total_impact_bps - sell.total_impact_bps) < 0.01

    def test_low_participation(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        estimate = engine.estimate(book, quantity=5000)  # 0.1% participation
        assert estimate.recommended_algorithm == "DIRECT"
        assert estimate.recommended_slices == 1

    def test_medium_participation(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        estimate = engine.estimate(book, quantity=250000)  # 5% participation
        assert estimate.recommended_slices >= 1
        assert estimate.recommended_algorithm in ("TWAP", "VWAP", "POV")

    def test_high_participation(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        estimate = engine.estimate(book, quantity=1000000)  # 20% participation
        assert estimate.recommended_slices >= 10
        assert "POV" in estimate.recommended_algorithm

    def test_impact_with_high_volatility(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)

        low_vol = engine.estimate(book, quantity=50000, volatility=0.15)
        high_vol = engine.estimate(book, quantity=50000, volatility=0.60)

        # Higher volatility = higher impact
        assert high_vol.total_impact_bps > low_vol.total_impact_bps

    def test_impact_grade(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)

        # Small order = low impact
        small = engine.estimate(book, quantity=1000)
        assert small.impact_grade in (LiquidityGrade.EXCELLENT, LiquidityGrade.GOOD)

        # Large order = high impact
        large = engine.estimate(book, quantity=2000000)
        assert large.impact_grade in (LiquidityGrade.POOR, LiquidityGrade.AVOID)

    def test_estimate_to_dict(self):
        engine = MarketImpactEngine()
        book = _make_book()
        estimate = engine.estimate(book, quantity=50000, side=Side.BUY)
        d = estimate.to_dict()
        assert d["symbol"] == "NVDA"
        assert "total_impact_bps" in d
        assert "impact_grade" in d

    def test_compare_algorithms(self):
        engine = MarketImpactEngine()
        book = _make_book(adv=5000000)
        result = engine.compare_algorithms(book, quantity=100000, side=Side.BUY)

        assert "scenarios" in result
        assert "best" in result
        assert len(result["scenarios"]) == 5  # DIRECT, TWAP_10, VWAP_26, POV_30, POV_60

    def test_estimate_from_depth(self):
        engine = MarketImpactEngine()
        # Deep book with multiple levels
        book = _make_book(
            bid_price=150.0, bid_vol=50000, ask_price=150.02, ask_vol=80000,
            extra_asks=[(150.04, 50000), (150.06, 50000)],
        )
        estimate = engine.estimate_from_depth(book, quantity=10000, side=Side.BUY)
        assert estimate.symbol == "NVDA"
        # With 80000 at best ask, 10000 should fill within the first level
        assert estimate.confidence >= 0.6

    def test_estimate_from_depth_large_order(self):
        engine = MarketImpactEngine()
        book = _make_book(
            bid_price=150.0, bid_vol=10000, ask_price=150.02, ask_vol=5000,
        )
        # Order larger than best ask volume
        estimate = engine.estimate_from_depth(book, quantity=20000, side=Side.BUY)
        assert estimate.order_quantity == 20000
        # Should use formula for the unfilled portion
        assert estimate.total_impact_bps > 0

    def test_zero_adv_fallback(self):
        engine = MarketImpactEngine()
        book = OrderBook(symbol="T", bids=[PriceLevel(100, 1000)], asks=[PriceLevel(101, 1000)])
        estimate = engine.estimate(book, quantity=100, side=Side.BUY)
        assert estimate.total_cost_bps > 0


# =============================================================================
# 2. Imbalance Estimator Tests
# =============================================================================


class TestImbalanceEstimator:
    """Tests for ImbalanceEstimator."""

    def test_analyze_balanced(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=10000, ask_vol=10000)
        result = estimator.analyze(book)
        assert result.condition == MarketCondition.BALANCED
        assert abs(result.imbalance_ratio - 0.5) < 0.001

    def test_analyze_buy_pressure(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=70000, ask_vol=30000)
        result = estimator.analyze(book)
        assert result.condition == MarketCondition.BUY_PRESSURE
        assert result.suggested_aggressiveness > 0.5

    def test_analyze_sell_pressure(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=30000, ask_vol=70000)
        result = estimator.analyze(book)
        assert result.condition == MarketCondition.SELL_PRESSURE

    def test_analyze_extreme_buy(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=90000, ask_vol=10000)
        result = estimator.analyze(book)
        assert result.condition == MarketCondition.EXTREME_BUY

    def test_analyze_extreme_sell(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=10000, ask_vol=90000)
        result = estimator.analyze(book)
        assert result.condition == MarketCondition.EXTREME_SELL

    def test_imbalance_to_dict(self):
        estimator = ImbalanceEstimator()
        book = _make_book()
        result = estimator.analyze(book)
        d = result.to_dict()
        assert d["symbol"] == "NVDA"
        assert "condition" in d
        assert "suggested_aggressiveness" in d

    def test_get_execution_recommendation_buy(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=50000, ask_vol=50000)
        rec = estimator.get_execution_recommendation(book, side=Side.BUY, quantity=10000)
        assert rec["side"] == "BUY"
        assert "recommended_algorithm" in rec
        assert "aggressiveness" in rec
        assert "urgency" in rec

    def test_get_execution_recommendation_sell(self):
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=50000, ask_vol=50000)
        rec = estimator.get_execution_recommendation(book, side=Side.SELL, quantity=10000)
        assert rec["side"] == "SELL"
        assert rec["condition"] == "BALANCED"

    def test_buy_into_buy_pressure(self):
        """BUY into heavy buy pressure should be less aggressive."""
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=70000, ask_vol=30000)
        rec = estimator.get_execution_recommendation(book, side=Side.BUY, quantity=10000)
        assert rec["condition"] in ("BUY_PRESSURE", "EXTREME_BUY")
        # Should be TWAP (less aggressive for buys into buy pressure)
        assert rec["recommended_algorithm"] in ("TWAP", "VWAP")
        # Aggressiveness should be reduced
        assert rec["aggressiveness"] < 0.7

    def test_buy_into_sell_pressure(self):
        """BUY into sell pressure should be more aggressive."""
        estimator = ImbalanceEstimator()
        book = _make_book(bid_vol=30000, ask_vol=70000)
        rec = estimator.get_execution_recommendation(book, side=Side.BUY, quantity=10000)
        assert rec["condition"] in ("SELL_PRESSURE", "EXTREME_SELL")
        assert rec["recommended_algorithm"] == "POV"
        assert rec["urgency"] == "HIGH"


# =============================================================================
# 3. Liquidity Service Tests
# =============================================================================


class TestLiquidityService:
    """Tests for LiquidityService."""

    def test_evaluate_full(self):
        service = LiquidityService()
        book = _make_book(
            bid_price=150.0, bid_vol=10000,
            ask_price=150.02, ask_vol=8000,
            adv=5000000,
        )

        result = service.evaluate(
            book=book,
            quantity=50000,
            side=Side.BUY,
            volatility=0.25,
            strategy_id="TEST",
        )

        assert "score" in result
        assert "impact" in result
        assert "capacity" in result
        assert "imbalance" in result
        assert "recommendation" in result
        assert result["symbol"] == "NVDA"

    def test_evaluate_sell(self):
        service = LiquidityService()
        book = _make_book()
        result = service.evaluate(book=book, quantity=50000, side=Side.SELL)
        assert result["recommendation"]["side"] == "SELL"

    def test_quick_evaluate(self):
        service = LiquidityService()
        book = _make_book()
        result = service.quick_evaluate(book=book, quantity=50000, side=Side.BUY)

        assert "score" in result
        assert "impact_bps" in result
        assert "recommended_algorithm" in result

    def test_quick_evaluate_format(self):
        service = LiquidityService()
        book = _make_book()
        result = service.quick_evaluate(book=book, quantity=10000)

        # Should return simple dict with key fields
        assert isinstance(result["score"], str)  # grade value
        assert isinstance(result["score_value"], float)
        assert isinstance(result["recommended_algorithm"], str)

    def test_update_and_get_book(self):
        service = LiquidityService()

        book = service.update_book(
            symbol="NVDA",
            bids=[(150.0, 10000)],
            asks=[(150.02, 8000)],
            last_price=150.0,
            daily_volume=1000000,
        )

        retrieved = service.get_book("NVDA")
        assert retrieved is not None
        assert retrieved.symbol == "NVDA"

    def test_analyze_depth(self):
        service = LiquidityService()
        book = _make_book(extra_bids=[(149.98, 20000)], extra_asks=[(150.04, 15000)])
        analysis = service.analyze_depth(book, order_quantity=1000)
        assert analysis.symbol == "NVDA"
        assert analysis.depth_multiple > 0


# =============================================================================
# 4. MarketCondition Classification
# =============================================================================


class TestMarketCondition:
    """Tests for market condition classification."""

    def test_classify_balanced(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.5)
        assert analysis.condition == MarketCondition.BALANCED

    def test_classify_buy_pressure(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.7)
        assert analysis.condition == MarketCondition.BUY_PRESSURE

    def test_classify_sell_pressure(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.3)
        assert analysis.condition == MarketCondition.SELL_PRESSURE

    def test_classify_extreme_buy(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.85)
        assert analysis.condition == MarketCondition.EXTREME_BUY

    def test_classify_extreme_sell(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.15)
        assert analysis.condition == MarketCondition.EXTREME_SELL

    def test_precise_boundary_buy_pressure(self):
        # boundary at 0.65
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.65)
        assert analysis.condition == MarketCondition.BUY_PRESSURE

    def test_precise_boundary_sell_pressure(self):
        # boundary at 0.35
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.35)
        assert analysis.condition == MarketCondition.SELL_PRESSURE

    def test_precise_boundary_extreme_buy(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.80)
        assert analysis.condition == MarketCondition.EXTREME_BUY

    def test_precise_boundary_extreme_sell(self):
        analysis = ImbalanceAnalysis(symbol="T", imbalance_ratio=0.20)
        assert analysis.condition == MarketCondition.EXTREME_SELL
