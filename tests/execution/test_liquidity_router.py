"""Tests for Liquidity Router — execution layer integration."""

import pytest

from services.liquidity.models import (
    OrderBook,
    PriceLevel,
    Side,
    LiquidityGrade,
    MarketCondition,
)
from services.liquidity.orderbook import OrderBookManager
from services.liquidity.scoring import LiquidityScorer
from services.liquidity.impact import MarketImpactEngine
from services.liquidity.capacity import CapacityAnalyzer
from services.liquidity.estimator import ImbalanceEstimator
from services.liquidity.service import LiquidityService
from services.execution.liquidity_router import LiquidityRouter


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
# LiquidityRouter Tests
# =============================================================================


class TestLiquidityRouter:
    """Tests for LiquidityRouter."""

    def setup_method(self):
        self.router = LiquidityRouter()
        self.service = LiquidityService()

    def test_adapt_execution_excellent(self):
        """Test adaptation when liquidity is excellent."""
        book = _make_book(
            bid_vol=500000, ask_vol=500000,
            ask_price=150.001, adv=10_000_000,
        )
        result = self.service.evaluate(book, quantity=1000, side=Side.BUY)
        adapted = self.router.adapt_execution(result, default_algorithm="VWAP")

        assert adapted["algorithm"] == "VWAP"
        assert adapted["liquidity_grade"] in ("EXCELLENT", "GOOD")

    def test_adapt_execution_poor(self):
        """Test adaptation when liquidity is poor."""
        book = _make_book(
            bid_vol=500, ask_vol=300,
            ask_price=151.0, adv=50000,
        )
        result = self.service.evaluate(book, quantity=50000, side=Side.BUY)
        adapted = self.router.adapt_execution(result, default_algorithm="VWAP")

        assert adapted["algorithm"] == "POV"
        assert adapted["liquidity_grade"] in ("POOR", "AVOID")
        # Poor liquidity = more slices
        assert adapted["slices"] >= 10

    def test_adapt_execution_buy_pressure(self):
        """Test adaptation with buy pressure."""
        book = _make_book(bid_vol=80000, ask_vol=20000)
        result = self.service.evaluate(book, quantity=5000, side=Side.BUY)
        adapted = self.router.adapt_execution(result)

        # Buy into buy pressure = less urgency
        assert adapted["aggressiveness"] > 0

    def test_adapt_execution_returns_all_fields(self):
        """Test that all expected fields are returned."""
        book = _make_book()
        result = self.service.evaluate(book, quantity=50000, side=Side.BUY)
        adapted = self.router.adapt_execution(result)

        required = {"algorithm", "slices", "urgency", "aggressiveness",
                     "max_slice_size", "liquidity_grade", "liquidity_score"}
        assert required.issubset(set(adapted.keys()))

    def test_get_routing_advice(self):
        """Test routing advice generation."""
        book = _make_book()
        result = self.service.evaluate(book, quantity=50000, side=Side.BUY)
        advice = self.router.get_routing_advice(result)

        assert "liquidity_grade" in advice
        assert "market_condition" in advice
        assert "advice" in advice
        assert "warnings" in advice

    def test_get_routing_advice_poor_liquidity(self):
        """Test routing advice with poor liquidity."""
        book = _make_book(bid_vol=500, ask_vol=300, ask_price=152.0, adv=50000)
        result = self.service.evaluate(book, quantity=50000, side=Side.BUY)
        advice = self.router.get_routing_advice(result)

        assert len(advice["warnings"]) > 0
        assert any("impact" in w.lower() or "liquidity" in w.lower() for w in advice["warnings"])

    def test_get_routing_advice_normal(self):
        """Test routing advice with normal conditions."""
        book = _make_book(adv=5000000)
        result = self.service.evaluate(book, quantity=5000, side=Side.BUY)
        advice = self.router.get_routing_advice(result)

        assert advice["market_condition"] == "BALANCED"
        # No extreme warnings
        assert len([w for w in advice["warnings"] if "Extreme" in w]) == 0

    def test_adapt_with_defaults(self):
        """Test that defaults are used when no liquidity data."""
        empty_result = {
            "score": {},
            "impact": {},
            "recommendation": {},
            "imbalance": {},
        }
        adapted = self.router.adapt_execution(empty_result)

        assert adapted["algorithm"] == "TWAP"  # Default for NORMAL
        assert adapted["slices"] == 10

    def test_algorithm_selection_by_grade(self):
        """Test algorithm selection based on grade."""
        for grade, expected in [
            ("EXCELLENT", "VWAP"),
            ("GOOD", "VWAP"),
            ("NORMAL", "TWAP"),
            ("POOR", "POV"),
            ("AVOID", "POV"),
        ]:
            result = {"score": {"grade": grade, "score": 50},
                      "impact": {}, "recommendation": {}, "imbalance": {}}
            adapted = self.router.adapt_execution(result, default_algorithm="TWAP")
            assert adapted["algorithm"] == expected, f"Expected {expected} for {grade}"


# =============================================================================
# Integration Tests: Liquidity -> Execution
# =============================================================================


class TestLiquidityExecutionIntegration:
    """End-to-end tests: liquidity analysis feeds into execution params."""

    def test_full_flow_excellent_liquidity(self):
        """Full flow: excellent liquidity → VWAP, low slices."""
        service = LiquidityService()
        router = LiquidityRouter()

        book = _make_book(
            bid_vol=500000, ask_vol=500000,
            ask_price=150.001, adv=10_000_000,
        )
        result = service.evaluate(book, quantity=5000, side=Side.BUY)
        adapted = router.adapt_execution(result)

        assert adapted["algorithm"] in ("VWAP", "TWAP")
        assert adapted["slices"] <= 10  # Good liquidity needs fewer slices

    def test_full_flow_poor_liquidity(self):
        """Full flow: poor liquidity → POV, many slices."""
        service = LiquidityService()
        router = LiquidityRouter()

        book = _make_book(
            bid_vol=300, ask_vol=200,
            ask_price=151.5, adv=10000,
        )
        result = service.evaluate(book, quantity=5000, side=Side.BUY)
        adapted = router.adapt_execution(result)

        assert adapted["algorithm"] == "POV"
        assert adapted["slices"] >= 10  # More slices for poor liquidity

    def test_buy_pressure_affects_sell(self):
        """Buy pressure should make selling aggressive (capture demand)."""
        service = LiquidityService()
        book = _make_book(bid_vol=80000, ask_vol=20000)

        result = service.evaluate(book, quantity=5000, side=Side.SELL)
        adapted = LiquidityRouter().adapt_execution(result)

        # Selling into buy pressure = aggressive POV to capture demand
        assert adapted["algorithm"] in ("POV", "TWAP", "VWAP")
        assert adapted["aggressiveness"] > 0.3

    def test_sell_pressure_affects_buy(self):
        """Sell pressure should make buying more aggressive."""
        service = LiquidityService()
        book = _make_book(bid_vol=20000, ask_vol=80000)

        result = service.evaluate(book, quantity=5000, side=Side.BUY)
        adapted = LiquidityRouter().adapt_execution(result)

        # Buying into sell pressure should use POV
        assert adapted["algorithm"] == "POV"
        assert adapted["urgency"] == "HIGH"
