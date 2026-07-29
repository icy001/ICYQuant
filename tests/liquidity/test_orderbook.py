"""Tests for OrderBook Engine — model, manager, depth analysis, scoring."""

import pytest
from datetime import datetime

from services.liquidity.models import (
    OrderBook,
    PriceLevel,
    Side,
    DepthLevel,
    LiquidityGrade,
    LiquidityScore,
    DepthAnalysis,
)
from services.liquidity.orderbook import OrderBookManager
from services.liquidity.depth import DepthAnalyzer
from services.liquidity.scoring import LiquidityScorer


# =============================================================================
# Helpers
# =============================================================================


def _make_book(
    symbol="NVDA",
    bid_price=150.0,
    bid_vol=10000,
    ask_price=150.02,
    ask_vol=8000,
    last_price=150.0,
    daily_vol=1000000,
    adv=5000000,
    extra_bids=None,
    extra_asks=None,
) -> OrderBook:
    """Create a test order book."""
    bids = [(bid_price, bid_vol)]
    asks = [(ask_price, ask_vol)]
    if extra_bids:
        bids.extend(extra_bids)
    if extra_asks:
        asks.extend(extra_asks)

    manager = OrderBookManager()
    return manager.build_book(
        symbol=symbol,
        bids=bids,
        asks=asks,
        last_price=last_price,
        daily_volume=daily_vol,
        adv=adv,
    )


def _make_deep_book() -> OrderBook:
    """Create a deep order book with 5 levels."""
    return _make_book(
        bid_price=150.00, bid_vol=10000,
        ask_price=150.02, ask_vol=8000,
        extra_bids=[(149.98, 20000), (149.95, 30000), (149.90, 50000), (149.85, 40000)],
        extra_asks=[(150.04, 15000), (150.06, 25000), (150.10, 35000), (150.15, 20000)],
    )


# =============================================================================
# 1. OrderBook Model Tests
# =============================================================================


class TestOrderBookModel:
    """Tests for OrderBook domain model."""

    def test_create_orderbook(self):
        book = _make_book()
        assert book.symbol == "NVDA"
        assert len(book.bids) == 1
        assert len(book.asks) == 1

    def test_best_bid_ask(self):
        book = _make_book()
        assert book.best_bid.price == 150.0
        assert book.best_bid.volume == 10000
        assert book.best_ask.price == 150.02
        assert book.best_ask.volume == 8000

    def test_mid_price(self):
        book = _make_book(bid_price=150.0, ask_price=150.04)
        assert abs(book.mid_price - 150.02) < 0.0001

    def test_mid_price_bid_only(self):
        book = OrderBook(symbol="T", bids=[PriceLevel(100.0, 100)])
        assert book.mid_price == 100.0

    def test_mid_price_ask_only(self):
        book = OrderBook(symbol="T", asks=[PriceLevel(101.0, 100)])
        assert book.mid_price == 101.0

    def test_mid_price_fallback_last_price(self):
        book = OrderBook(symbol="T", last_price=99.0)
        assert book.mid_price == 99.0

    def test_spread(self):
        book = _make_book(bid_price=150.0, ask_price=150.04)
        assert abs(book.spread - 0.04) < 0.0001

    def test_spread_bps(self):
        book = _make_book(bid_price=150.0, ask_price=150.03)
        expected_bps = (0.03 / 150.015) * 10000
        assert abs(book.spread_bps - expected_bps) < 0.01

    def test_total_bid_volume(self):
        book = _make_book(extra_bids=[(149.98, 5000)])
        assert book.total_bid_volume == 15000

    def test_total_ask_volume(self):
        book = _make_book(extra_asks=[(150.04, 3000)])
        assert book.total_ask_volume == 11000

    def test_bid_depth_5(self):
        book = _make_deep_book()
        # 5 bid levels
        bid_vols = [10000, 20000, 30000, 50000, 40000]
        assert book.bid_depth_5 == sum(bid_vols)

    def test_ask_depth_5(self):
        book = _make_deep_book()
        ask_vols = [8000, 15000, 25000, 35000, 20000]
        assert book.ask_depth_5 == sum(ask_vols)

    def test_imbalance_balanced(self):
        book = _make_book(bid_vol=10000, ask_vol=10000)
        assert abs(book.imbalance_ratio - 0.5) < 0.001

    def test_imbalance_buy_pressure(self):
        book = _make_book(bid_vol=30000, ask_vol=10000)
        assert book.imbalance_ratio == 0.75

    def test_imbalance_sell_pressure(self):
        book = _make_book(bid_vol=10000, ask_vol=30000)
        assert book.imbalance_ratio == 0.25

    def test_imbalance_empty_book(self):
        book = OrderBook(symbol="EMPTY")
        assert book.imbalance_ratio == 0.5

    def test_weighted_prices(self):
        book = _make_book(
            bid_price=150.0, bid_vol=10000,
            extra_bids=[(149.0, 10000)],
            ask_price=151.0, ask_vol=10000,
            extra_asks=[(152.0, 10000)],
        )
        expected_bid_vwap = (150.0 * 10000 + 149.0 * 10000) / 20000
        expected_ask_vwap = (151.0 * 10000 + 152.0 * 10000) / 20000
        assert abs(book.weighted_bid_price - expected_bid_vwap) < 0.001
        assert abs(book.weighted_ask_price - expected_ask_vwap) < 0.001

    def test_bid_sorting_descending(self):
        manager = OrderBookManager()
        book = manager.build_book(
            symbol="T",
            bids=[(100.0, 100), (102.0, 200), (101.0, 300)],
            asks=[(103.0, 100)],
        )
        prices = [b.price for b in book.bids]
        assert prices == [102.0, 101.0, 100.0]  # Descending

    def test_ask_sorting_ascending(self):
        manager = OrderBookManager()
        book = manager.build_book(
            symbol="T",
            bids=[(100.0, 100)],
            asks=[(105.0, 100), (103.0, 200), (104.0, 300)],
        )
        prices = [a.price for a in book.asks]
        assert prices == [103.0, 104.0, 105.0]  # Ascending

    def test_to_dict(self):
        book = _make_book()
        d = book.to_dict()
        assert d["symbol"] == "NVDA"
        assert d["best_bid"] == 150.0
        assert d["best_ask"] == 150.02
        assert d["mid_price"] == 150.01
        assert "bids" in d
        assert "asks" in d

    def test_price_level_notional(self):
        level = PriceLevel(price=150.0, volume=5000)
        assert level.notional == 750000.0

    def test_price_level_to_dict(self):
        level = PriceLevel(price=150.0, volume=5000, order_count=10)
        d = level.to_dict()
        assert d["price"] == 150.0
        assert d["volume"] == 5000
        assert d["order_count"] == 10
        assert d["notional"] == 750000.0


# =============================================================================
# 2. OrderBook Manager Tests
# =============================================================================


class TestOrderBookManager:
    """Tests for OrderBookManager."""

    def test_build_book_basic(self, manager=None):
        manager = manager or OrderBookManager()
        book = manager.build_book(
            symbol="NVDA",
            bids=[(150.0, 10000)],
            asks=[(150.02, 8000)],
            last_price=150.0,
        )
        assert book.symbol == "NVDA"
        assert len(book.bids) == 1
        assert len(book.asks) == 1

    def test_build_book_with_order_counts(self):
        manager = OrderBookManager()
        book = manager.build_book(
            symbol="NVDA",
            bids=[(150.0, 10000)],
            asks=[(150.02, 8000)],
            order_counts={"bids": [5], "asks": [3]},
        )
        assert book.bids[0].order_count == 5
        assert book.asks[0].order_count == 3

    def test_build_book_l1(self):
        manager = OrderBookManager()
        book = manager.build_book_l1(
            symbol="NVDA",
            bid_price=150.0, bid_volume=10000,
            ask_price=150.02, ask_volume=8000,
            last_price=150.0,
        )
        assert book.symbol == "NVDA"
        assert len(book.bids) == 1
        assert len(book.asks) == 1

    def test_get_book(self):
        manager = OrderBookManager()
        manager.build_book_l1(
            symbol="NVDA",
            bid_price=150.0, bid_volume=10000,
            ask_price=150.02, ask_volume=8000,
        )
        book = manager.get_book("NVDA")
        assert book is not None
        assert book.symbol == "NVDA"

    def test_get_book_case_insensitive(self):
        manager = OrderBookManager()
        manager.build_book_l1(
            symbol="NVDA",
            bid_price=150.0, bid_volume=10000,
            ask_price=150.02, ask_volume=8000,
        )
        book = manager.get_book("nvda")
        assert book is not None

    def test_get_book_nonexistent(self):
        manager = OrderBookManager()
        assert manager.get_book("NONEXISTENT") is None

    def test_list_symbols(self):
        manager = OrderBookManager()
        manager.build_book_l1("NVDA", 150, 10000, 150.02, 8000)
        manager.build_book_l1("AAPL", 175, 5000, 175.02, 3000)
        symbols = manager.list_symbols()
        assert "NVDA" in symbols
        assert "AAPL" in symbols

    def test_update_book(self):
        manager = OrderBookManager()
        book = manager.build_book_l1("NVDA", 150, 10000, 150.02, 8000)
        assert manager.get_book("NVDA").best_bid.volume == 10000

        # Update with new book
        new_book = OrderBook(symbol="NVDA", bids=[PriceLevel(151, 20000)], asks=[PriceLevel(151.02, 15000)])
        manager.update_book("NVDA", new_book)
        assert manager.get_book("NVDA").best_bid.volume == 20000

    def test_analyze_depth(self):
        manager = OrderBookManager()
        book = _make_deep_book()
        result = manager.analyze_depth(book, order_quantity=1000)
        assert result["symbol"] == "NVDA"
        # With 5 deep levels, depth multiple should be significant
        assert result["depth_multiple"] >= 8.0  # 8000 / 1000

    def test_compare_books(self):
        manager = OrderBookManager()
        before = _make_book(bid_price=150.0, ask_price=150.02, bid_vol=10000, ask_vol=8000)
        after = _make_book(bid_price=150.0, ask_price=150.04, bid_vol=12000, ask_vol=9000)

        result = manager.compare_books(before, after)
        assert result["spread_delta_bps"] > 0  # Spread widened
        assert result["bid_volume_delta"] == 2000


# =============================================================================
# 3. Depth Analyzer Tests
# =============================================================================


class TestDepthAnalyzer:
    """Tests for DepthAnalyzer."""

    def test_analyze_deep_book(self):
        analyzer = DepthAnalyzer()
        book = _make_deep_book()
        result = analyzer.analyze(book, order_quantity=1000)
        assert result.level == DepthLevel.MODERATE
        assert result.depth_multiple == 10.0  # 10000 / 1000 (max of best bid/ask)

    def test_analyze_shallow_book(self):
        analyzer = DepthAnalyzer()
        book = _make_book(bid_vol=300, ask_vol=200)
        result = analyzer.analyze(book, order_quantity=500)
        # 300 / 500 = 0.6 -> THIN
        assert result.level == DepthLevel.THIN

    def test_analyze_deep_level(self):
        analyzer = DepthAnalyzer()
        book = _make_book(bid_vol=100000, ask_vol=80000)
        result = analyzer.analyze(book, order_quantity=1000)
        assert result.level == DepthLevel.DEEP  # 100000/1000=100x

    def test_assess_depth_level(self):
        analyzer = DepthAnalyzer()
        assert analyzer.assess_depth_level(100) == DepthLevel.DEEP
        assert analyzer.assess_depth_level(20) == DepthLevel.MODERATE
        assert analyzer.assess_depth_level(5) == DepthLevel.SHALLOW
        assert analyzer.assess_depth_level(1) == DepthLevel.THIN

    def test_estimate_slices_needed(self):
        analyzer = DepthAnalyzer()
        # Deep book: 5 levels with lots of volume
        book = _make_deep_book()
        slices = analyzer.estimate_slices_needed(book, quantity=50000, max_impact_bps=5.0)
        assert slices >= 1

    def test_estimate_slices_thin_book(self):
        analyzer = DepthAnalyzer()
        book = _make_book(bid_vol=100, ask_vol=100)
        slices = analyzer.estimate_slices_needed(book, quantity=50000, max_impact_bps=5.0)
        assert slices > 1  # Thin book needs more slices


# =============================================================================
# 4. Liquidity Scorer Tests
# =============================================================================


class TestLiquidityScorer:
    """Tests for LiquidityScorer."""

    def test_score_excellent_liquidity(self):
        scorer = LiquidityScorer()
        book = _make_book(
            bid_price=150.0, bid_vol=500000,
            ask_price=150.001, ask_vol=500000,
            adv=10_000_000, daily_vol=8_000_000,
        )
        score = scorer.score(book, order_quantity=1000, volatility=0.15)
        assert score.score >= 80
        assert score.grade in (LiquidityGrade.EXCELLENT, LiquidityGrade.GOOD)

    def test_score_poor_liquidity(self):
        scorer = LiquidityScorer()
        book = _make_book(
            bid_price=150.0, bid_vol=500,
            ask_price=151.0, ask_vol=500,
            adv=10000, daily_vol=5000,
        )
        score = scorer.score(book, order_quantity=100000, volatility=0.60)
        assert score.score < 50

    def test_score_components(self):
        scorer = LiquidityScorer()
        book = _make_deep_book()
        score = scorer.score(book, order_quantity=5000)
        assert score.depth_score >= 0
        assert score.spread_score >= 0
        assert score.turnover_score >= 0
        assert score.fill_probability >= 0

    def test_score_to_dict(self):
        scorer = LiquidityScorer()
        book = _make_book()
        score = scorer.score(book, order_quantity=5000)
        d = score.to_dict()
        assert d["symbol"] == "NVDA"
        assert "score" in d
        assert "grade" in d

    def test_score_no_order_quantity(self):
        """Test scoring without a reference order quantity."""
        scorer = LiquidityScorer()
        book = _make_deep_book()
        score = scorer.score(book)
        assert score.score >= 0  # Should not crash

    def test_score_empty_book(self):
        scorer = LiquidityScorer()
        book = OrderBook(symbol="EMPTY")
        score = scorer.score(book, order_quantity=5000)
        assert score.score >= 0

    def test_grade_classification(self):
        score = LiquidityScore(symbol="TEST", score=95)
        assert score.grade == LiquidityGrade.EXCELLENT

        score = LiquidityScore(symbol="TEST", score=80)
        assert score.grade == LiquidityGrade.GOOD

        score = LiquidityScore(symbol="TEST", score=60)
        assert score.grade == LiquidityGrade.NORMAL

        score = LiquidityScore(symbol="TEST", score=40)
        assert score.grade == LiquidityGrade.POOR

        score = LiquidityScore(symbol="TEST", score=20)
        assert score.grade == LiquidityGrade.AVOID

    def test_depth_scoring_elements(self):
        scorer = LiquidityScorer()
        # High depth = high depth_score
        book_deep = _make_book(bid_vol=100000, ask_vol=80000)
        book_thin = _make_book(bid_vol=100, ask_vol=100)

        score_deep = scorer.score(book_deep, order_quantity=1000)
        score_thin = scorer.score(book_thin, order_quantity=1000)

        assert score_deep.depth_score > score_thin.depth_score

    def test_spread_scoring_elements(self):
        scorer = LiquidityScorer()
        # Tight spread = high spread_score
        book_tight = _make_book(bid_price=150.0, ask_price=150.01)
        book_wide = _make_book(bid_price=150.0, ask_price=150.50)

        score_tight = scorer.score(book_tight, order_quantity=1000)
        score_wide = scorer.score(book_wide, order_quantity=1000)

        assert score_tight.spread_score > score_wide.spread_score
