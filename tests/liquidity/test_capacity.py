"""Tests for Capacity Analyzer, Impact Controller, and edge cases."""

import pytest
from datetime import datetime

from services.liquidity.models import (
    OrderBook,
    PriceLevel,
    Side,
    CapacityLevel,
    CapacityEstimate,
)
from services.liquidity.orderbook import OrderBookManager
from services.liquidity.capacity import CapacityAnalyzer
from services.execution.impact_controller import (
    ImpactController,
    ImpactBudget,
    ImpactBudgetStatus,
    AdjustmentAction,
)


# =============================================================================
# Helpers
# =============================================================================


def _make_book(
    symbol="NVDA",
    bid_vol=10000,
    ask_vol=8000,
    adv=5000000,
    mid_price=150.0,
) -> OrderBook:
    manager = OrderBookManager()
    return manager.build_book(
        symbol=symbol,
        bids=[(mid_price - 0.01, bid_vol), (mid_price - 0.05, bid_vol * 2)],
        asks=[(mid_price + 0.01, ask_vol), (mid_price + 0.05, ask_vol * 2)],
        last_price=mid_price,
        adv=adv,
    )


# =============================================================================
# 1. Capacity Analyzer Tests
# =============================================================================


class TestCapacityAnalyzer:
    """Tests for CapacityAnalyzer."""

    def test_analyze_basic(self):
        analyzer = CapacityAnalyzer(target_participation=0.10)
        book = _make_book(adv=5000000)
        result = analyzer.analyze(
            book=book,
            strategy_id="AI_Momentum",
            price=150.0,
        )
        assert result.strategy_id == "AI_Momentum"
        assert result.symbol == "NVDA"
        # Max daily = 0.10 * 5M * 150 = 75M
        assert result.max_daily_notional > 0
        assert result.max_single_order > 0

    def test_analyze_with_current_usage(self):
        analyzer = CapacityAnalyzer()
        book = _make_book(adv=5000000)
        result = analyzer.analyze(
            book=book,
            strategy_id="S1",
            price=150.0,
            current_daily_notional=30_000_000,  # 40% of max
            current_position=500000,
        )
        assert result.daily_capacity_pct > 0
        assert result.position_capacity_pct > 0
        assert result.can_scale

    def test_analyze_near_capacity(self):
        analyzer = CapacityAnalyzer()
        book = _make_book(adv=5000000)
        result = analyzer.analyze(
            book=book,
            strategy_id="S1",
            price=150.0,
            current_daily_notional=80_000_000,  # ~107% of 75M → CONSTRAINED
            current_position=20_000_000,
        )
        assert result.level in (CapacityLevel.CONSTRAINED, CapacityLevel.LIMITED)
        assert not result.can_scale

    def test_analyze_exceeded_capacity(self):
        analyzer = CapacityAnalyzer()
        book = _make_book(adv=5000000)
        result = analyzer.analyze(
            book=book,
            strategy_id="S1",
            price=150.0,
            current_daily_notional=200_000_000,  # > 2x max
            current_position=30_000_000,
        )
        assert result.level == CapacityLevel.LIMITED
        assert not result.can_scale

    def test_capacity_levels(self):
        """Test capacity level computation."""
        analyzer = CapacityAnalyzer()
        book = _make_book(adv=5000000)

        # High: < 50% used
        r1 = analyzer.analyze(book, "S1", price=150.0, current_daily_notional=10_000_000)
        assert r1.level == CapacityLevel.HIGH

        # Adequate: 50-100%
        r2 = analyzer.analyze(book, "S1", price=150.0, current_daily_notional=50_000_000)
        assert r2.level == CapacityLevel.ADEQUATE

        # Constrained: 100-200%
        r3 = analyzer.analyze(book, "S1", price=150.0, current_daily_notional=100_000_000)
        assert r3.level == CapacityLevel.CONSTRAINED

        # Limited: > 200%
        r4 = analyzer.analyze(book, "S1", price=150.0, current_daily_notional=200_000_000)
        assert r4.level == CapacityLevel.LIMITED

    def test_capacity_to_dict(self):
        analyzer = CapacityAnalyzer()
        book = _make_book()
        result = analyzer.analyze(book, strategy_id="S1", price=150.0)
        d = result.to_dict()
        assert d["strategy_id"] == "S1"
        assert "max_daily_notional" in d
        assert "level" in d
        assert "can_scale" in d

    def test_remaining_daily_capacity(self):
        analyzer = CapacityAnalyzer(target_participation=0.10)
        book = _make_book(adv=5000000)
        result = analyzer.analyze(book, "S1", price=150.0, current_daily_notional=20_000_000)
        assert result.remaining_daily_capacity > 0
        # Should be ~75M - 20M = 55M
        expected_remaining = result.max_daily_notional - 20_000_000
        assert abs(result.remaining_daily_capacity - expected_remaining) < 0.01

    def test_analyze_multi_symbol(self):
        analyzer = CapacityAnalyzer()
        books = {
            "NVDA": _make_book(symbol="NVDA", adv=5000000),
            "AAPL": _make_book(symbol="AAPL", adv=8000000),
        }
        results = analyzer.analyze_multi_symbol(
            books=books,
            strategy_id="S1",
            prices={"NVDA": 150.0, "AAPL": 175.0},
        )
        assert len(results) == 2
        assert results[0].symbol in ("NVDA", "AAPL")

    def test_aggregate_capacity(self):
        analyzer = CapacityAnalyzer()
        books = {
            "NVDA": _make_book(symbol="NVDA", adv=5000000),
            "AAPL": _make_book(symbol="AAPL", adv=8000000),
        }
        results = analyzer.analyze_multi_symbol(
            books=books,
            strategy_id="S1",
            prices={"NVDA": 150.0, "AAPL": 175.0},
            current_daily_notionals={"NVDA": 10_000_000, "AAPL": 20_000_000},
        )
        aggregate = analyzer.get_aggregate_capacity(results)
        assert aggregate["symbols"] == 2
        assert "total_max_daily" in aggregate
        assert "overall_level" in aggregate

    def test_aggregate_empty(self):
        analyzer = CapacityAnalyzer()
        result = analyzer.get_aggregate_capacity([])
        assert result["total_max_daily"] == 0.0

    def test_fallback_price(self):
        """Test fallback when price not provided."""
        analyzer = CapacityAnalyzer()
        book = _make_book(mid_price=150.0, adv=5000000)
        result = analyzer.analyze(book, "S1")  # No price
        assert result.max_daily_notional > 0
        assert result.price == 150.0  # Uses mid_price

    def test_zero_adv(self):
        """Test with zero ADV."""
        analyzer = CapacityAnalyzer()
        book = OrderBook(symbol="T", bids=[PriceLevel(100, 5000)], asks=[PriceLevel(101, 3000)])
        result = analyzer.analyze(book, "S1", price=100.0)
        # Should use default fallback
        assert result.max_daily_notional > 0


# =============================================================================
# 2. Impact Controller Tests
# =============================================================================


class TestImpactController:
    """Tests for ImpactController."""

    def test_create_budget(self):
        controller = ImpactController()
        budget = controller.create_budget(
            order_id="ORD_001",
            symbol="NVDA",
            max_total_cost_bps=20.0,
            projected_cost_bps=8.0,
            total_slices=10,
        )
        assert budget.order_id == "ORD_001"
        assert budget.max_total_cost_bps == 20.0
        assert budget.projected_cost_bps == 8.0
        assert budget.status == ImpactBudgetStatus.ON_TRACK

    def test_update_budget(self):
        controller = ImpactController()
        budget = controller.create_budget(
            order_id="ORD_001",
            symbol="NVDA",
            max_total_cost_bps=20.0,
            total_slices=10,
        )
        updated = controller.update_budget(
            order_id="ORD_001",
            realized_cost_bps=5.0,
            slice_num=3,
        )
        assert updated.realized_cost_bps == 5.0
        assert updated.slice_count == 3
        assert updated.remaining_budget_bps == 15.0
        assert updated.budget_consumed_pct == 0.25

    def test_budget_on_track(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0)
        budget = controller.update_budget("ORD_001", realized_cost_bps=5.0, slice_num=3)
        action = controller.check_budget(budget, remaining_slices=7)
        assert action == AdjustmentAction.NONE

    def test_budget_approaching_limit(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=17.0, slice_num=5)
        assert budget.status == ImpactBudgetStatus.APPROACHING_LIMIT

        action = controller.check_budget(budget, remaining_slices=5)
        assert action in (AdjustmentAction.REDUCE_SLICE_SIZE, AdjustmentAction.SLOW_DOWN)

    def test_budget_exceeded(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=22.0, slice_num=7)
        assert budget.status == ImpactBudgetStatus.EXCEEDED

        action = controller.check_budget(budget)
        assert action == AdjustmentAction.REDUCE_SLICE_SIZE

    def test_budget_severe(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=35.0, slice_num=9)
        assert budget.status == ImpactBudgetStatus.SEVERE
        # remaining_budget_bps = -15, which is >= -20, so SWITCH_ALGORITHM
        action = controller.check_budget(budget)
        assert action in (AdjustmentAction.SWITCH_ALGORITHM, AdjustmentAction.CANCEL)

    def test_budget_severe_cancel(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=45.0, slice_num=9)
        assert budget.status == ImpactBudgetStatus.SEVERE
        action = controller.check_budget(budget)
        assert action == AdjustmentAction.CANCEL

    def test_should_adjust(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=18.0, slice_num=8)

        result = controller.should_adjust(budget, current_slice_cost_bps=3.0, remaining_slices=2)
        assert "action" in result
        assert "budget_status" in result

    def test_get_per_slice_budget(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=5.0, slice_num=3)

        per_slice = controller.get_per_slice_budget(budget, total_slices=10, slice_num=4)
        # 15 bps remaining / 7 slices = ~2.14 bps per slice
        assert abs(per_slice - (15.0 / 7)) < 0.01

    def test_get_nonexistent_budget(self):
        controller = ImpactController()
        assert controller.get_budget("nonexistent") is None

    def test_update_nonexistent_budget(self):
        controller = ImpactController()
        with pytest.raises(ValueError):
            controller.update_budget("nonexistent", realized_cost_bps=5.0, slice_num=1)

    def test_budget_consumed_at_zero_max(self):
        """Edge case: zero max cost."""
        budget = ImpactBudget(order_id="T", symbol="T", max_total_cost_bps=0.0)
        assert budget.budget_consumed_pct == 0.0
        assert budget.remaining_budget_bps == 0.0

    def test_per_slice_budget_last_slice(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=10.0, slice_num=5)

        # Last slice
        per_slice = controller.get_per_slice_budget(budget, total_slices=10, slice_num=10)
        assert per_slice >= 0.0

    def test_per_slice_budget_no_remaining_slices(self):
        controller = ImpactController()
        budget = controller.create_budget("ORD_001", "NVDA", max_total_cost_bps=20.0, total_slices=10)
        budget = controller.update_budget("ORD_001", realized_cost_bps=10.0, slice_num=10)

        per_slice = controller.get_per_slice_budget(budget, total_slices=10, slice_num=11)
        assert per_slice == 0.0


# =============================================================================
# 3. Capacity Edge Cases
# =============================================================================


class TestCapacityEdgeCases:
    """Edge cases for capacity analysis."""

    def test_capacity_empty_book(self):
        analyzer = CapacityAnalyzer()
        book = OrderBook(symbol="T")
        result = analyzer.analyze(book, "S1", price=100.0)
        # Should use fallback values
        assert result.max_daily_notional >= 0
        assert result.max_single_order >= 0

    def test_capacity_to_dict_all_fields(self):
        analyzer = CapacityAnalyzer()
        book = _make_book(adv=5000000)
        result = analyzer.analyze(
            book=book,
            strategy_id="STRAT_001",
            price=150.0,
            current_daily_notional=30_000_000,
            current_position=200000,
        )
        d = result.to_dict()
        # All keys should be present
        expected_keys = {
            "strategy_id", "symbol", "max_daily_notional", "max_single_order",
            "max_position_size", "current_daily_notional", "current_position",
            "daily_capacity_pct", "position_capacity_pct", "level",
            "can_scale", "remaining_daily_capacity", "adv",
            "target_participation", "price",
        }
        assert expected_keys.issubset(set(d.keys()))
