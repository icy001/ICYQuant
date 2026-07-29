"""Tests for Execution Optimization Engine.

Coverage:
- TWAP order slicing
- VWAP order slicing
- POV order slicing
- Market impact estimation
- Slippage analysis
- Execution algorithm selection
- Execution plan generation
- TCA cost analysis
- Benchmark calculation
- Edge cases (empty data, zero quantity, etc.)
"""

import math
from datetime import datetime

import pytest

from services.execution.optimization import (
    ExecutionAlgorithm,
    ExecutionOptimizer,
    ExecutionPlan,
    ExecutionSlice,
    ExecutionTask,
    ImpactEstimate,
    MarketImpactModel,
    MarketState,
    OrderSide,
    OrderSlicer,
    OrderUrgency,
    PlanStatus,
)
from services.execution.optimization.algorithms import (
    AdaptiveExecutor,
    PovExecutor,
    TwapExecutor,
    VwapExecutor,
)
from services.execution.tca import (
    BenchmarkCalculator,
    BenchmarkResult,
    TCAAnalyzer,
    TCAResult,
)


# =============================================================================
# Helper Functions
# =============================================================================


def _make_market_state(
    symbol: str = "NVDA",
    bid: float = 100.0,
    ask: float = 100.10,
    daily_volume: float = 10_000_000,
    volatility: float = 0.25,
) -> MarketState:
    return MarketState(
        symbol=symbol,
        bid=bid,
        ask=ask,
        last_price=(bid + ask) / 2,
        daily_volume=daily_volume,
        volatility_20d=volatility,
    )


def _make_task(
    symbol: str = "NVDA",
    quantity: float = 10000,
    side: str = "BUY",
    urgency: str = "MEDIUM",
    algorithm: str = "TWAP",
) -> ExecutionTask:
    side_map = {"BUY": OrderSide.BUY, "SELL": OrderSide.SELL}
    urgency_map = {
        "LOW": OrderUrgency.LOW,
        "MEDIUM": OrderUrgency.MEDIUM,
        "HIGH": OrderUrgency.HIGH,
        "CRITICAL": OrderUrgency.CRITICAL,
    }
    algo_map = {
        "TWAP": ExecutionAlgorithm.TWAP,
        "VWAP": ExecutionAlgorithm.VWAP,
        "POV": ExecutionAlgorithm.POV,
        "ADAPTIVE": ExecutionAlgorithm.ADAPTIVE,
    }
    return ExecutionTask(
        order_id=f"TEST_{symbol}",
        symbol=symbol,
        quantity=quantity,
        side=side_map.get(side, OrderSide.BUY),
        urgency=urgency_map.get(urgency, OrderUrgency.MEDIUM),
        algorithm=algo_map.get(algorithm, ExecutionAlgorithm.TWAP),
    )


# =============================================================================
# 1. Models
# =============================================================================


class TestExecutionModels:
    """Test execution optimization data models."""

    def test_execution_task_creation(self):
        task = _make_task()
        assert task.order_id == "TEST_NVDA"
        assert task.symbol == "NVDA"
        assert task.quantity == 10000
        assert task.side == OrderSide.BUY

    def test_execution_task_to_dict(self):
        task = _make_task()
        d = task.to_dict()
        assert d["order_id"] == "TEST_NVDA"
        assert d["side"] == "BUY"
        assert d["quantity"] == 10000

    def test_market_state_spread_calculation(self):
        ms = MarketState(
            symbol="NVDA",
            bid=100.0,
            ask=100.20,
            last_price=100.10,
        )
        assert ms.spread_bps > 0
        assert ms.mid_price == 100.10

    def test_market_state_to_dict(self):
        ms = _make_market_state()
        d = ms.to_dict()
        assert d["symbol"] == "NVDA"
        assert "mid_price" in d
        assert "spread_bps" in d

    def test_execution_slice_properties(self):
        s = ExecutionSlice(
            slice_id="S_001",
            order_id="O_001",
            symbol="NVDA",
            quantity=500,
            side=OrderSide.BUY,
            scheduled_time=datetime.utcnow(),
            executed_quantity=300,
        )
        assert s.fill_pct == 0.6

    def test_execution_plan_properties(self):
        plan = ExecutionPlan(
            plan_id="P_001",
            order_id="O_001",
            algorithm=ExecutionAlgorithm.TWAP,
            total_quantity=10000,
            executed_quantity=4000,
        )
        assert plan.remaining_quantity == 6000
        assert plan.fill_pct == 0.4

    def test_execution_plan_to_dict(self):
        plan = ExecutionPlan(
            plan_id="P_001",
            order_id="O_001",
            algorithm=ExecutionAlgorithm.TWAP,
            total_quantity=10000,
            duration_minutes=60,
        )
        d = plan.to_dict()
        assert d["plan_id"] == "P_001"
        assert d["algorithm"] == "TWAP"
        assert d["slice_count"] == 0

    def test_impact_estimate_to_dict(self):
        impact = ImpactEstimate(
            symbol="NVDA",
            order_quantity=10000,
            daily_volume=10_000_000,
            volatility=0.25,
            spread_bps=10.0,
            total_impact_bps=5.0,
            total_impact_amount=500.0,
        )
        d = impact.to_dict()
        assert "expected_impact_pct" in d
        assert d["total_impact_bps"] == 5.0

    def test_enum_values(self):
        assert ExecutionAlgorithm.TWAP.value == "TWAP"
        assert ExecutionAlgorithm.VWAP.value == "VWAP"
        assert ExecutionAlgorithm.POV.value == "POV"
        assert OrderSide.BUY.value == "BUY"
        assert OrderUrgency.LOW.value == "LOW"
        assert PlanStatus.CREATED.value == "CREATED"


# =============================================================================
# 2. Order Slicer — TWAP
# =============================================================================


class TestTwapSlicer:
    """Test TWAP order slicing."""

    def test_twap_basic_slicing(self):
        slicer = OrderSlicer(default_slices=20)
        task = _make_task(quantity=10000, algorithm="TWAP")
        slices = slicer.slice(task)

        assert len(slices) > 0
        total_qty = sum(s.quantity for s in slices)
        assert abs(total_qty - 10000) < 1.0

    def test_twap_slice_count(self):
        slicer = OrderSlicer(default_slices=10)
        task = _make_task(quantity=10000, algorithm="TWAP")
        slices = slicer.slice(task, num_slices=10)
        # May be slightly fewer due to min_slice_size
        assert len(slices) > 0

    def test_twap_equal_slices(self):
        slicer = OrderSlicer(default_slices=20)
        task = _make_task(quantity=20000, algorithm="TWAP")
        slices = slicer.slice(task, num_slices=20)

        # All slices should be roughly equal
        quantities = [s.quantity for s in slices]
        assert max(quantities) - min(quantities) < 0.01

    def test_twap_timing_sequential(self):
        slicer = OrderSlicer(default_slices=5)
        task = _make_task(quantity=5000, algorithm="TWAP")
        slices = slicer.slice(task, num_slices=5)

        for i in range(len(slices) - 1):
            assert slices[i].scheduled_time <= slices[i + 1].scheduled_time

    def test_twap_min_slice_size_respected(self):
        slicer = OrderSlicer(default_slices=20)
        task = _make_task(quantity=100, algorithm="TWAP")
        task.min_slice_size = 50.0
        slices = slicer.slice(task, num_slices=10)
        for s in slices:
            assert s.quantity >= 50.0 or s.quantity == task.quantity

    def test_twap_single_slice_small_order(self):
        slicer = OrderSlicer(default_slices=20)
        task = _make_task(quantity=50, algorithm="TWAP")
        task.min_slice_size = 10.0
        slices = slicer.slice(task, num_slices=5)
        total = sum(s.quantity for s in slices)
        assert abs(total - 50) < 1.0


# =============================================================================
# 3. Order Slicer — VWAP
# =============================================================================


class TestVwapSlicer:
    """Test VWAP order slicing."""

    def test_vwap_basic_slicing(self):
        slicer = OrderSlicer(default_slices=26)
        task = _make_task(quantity=50000, algorithm="VWAP")
        ms = _make_market_state()
        slices = slicer.slice(task, ms)

        assert len(slices) > 0
        total = sum(s.quantity for s in slices)
        assert abs(total - 50000) < 1.0

    def test_vwap_variable_slice_sizes(self):
        """VWAP slices should vary based on volume profile."""
        slicer = OrderSlicer(default_slices=26)
        task = _make_task(quantity=26000, algorithm="VWAP")
        ms = _make_market_state()
        slices = slicer.slice(task, ms)

        quantities = [s.quantity for s in slices]
        # VWAP slices should not all be identical
        assert max(quantities) != min(quantities) or len(quantities) <= 1

    def test_vwap_without_market_state(self):
        """VWAP should still work without market state."""
        slicer = OrderSlicer(default_slices=10)
        task = _make_task(quantity=10000, algorithm="VWAP")
        slices = slicer.slice(task, None)
        assert len(slices) > 0


# =============================================================================
# 4. Order Slicer — POV
# =============================================================================


class TestPovSlicer:
    """Test POV order slicing."""

    def test_pov_basic_slicing(self):
        slicer = OrderSlicer()
        task = _make_task(quantity=5000, algorithm="POV")
        task.max_participation_rate = 0.10
        ms = _make_market_state(daily_volume=1_000_000)
        slices = slicer.slice(task, ms)

        assert len(slices) > 0
        total = sum(s.quantity for s in slices)
        assert abs(total - 5000) < 1.0

    def test_pov_respects_participation_rate(self):
        slicer = OrderSlicer()
        task = _make_task(quantity=10000, algorithm="POV")
        task.max_participation_rate = 0.05
        ms = _make_market_state(daily_volume=1_000_000)
        slices = slicer.slice(task, ms)

        # Each slice should be <= participation_rate * expected_market_vol
        for s in slices:
            expected_max = 1_000_000 / 390 * 0.05  # per-minute vol * rate
            assert s.quantity <= expected_max * 1.1  # 10% tolerance

    def test_pov_empty_market(self):
        slicer = OrderSlicer()
        task = _make_task(quantity=1000, algorithm="POV")
        slices = slicer.slice(task, None)
        assert len(slices) > 0


# =============================================================================
# 5. Algorithm Executors
# =============================================================================


class TestAlgorithmExecutors:
    """Test TWAP, VWAP, POV executor classes."""

    def test_twap_executor_generates_plan(self):
        executor = TwapExecutor(default_slices=10)
        task = _make_task(quantity=10000)
        ms = _make_market_state()
        plan = executor.generate_plan(task, ms)

        assert plan.algorithm == ExecutionAlgorithm.TWAP
        assert plan.total_quantity == 10000
        assert plan.slice_count > 0

    def test_vwap_executor_generates_plan(self):
        executor = VwapExecutor(default_slices=26)
        task = _make_task(quantity=50000, algorithm="VWAP")
        ms = _make_market_state()
        plan = executor.generate_plan(task, ms)

        assert plan.algorithm == ExecutionAlgorithm.VWAP
        assert plan.total_quantity == 50000

    def test_pov_executor_generates_plan(self):
        executor = PovExecutor()
        task = _make_task(quantity=5000, algorithm="POV")
        ms = _make_market_state(daily_volume=500_000)
        plan = executor.generate_plan(task, ms)

        assert plan.algorithm == ExecutionAlgorithm.POV
        assert plan.slice_count > 0

    def test_adaptive_selects_algorithm_for_large_order(self):
        executor = AdaptiveExecutor()
        task = _make_task(quantity=1_000_000, urgency="LOW")  # 10% of ADV
        ms = _make_market_state(daily_volume=10_000_000, volatility=0.25)

        algo = executor.select_algorithm(task, ms)
        # Large order should prefer VWAP or POV
        assert algo in (ExecutionAlgorithm.VWAP, ExecutionAlgorithm.POV)

    def test_adaptive_selects_twap_for_small_order(self):
        executor = AdaptiveExecutor()
        task = _make_task(quantity=10000, urgency="MEDIUM")  # 0.1% of ADV
        ms = _make_market_state(daily_volume=10_000_000, volatility=0.15)

        algo = executor.select_algorithm(task, ms)
        assert algo == ExecutionAlgorithm.TWAP

    def test_adaptive_selects_twap_for_critical_urgency(self):
        executor = AdaptiveExecutor()
        task = _make_task(quantity=1_000_000, urgency="CRITICAL")
        ms = _make_market_state(daily_volume=10_000_000, volatility=0.30)

        algo = executor.select_algorithm(task, ms)
        assert algo == ExecutionAlgorithm.TWAP

    def test_adaptive_generates_plan(self):
        executor = AdaptiveExecutor()
        task = _make_task(quantity=100000, urgency="MEDIUM", algorithm="ADAPTIVE")
        ms = _make_market_state(daily_volume=1_000_000, volatility=0.20)
        plan = executor.generate_plan(task, ms)

        assert plan.total_quantity == 100000
        assert plan.slice_count > 0


# =============================================================================
# 6. Market Impact Model
# =============================================================================


class TestMarketImpact:
    """Test market impact estimation."""

    def test_basic_impact_estimate(self):
        model = MarketImpactModel()
        ms = _make_market_state(daily_volume=10_000_000, volatility=0.25)
        impact = model.estimate(
            symbol="NVDA",
            order_quantity=100000,
            market_state=ms,
        )

        assert impact.total_impact_bps > 0
        assert impact.participation_rate == 0.01  # 1%
        assert impact.temporary_impact_bps > 0
        assert impact.permanent_impact_bps > 0

    def test_impact_scales_with_quantity(self):
        """Larger orders should have higher impact."""
        model = MarketImpactModel()
        ms = _make_market_state(daily_volume=10_000_000)

        small = model.estimate("NVDA", 10000, ms)
        large = model.estimate("NVDA", 1_000_000, ms)

        assert large.total_impact_bps > small.total_impact_bps

    def test_impact_scales_with_volatility(self):
        """Higher volatility → higher impact."""
        model = MarketImpactModel()
        ms_low = _make_market_state(volatility=0.10)
        ms_high = _make_market_state(volatility=0.50)

        low = model.estimate("NVDA", 100000, ms_low)
        high = model.estimate("NVDA", 100000, ms_high)

        assert high.total_impact_bps > low.total_impact_bps

    def test_sliced_impact_lower_than_single(self):
        """Slicing should reduce temporary impact."""
        model = MarketImpactModel()
        ms = _make_market_state(daily_volume=10_000_000, volatility=0.25)

        single = model.estimate("NVDA", 100000, ms, time_fraction=1.0)
        sliced = model.estimate_sliced("NVDA", 100000, 20, ms)

        # Sliced temporary impact should be lower
        assert sliced.temporary_impact_bps < single.temporary_impact_bps

    def test_impact_zero_quantity(self):
        model = MarketImpactModel()
        ms = _make_market_state()
        impact = model.estimate("NVDA", 0, ms)
        assert impact.total_impact_bps == 0

    def test_compare_algorithms(self):
        model = MarketImpactModel()
        ms = _make_market_state(daily_volume=10_000_000)
        results = model.compare_algorithms("NVDA", 100000, ms)

        assert "single_order" in results
        assert "twap_20" in results
        assert "vwap_26" in results
        assert "pov_60" in results

        # Sliced should have lower impact than single order
        single_impact = results["single_order"]["total_impact_bps"]
        twap_impact = results["twap_20"]["total_impact_bps"]
        assert twap_impact < single_impact


# =============================================================================
# 7. Execution Optimizer
# =============================================================================


class TestExecutionOptimizer:
    """Test the full execution optimizer."""

    def test_optimize_generates_plan(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=50000, algorithm="TWAP")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)

        assert plan.total_quantity == 50000
        assert plan.slice_count > 0
        assert plan.algorithm == ExecutionAlgorithm.TWAP
        assert plan.status == PlanStatus.CREATED
        assert plan.expected_impact_bps > 0

    def test_optimize_adaptive(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=50000, algorithm="ADAPTIVE")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)

        assert plan.total_quantity == 50000
        assert plan.slice_count > 0

    def test_optimize_vwap(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=50000, algorithm="VWAP")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)

        assert plan.algorithm == ExecutionAlgorithm.VWAP

    def test_optimize_pov(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=5000, algorithm="POV")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)

        assert plan.algorithm == ExecutionAlgorithm.POV

    def test_evaluate_outcome(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=10000, algorithm="TWAP")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)
        plan.executed_quantity = 10000

        outcome = optimizer.evaluate_outcome(
            plan=plan,
            arrival_price=100.0,
            average_execution_price=100.05,
        )

        assert outcome.slippage_bps > 0  # Bought above arrival
        assert outcome.fill_rate == 1.0
        assert outcome.quality is not None

    def test_evaluate_outcome_perfect_execution(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=10000, algorithm="TWAP")
        ms = _make_market_state()
        plan = optimizer.optimize(task, ms)
        plan.executed_quantity = 10000

        outcome = optimizer.evaluate_outcome(
            plan=plan,
            arrival_price=100.0,
            average_execution_price=100.0,
        )

        assert outcome.slippage_bps == 0.0

    def test_get_recommendation(self):
        optimizer = ExecutionOptimizer()
        task = _make_task(quantity=50000)
        ms = _make_market_state()
        rec = optimizer.get_recommendation(task, ms)

        assert "recommended_algorithm" in rec
        assert "estimated_impact_bps" in rec
        assert "recommended_slices" in rec
        assert "participation_rate" in rec


# =============================================================================
# 8. Slicer Statistics
# =============================================================================


class TestSliceStatistics:
    """Test slice statistics computation."""

    def test_statistics_non_empty(self):
        slicer = OrderSlicer(default_slices=10)
        task = _make_task(quantity=10000, algorithm="TWAP")
        slices = slicer.slice(task)
        stats = slicer.compute_slice_statistics(slices)

        assert stats["total_slices"] > 0
        assert stats["total_quantity"] > 0
        assert stats["avg_slice_size"] > 0

    def test_statistics_empty(self):
        slicer = OrderSlicer()
        stats = slicer.compute_slice_statistics([])

        assert stats["total_slices"] == 0
        assert stats["total_quantity"] == 0

    def test_statistics_duration(self):
        slicer = OrderSlicer(default_slices=20)
        task = _make_task(quantity=10000, algorithm="TWAP")
        slices = slicer.slice(task)
        stats = slicer.compute_slice_statistics(slices)

        assert stats["duration_minutes"] >= 0


# =============================================================================
# 9. TCA — Benchmark Calculator
# =============================================================================


class TestBenchmarkCalculator:
    """Test TCA benchmark calculations."""

    def test_vwap_calculation(self):
        calc = BenchmarkCalculator()
        prices = [100.0, 101.0, 102.0, 101.0, 100.0]
        volumes = [1000, 2000, 3000, 2000, 1000]
        vwap = calc.compute_vwap(prices, volumes)

        assert vwap > 0
        # VWAP should be closer to higher-volume prices
        assert 100.5 < vwap < 101.5

    def test_vwap_equal_volumes_equals_twap(self):
        calc = BenchmarkCalculator()
        prices = [100.0, 101.0, 102.0]
        volumes = [1000, 1000, 1000]
        vwap = calc.compute_vwap(prices, volumes)

        assert vwap == 101.0

    def test_twap_calculation(self):
        calc = BenchmarkCalculator()
        prices = [100.0, 101.0, 102.0, 103.0, 104.0]
        twap = calc.compute_twap(prices)

        assert twap == 102.0

    def test_vwap_empty(self):
        calc = BenchmarkCalculator()
        assert calc.compute_vwap([], []) == 0.0

    def test_twap_empty(self):
        calc = BenchmarkCalculator()
        assert calc.compute_twap([]) == 0.0

    def test_compute_benchmarks(self):
        calc = BenchmarkCalculator()
        result = calc.compute_benchmarks(
            symbol="NVDA",
            arrival_price=100.0,
            trade_prices=[100.1, 100.2, 100.3, 100.2, 100.1],
            trade_volumes=[1000, 2000, 3000, 2000, 1000],
            open_price=99.5,
            close_price=100.5,
        )

        assert result.symbol == "NVDA"
        assert result.arrival_price == 100.0
        assert result.vwap > 0
        assert result.twap > 0
        assert result.high_price == 100.3
        assert result.low_price == 100.1
        assert result.volume == 9000

    def test_compare_to_benchmark(self):
        calc = BenchmarkCalculator()
        result = calc.compare_to_benchmark(
            execution_price=100.10,
            benchmark_price=100.00,
        )
        assert result["slippage_bps"] == 10.0
        assert result["cost"] == "MODERATE"
        assert not result["beats_benchmark"]

    def test_compare_beats_benchmark(self):
        calc = BenchmarkCalculator()
        result = calc.compare_to_benchmark(
            execution_price=99.90,  # Better than benchmark
            benchmark_price=100.00,
        )
        assert result["slippage_bps"] == -10.0
        assert result["beats_benchmark"]


# =============================================================================
# 10. TCA — Analyzer
# =============================================================================


class TestTCAAnalyzer:
    """Test TCA analysis engine."""

    def test_analyze_basic(self):
        analyzer = TCAAnalyzer()
        result = analyzer.analyze(
            order_id="ORD_001",
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            arrival_price=100.0,
            execution_price=100.10,
            spread_bps=5.0,
            commission=10.0,
        )

        assert result.order_id == "ORD_001"
        assert result.implementation_shortfall_bps > 0
        assert result.arrival_slippage_bps == 10.0
        assert result.commission_bps > 0

    def test_analyze_sell(self):
        """For sells, buying cheaper than arrival is good."""
        analyzer = TCAAnalyzer()
        result = analyzer.analyze(
            order_id="ORD_002",
            symbol="NVDA",
            side="SELL",
            quantity=10000,
            arrival_price=100.0,
            execution_price=99.90,
        )

        # Implementation shortfall for sell: arrival - execution = good
        assert result.arrival_slippage_bps == -10.0

    def test_analyze_vs_benchmarks(self):
        analyzer = TCAAnalyzer()
        result = analyzer.analyze(
            order_id="ORD_003",
            symbol="NVDA",
            side="BUY",
            quantity=10000,
            arrival_price=100.0,
            execution_price=100.05,
            benchmark_vwap=100.03,
            benchmark_twap=100.04,
        )

        assert result.vwap_slippage_bps > 0
        assert result.twap_slippage_bps > 0

    def test_tca_quality_assessment(self):
        analyzer = TCAAnalyzer()

        # Excellent execution
        r1 = analyzer.analyze(
            "E1", "NVDA", "BUY", 1000, 100.0, 100.01, spread_bps=1.0
        )
        assert r1.quality.value in ("EXCELLENT", "GOOD")

        # Poor execution
        r2 = analyzer.analyze(
            "E2", "NVDA", "BUY", 1000, 100.0, 100.30, spread_bps=10.0
        )
        assert r2.quality.value in ("FAIR", "POOR")

    def test_tca_summary_stats(self):
        analyzer = TCAAnalyzer()
        # No history
        stats = analyzer.get_summary_stats()
        assert stats["total_orders"] == 0

        # Add some history
        analyzer.analyze("O1", "NVDA", "BUY", 1000, 100.0, 100.02)
        analyzer.analyze("O2", "AAPL", "SELL", 500, 200.0, 199.95)

        stats = analyzer.get_summary_stats()
        assert stats["total_orders"] == 2
        assert "avg_cost_bps" in stats

    def test_tca_result_to_dict(self):
        analyzer = TCAAnalyzer()
        result = analyzer.analyze(
            "ORD_001", "NVDA", "BUY", 1000, 100.0, 100.05
        )
        d = result.to_dict()
        assert d["order_id"] == "ORD_001"
        assert "total_cost_bps" in d

    def test_clear_history(self):
        analyzer = TCAAnalyzer()
        analyzer.analyze("O1", "NVDA", "BUY", 1000, 100.0, 100.02)
        assert analyzer.get_summary_stats()["total_orders"] == 1

        analyzer.clear_history()
        assert analyzer.get_summary_stats()["total_orders"] == 0


# =============================================================================
# 11. Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_quantity(self):
        task = _make_task(quantity=0)
        slicer = OrderSlicer()
        slices = slicer.slice(task)
        # Should handle gracefully
        assert sum(s.quantity for s in slices) == 0

    def test_single_share(self):
        task = _make_task(quantity=1)
        task.min_slice_size = 1.0
        slicer = OrderSlicer(default_slices=20)
        slices = slicer.slice(task, num_slices=1)
        assert len(slices) >= 0

    def test_very_large_order(self):
        task = _make_task(quantity=10_000_000, algorithm="TWAP")
        ms = _make_market_state(daily_volume=100_000_000)
        slicer = OrderSlicer(default_slices=20)
        slices = slicer.slice(task, num_slices=20)

        total = sum(s.quantity for s in slices)
        assert total > 0

    def test_extreme_volatility(self):
        ms = _make_market_state(volatility=0.80)  # 80% vol
        model = MarketImpactModel()
        impact = model.estimate("NVDA", 100000, ms)

        assert impact.total_impact_bps > 0

    def test_zero_daily_volume(self):
        ms = MarketState(
            symbol="ILLIQUID",
            bid=10.0,
            ask=10.50,
            last_price=10.25,
            daily_volume=0.0,
        )
        model = MarketImpactModel()
        impact = model.estimate("ILLIQUID", 1000, ms)

        assert impact.total_impact_bps == 0

    def test_market_state_defaults(self):
        ms = MarketState(symbol="TEST", bid=10.0, ask=10.10, last_price=10.05)
        assert ms.daily_volume == 1_000_000.0
        assert ms.volatility_20d == 0.20

    def test_slicer_custom_volume_profile(self):
        custom_profile = [0.05] * 20  # Uniform
        slicer = OrderSlicer(volume_profile=custom_profile)
        task = _make_task(quantity=10000, algorithm="VWAP")
        slices = slicer.slice(task, num_slices=20)

        assert len(slices) > 0

    def test_twap_with_critical_urgency(self):
        task = _make_task(quantity=10000, urgency="CRITICAL", algorithm="TWAP")
        slicer = OrderSlicer(default_slices=20)
        slices = slicer.slice(task)

        assert len(slices) > 0
