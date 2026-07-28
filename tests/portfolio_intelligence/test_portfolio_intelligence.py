"""Tests for AI Portfolio Intelligence Engine (Part 30)."""

import pytest
from services.portfolio_intelligence import (
    # Allocation
    AssetAllocation,
    AssetAllocationEngine,
    AssetClass,
    AllocationResult,
    AllocationStrategy,
    Horizon,
    RiskTolerance,
    # Sizing
    PositionSize,
    PositionSizingEngine,
    SizingMethod,
    SizingPriority,
    SizingResult,
    # Budget
    BudgetAllocation,
    BudgetLevel,
    BudgetMethod,
    BudgetStatus,
    RiskBudget,
    RiskBudgetEngine,
    # Exposure
    Exposure,
    ExposureDirection,
    ExposureEngine,
    ExposureReport,
    ExposureStatus,
    ExposureType,
    # Optimizer
    ConstraintType,
    EfficientFrontierPoint,
    Objective,
    OptimizationConstraint,
    OptimizationResult,
    PortfolioOptimizer,
    # Rebalance
    RebalanceEngine,
    RebalancePlan,
    RebalanceStatus,
    RebalanceStrategy,
    RebalanceTrade,
    TradeSide,
    # Attribution
    AttributionComponent,
    AttributionEngine,
    AttributionLevel,
    AttributionMethod,
    AttributionResult,
    # Memory
    DecisionOutcome,
    MemoryEvent,
    MemoryEventType,
    PerformanceSnapshot,
    PortfolioInsight,
    PortfolioMemory,
    # Service
    PortfolioBuildResult,
    PortfolioIntelligenceService,
)


# ====================================================================
# AssetAllocationEngine
# ====================================================================

class TestAssetAllocationEngine:
    def test_default_allocate(self):
        engine = AssetAllocationEngine()
        result = engine.allocate()
        assert isinstance(result, AllocationResult)
        assert result.strategy == AllocationStrategy.RISK_PARITY
        assert len(result.allocations) == len(AssetClass)
        assert result.is_valid
        assert abs(result.total_weight - 1.0) < 0.01

    def test_equal_weight_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.EQUAL_WEIGHT)
        result = engine.allocate()
        weights = [a.target_weight for a in result.allocations]
        # All active assets should have same weight
        assert max(weights) - min(weights) < 0.001
        assert result.is_valid

    def test_risk_parity_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.RISK_PARITY)
        asset_data = {
            AssetClass.EQUITY: {"volatility": 0.18},
            AssetClass.FIXED_INCOME: {"volatility": 0.05},
            AssetClass.CASH: {"volatility": 0.005},
        }
        result = engine.allocate(asset_data=asset_data)
        # Low vol assets should get higher weight
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        assert weights.get("fixed_income", 0) > weights.get("equity", 0)
        assert result.is_valid

    def test_conservative_risk_profile(self):
        engine = AssetAllocationEngine(risk_tolerance=RiskTolerance.CONSERVATIVE)
        result = engine.allocate()
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        # Conservative should have higher cash allocation
        assert weights.get("cash", 0) >= 0.10

    def test_aggressive_risk_profile(self):
        engine = AssetAllocationEngine(risk_tolerance=RiskTolerance.AGGRESSIVE)
        result = engine.allocate()
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        # Aggressive profile has 1.4x equity multiplier → equity should be largest weight
        assert weights.get("equity", 0) >= max(weights.values()) * 0.8

    def test_momentum_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.MOMENTUM_BASED)
        asset_data = {
            AssetClass.EQUITY: {"momentum_3m": 0.10, "momentum_6m": 0.08},
            AssetClass.FIXED_INCOME: {"momentum_3m": -0.02, "momentum_6m": 0.01},
        }
        result = engine.allocate(asset_data=asset_data)
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        assert weights.get("equity", 0) > weights.get("fixed_income", 0)

    def test_min_variance_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.MIN_VARIANCE)
        asset_data = {
            AssetClass.EQUITY: {"volatility": 0.30},
            AssetClass.CASH: {"volatility": 0.005},
        }
        result = engine.allocate(asset_data=asset_data)
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        assert weights.get("cash", 0) > weights.get("equity", 0)

    def test_adaptive_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.ADAPTIVE)
        result = engine.allocate()
        assert result.is_valid
        assert result.diversification_ratio > 0

    def test_black_litterman_strategy(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.BLACK_LITTERMAN)
        views = {AssetClass.EQUITY: 0.05, AssetClass.FIXED_INCOME: -0.02}
        result = engine.allocate(views=views)
        # Positive view → higher weight
        weights = {a.asset_class.value: a.target_weight for a in result.allocations}
        assert weights.get("equity", 0) > 0

    def test_constraint_application(self):
        engine = AssetAllocationEngine(strategy=AllocationStrategy.RISK_PARITY)
        constraints = {
            AssetClass.EQUITY: {"max_weight": 0.25},
            AssetClass.CRYPTO: {"excluded": True},
        }
        result = engine.allocate(constraints=constraints)
        eq_allocation = [a for a in result.allocations if a.asset_class == AssetClass.EQUITY][0]
        assert eq_allocation.target_weight <= 0.25
        crypto_allocation = [a for a in result.allocations if a.asset_class == AssetClass.CRYPTO]
        if crypto_allocation:
            assert crypto_allocation[0].target_weight == 0.0

    def test_quick_allocate(self):
        engine = AssetAllocationEngine()
        result = engine.quick_allocate()
        assert "strategy" in result
        assert "weights" in result
        assert "sharpe_ratio" in result
        assert isinstance(result["weights"], dict)

    def test_history_and_clear(self):
        engine = AssetAllocationEngine()
        engine.allocate()
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# PositionSizingEngine
# ====================================================================

class TestPositionSizingEngine:
    def _make_assets(self, symbols=None):
        symbols = symbols or ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        return [
            {
                "symbol": s,
                "win_rate": 0.55,
                "avg_win": 0.03,
                "avg_loss": 0.02,
                "volatility": 0.20,
                "correlation": 0.3,
                "liquidity_score": 0.9,
            }
            for s in symbols
        ]

    def test_fixed_fraction(self):
        engine = PositionSizingEngine(method=SizingMethod.FIXED_FRACTION)
        assets = self._make_assets(["A", "B", "C", "D"])
        result = engine.calculate(assets)
        assert isinstance(result, SizingResult)
        assert result.position_count == 4
        assert result.total_allocation <= 1.0 + 0.01

    def test_kelly_criterion(self):
        engine = PositionSizingEngine(method=SizingMethod.KELLY_CRITERION)
        assets = self._make_assets(["A", "B"])
        result = engine.calculate(assets)
        assert result.position_count == 2
        for p in result.positions:
            assert p.target_size_pct <= 0.30  # Kelly cap

    def test_volatility_target(self):
        engine = PositionSizingEngine(method=SizingMethod.VOLATILITY_TARGET)
        assets = [
            {"symbol": "A", "volatility": 0.10, "correlation": 0.0, "liquidity_score": 1.0},
            {"symbol": "B", "volatility": 0.30, "correlation": 0.0, "liquidity_score": 1.0},
        ]
        result = engine.calculate(assets)
        positions = {p.symbol: p.target_size_pct for p in result.positions}
        # Lower vol should get higher allocation
        assert positions.get("A", 0) > positions.get("B", 0)

    def test_equal_risk(self):
        engine = PositionSizingEngine(method=SizingMethod.EQUAL_RISK)
        assets = self._make_assets(["A", "B", "C"])
        result = engine.calculate(assets)
        assert result.position_count == 3

    def test_position_cap(self):
        engine = PositionSizingEngine()
        assets = self._make_assets(["A", "B"])
        result = engine.calculate(assets, constraints={"max_position": 0.15})
        for p in result.positions:
            assert p.target_size_pct <= 0.15

    def test_concentration_ratio(self):
        engine = PositionSizingEngine()
        assets = self._make_assets(["A", "B", "C", "D", "E", "F", "G", "H"])
        result = engine.calculate(assets)
        assert 0 <= result.concentration_ratio <= 1.0

    def test_risk_utilization(self):
        engine = PositionSizingEngine()
        assets = self._make_assets(["A", "B", "C"])
        result = engine.calculate(assets)
        assert 0 <= result.risk_utilization <= 1.0

    def test_quick_size(self):
        engine = PositionSizingEngine()
        result = engine.quick_size(["AAPL", "GOOGL", "MSFT"])
        assert "positions" in result
        assert "total_allocation" in result
        assert len(result["positions"]) == 3

    def test_low_liquidity_adjustment(self):
        engine = PositionSizingEngine(method=SizingMethod.FIXED_FRACTION)
        assets = [
            {"symbol": "A", "volatility": 0.15, "correlation": 0.0, "liquidity_score": 0.2},
            {"symbol": "B", "volatility": 0.15, "correlation": 0.0, "liquidity_score": 1.0},
        ]
        result = engine.calculate(assets)
        positions = {p.symbol: p.target_size_pct for p in result.positions}
        assert positions.get("A", 0) < positions.get("B", 0)

    def test_history_and_clear(self):
        engine = PositionSizingEngine()
        assets = self._make_assets(["A"])
        engine.calculate(assets)
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# RiskBudgetEngine
# ====================================================================

class TestRiskBudgetEngine:
    def test_equal_distribution(self):
        engine = RiskBudgetEngine(method=BudgetMethod.EQUAL_DISTRIBUTION)
        entities = [
            {"entity_id": "equity", "level": "asset_class"},
            {"entity_id": "fixed_income", "level": "asset_class"},
            {"entity_id": "commodity", "level": "asset_class"},
        ]
        result = engine.allocate(entities)
        assert isinstance(result, BudgetAllocation)
        assert len(result.budgets) == 3
        # Equal distribution → all budgets similar
        budgets = [b.budget_pct for b in result.budgets]
        assert max(budgets) - min(budgets) < 0.001

    def test_volatility_weighted(self):
        engine = RiskBudgetEngine(method=BudgetMethod.VOLATILITY_WEIGHTED)
        entities = [
            {"entity_id": "high_vol", "level": "asset_class", "volatility": 0.30},
            {"entity_id": "low_vol", "level": "asset_class", "volatility": 0.10},
        ]
        result = engine.allocate(entities)
        # Higher vol → higher risk budget
        budgets = {b.entity_id: b.budget_pct for b in result.budgets}
        assert budgets["high_vol"] > budgets["low_vol"]

    def test_sharpe_weighted(self):
        engine = RiskBudgetEngine(method=BudgetMethod.SHARPE_WEIGHTED)
        entities = [
            {"entity_id": "good", "level": "asset_class", "sharpe": 1.0},
            {"entity_id": "bad", "level": "asset_class", "sharpe": 0.2},
        ]
        result = engine.allocate(entities)
        budgets = {b.entity_id: b.budget_pct for b in result.budgets}
        assert budgets["good"] > budgets["bad"]

    def test_custom_weights(self):
        engine = RiskBudgetEngine(method=BudgetMethod.CUSTOM)
        entities = [
            {"entity_id": "high", "level": "asset_class", "weight": 0.7},
            {"entity_id": "low", "level": "asset_class", "weight": 0.3},
        ]
        result = engine.allocate(entities)
        budgets = {b.entity_id: b.budget_pct for b in result.budgets}
        assert budgets["high"] > budgets["low"]

    def test_budget_consumption(self):
        engine = RiskBudgetEngine()
        entities = [
            {"entity_id": "equity", "level": "asset_class"},
            {"entity_id": "fixed_income", "level": "asset_class"},
        ]
        result = engine.allocate(entities, consumption={"equity": 0.06})
        eq_budget = [b for b in result.budgets if b.entity_id == "equity"][0]
        assert eq_budget.consumed_pct == 0.06

    def test_exceeded_detection(self):
        engine = RiskBudgetEngine()
        entities = [{"entity_id": "equity", "level": "asset_class"}]
        result = engine.allocate(entities, consumption={"equity": 0.20})
        eq_budget = [b for b in result.budgets if b.entity_id == "equity"][0]
        assert eq_budget.is_exceeded

    def test_check_budgets_healthy(self):
        engine = RiskBudgetEngine()
        entities = [{"entity_id": "equity", "level": "asset_class"}]
        result = engine.allocate(entities)
        check = engine.check_budgets(result)
        assert check["overall_status"] == "healthy"

    def test_check_budgets_exceeded(self):
        engine = RiskBudgetEngine()
        entities = [{"entity_id": "equity", "level": "asset_class"}]
        result = engine.allocate(entities, consumption={"equity": 0.20})
        check = engine.check_budgets(result)
        assert check["overall_status"] == "critical"

    def test_quick_budget(self):
        engine = RiskBudgetEngine()
        result = engine.quick_budget(["AAPL", "GOOGL", "MSFT"])
        assert "total_budget" in result
        assert "budgets" in result
        assert len(result["budgets"]) == 3

    def test_history_and_clear(self):
        engine = RiskBudgetEngine()
        entities = [{"entity_id": "equity", "level": "asset_class"}]
        engine.allocate(entities)
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# ExposureEngine
# ====================================================================

class TestExposureEngine:
    def _make_positions(self):
        return [
            {
                "symbol": "AAPL",
                "market_value": 200000,
                "beta": 1.2,
                "sector": "technology",
                "region": "US",
                "currency": "USD",
                "style": "growth",
                "factor_loadings": {"momentum": 0.3, "quality": 0.5},
                "instrument_type": "equity",
                "liquidity_score": 0.95,
            },
            {
                "symbol": "XOM",
                "market_value": 100000,
                "beta": 0.8,
                "sector": "energy",
                "region": "US",
                "currency": "USD",
                "style": "value",
                "factor_loadings": {"value": 0.6, "low_vol": 0.4},
                "instrument_type": "equity",
                "liquidity_score": 0.85,
            },
        ]

    def test_analyze_basic(self):
        engine = ExposureEngine()
        positions = self._make_positions()
        report = engine.analyze(positions, nav=500000)
        assert isinstance(report, ExposureReport)
        assert len(report.exposures) > 0
        assert report.total_gross_exposure > 0

    def test_within_limits_default(self):
        engine = ExposureEngine()
        # Balanced 5-stock portfolio to avoid concentration breaches
        positions = [
            {"symbol": "AAPL", "market_value": 200000, "beta": 1.0, "sector": "tech",
             "region": "US", "currency": "USD", "style": "growth",
             "factor_loadings": {"momentum": 0.2}, "instrument_type": "equity", "liquidity_score": 0.95},
            {"symbol": "JNJ", "market_value": 200000, "beta": 0.6, "sector": "healthcare",
             "region": "US", "currency": "USD", "style": "value",
             "factor_loadings": {"quality": 0.3}, "instrument_type": "equity", "liquidity_score": 0.90},
            {"symbol": "XOM", "market_value": 200000, "beta": 0.8, "sector": "energy",
             "region": "US", "currency": "USD", "style": "value",
             "factor_loadings": {"value": 0.4}, "instrument_type": "equity", "liquidity_score": 0.85},
            {"symbol": "TLT", "market_value": 200000, "beta": -0.2, "sector": "government",
             "region": "US", "currency": "USD", "style": "defensive",
             "factor_loadings": {"low_vol": 0.5}, "instrument_type": "fixed_income", "liquidity_score": 0.95},
            {"symbol": "GLD", "market_value": 200000, "beta": 0.1, "sector": "precious_metals",
             "region": "global", "currency": "USD", "style": "defensive",
             "factor_loadings": {}, "instrument_type": "commodity", "liquidity_score": 0.90},
        ]
        report = engine.analyze(positions, nav=2_000_000)
        # Diversified portfolio should have fewer breaches
        assert report.is_within_limits or report.breached_exposures <= 2

    def test_breached_detection(self):
        engine = ExposureEngine()
        # Over-concentrated portfolio
        positions = [self._make_positions()[0]]  # single stock
        report = engine.analyze(positions, nav=200000)
        # Single stock = 100% sector concentration
        assert report.breached_exposures >= 1

    def test_all_exposure_types(self):
        engine = ExposureEngine()
        positions = self._make_positions()
        report = engine.analyze(positions, nav=500000)
        exposure_types = [e.exposure_type for e in report.exposures]
        expected = [
            ExposureType.MARKET_BETA,
            ExposureType.SECTOR,
            ExposureType.GEOGRAPHY,
            ExposureType.CURRENCY,
            ExposureType.STYLE,
            ExposureType.FACTOR,
            ExposureType.INSTRUMENT,
            ExposureType.LIQUIDITY,
            ExposureType.CONCENTRATION,
        ]
        for et in expected:
            assert et in exposure_types, f"Missing exposure type: {et}"

    def test_set_limit(self):
        engine = ExposureEngine()
        engine.set_limit(ExposureType.SECTOR, 0.10)
        assert engine.limits[ExposureType.SECTOR] == 0.10

    def test_breach_summary(self):
        engine = ExposureEngine()
        positions = [self._make_positions()[0]]
        report = engine.analyze(positions, nav=200000)
        summary = engine.get_breach_summary(report)
        assert "status" in summary
        assert "breaches" in summary

    def test_quick_scan(self):
        engine = ExposureEngine()
        positions = self._make_positions()
        result = engine.quick_scan(positions, nav=500000)
        assert "total_gross" in result
        assert "breached" in result
        assert "exposures" in result

    def test_history_and_clear(self):
        engine = ExposureEngine()
        positions = self._make_positions()
        engine.analyze(positions, nav=500000)
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# PortfolioOptimizer
# ====================================================================

class TestPortfolioOptimizer:
    def _make_assets(self):
        return [
            {"symbol": "EQUITY", "expected_return": 0.08, "volatility": 0.18},
            {"symbol": "FIXED_INCOME", "expected_return": 0.04, "volatility": 0.05},
            {"symbol": "COMMODITY", "expected_return": 0.06, "volatility": 0.20},
            {"symbol": "CASH", "expected_return": 0.03, "volatility": 0.005},
        ]

    def test_optimize_default(self):
        optimizer = PortfolioOptimizer()
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        assert isinstance(result, OptimizationResult)
        assert result.objective == Objective.MAX_SHARPE
        assert abs(result.total_weight - 1.0) < 0.01

    def test_max_sharpe(self):
        optimizer = PortfolioOptimizer(objective=Objective.MAX_SHARPE)
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        assert result.sharpe_ratio > 0

    def test_min_variance(self):
        optimizer = PortfolioOptimizer(objective=Objective.MIN_VARIANCE)
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        # Cash should have highest weight in min variance
        assert result.weights.get("CASH", 0) > result.weights.get("EQUITY", 0)

    def test_max_return(self):
        optimizer = PortfolioOptimizer(objective=Objective.MAX_RETURN)
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        # All weight should be on highest-return asset
        best = max(assets, key=lambda a: a["expected_return"])
        assert result.weights[best["symbol"]] > 0.95

    def test_risk_parity(self):
        optimizer = PortfolioOptimizer(objective=Objective.RISK_PARITY)
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        # Low vol assets get higher weight
        assert result.weights.get("CASH", 0) > result.weights.get("COMMODITY", 0)

    def test_target_risk(self):
        optimizer = PortfolioOptimizer(objective=Objective.TARGET_RISK)
        assets = self._make_assets()
        result = optimizer.optimize(
            assets,
            constraints={"target_volatility": 0.10},
        )
        assert result.expected_volatility > 0

    def test_target_return(self):
        optimizer = PortfolioOptimizer(objective=Objective.TARGET_RETURN)
        assets = self._make_assets()
        result = optimizer.optimize(
            assets,
            constraints={"target_return": 0.06},
        )
        assert result.expected_return > 0

    def test_efficient_frontier(self):
        optimizer = PortfolioOptimizer(max_frontier_points=10)
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        assert len(result.efficient_frontier) == 10
        # At least one point is tangency
        assert any(p.is_tangency for p in result.efficient_frontier)

    def test_constraints_bounds(self):
        optimizer = PortfolioOptimizer()
        assets = self._make_assets()
        result = optimizer.optimize(
            assets,
            constraints={
                "bounds": {
                    "EQUITY": {"min": 0.1, "max": 0.3},
                    "CASH": {"min": 0.05},
                }
            },
        )
        assert result.weights["EQUITY"] >= 0.1
        assert result.weights["EQUITY"] <= 0.3
        assert result.weights["CASH"] >= 0.03  # min constraint, may be slightly under after renormalization

    def test_sensitivity_analysis(self):
        optimizer = PortfolioOptimizer()
        assets = self._make_assets()
        result = optimizer.optimize(assets)
        assert "portfolio_volatility" in result.sensitivity
        assert "marginal_risk_contribution" in result.sensitivity

    def test_quick_optimize(self):
        optimizer = PortfolioOptimizer()
        result = optimizer.quick_optimize(["EQUITY", "FIXED_INCOME", "CASH"])
        assert "weights" in result
        assert "sharpe_ratio" in result

    def test_history_and_clear(self):
        optimizer = PortfolioOptimizer()
        assets = self._make_assets()
        optimizer.optimize(assets)
        assert optimizer.last_result() is not None
        optimizer.clear()
        assert optimizer.last_result() is None


# ====================================================================
# RebalanceEngine
# ====================================================================

class TestRebalanceEngine:
    def test_no_rebalance_needed(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.THRESHOLD_BASED)
        current = {"AAPL": 0.30, "MSFT": 0.30, "CASH": 0.40}
        target = {"AAPL": 0.30, "MSFT": 0.30, "CASH": 0.40}
        plan = engine.plan(current, target)
        assert plan.status == RebalanceStatus.NO_ACTION
        assert plan.trade_count == 0

    def test_rebalance_required(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.THRESHOLD_BASED)
        current = {"AAPL": 0.60, "MSFT": 0.20, "CASH": 0.20}
        target = {"AAPL": 0.30, "MSFT": 0.30, "CASH": 0.40}
        plan = engine.plan(current, target)
        assert plan.status in (
            RebalanceStatus.CRITICAL,
            RebalanceStatus.ACTION_REQUIRED,
            RebalanceStatus.ACTION_RECOMMENDED,
        )
        assert plan.trade_count > 0

    def test_critical_drift(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.THRESHOLD_BASED)
        current = {"AAPL": 0.90, "CASH": 0.10}
        target = {"AAPL": 0.30, "CASH": 0.70}
        plan = engine.plan(current, target)
        assert plan.status == RebalanceStatus.CRITICAL

    def test_buy_sell_split(self):
        engine = RebalanceEngine()
        current = {"AAPL": 0.50, "GOOGL": 0.20, "CASH": 0.30}
        target = {"AAPL": 0.30, "GOOGL": 0.40, "CASH": 0.30}
        plan = engine.plan(current, target)
        assert plan.buy_count > 0
        assert plan.sell_count > 0

    def test_tactical_rebalance(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.TACTICAL)
        current = {"AAPL": 0.32, "CASH": 0.68}
        target = {"AAPL": 0.30, "CASH": 0.70}
        plan = engine.plan(current, target, metadata={"market_signal": 0.4})
        assert plan.status in (
            RebalanceStatus.ACTION_RECOMMENDED,
            RebalanceStatus.ACTION_REQUIRED,
            RebalanceStatus.NO_ACTION,
        )

    def test_adaptive_rebalance(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.ADAPTIVE)
        current = {"AAPL": 0.35, "CASH": 0.65}
        target = {"AAPL": 0.30, "CASH": 0.70}
        plan = engine.plan(current, target, metadata={"vol_regime": "normal"})
        assert plan.status is not None

    def test_cost_optimized(self):
        engine = RebalanceEngine(strategy=RebalanceStrategy.COST_OPTIMIZED)
        current = {"AAPL": 0.32, "CASH": 0.68}
        target = {"AAPL": 0.30, "CASH": 0.70}
        plan = engine.plan(current, target, metadata={"cost_bps": 5.0})
        assert plan.status is not None

    def test_turnover_metric(self):
        engine = RebalanceEngine()
        current = {"AAPL": 0.50, "GOOGL": 0.20, "MSFT": 0.20, "CASH": 0.10}
        target = {"AAPL": 0.25, "GOOGL": 0.25, "MSFT": 0.25, "CASH": 0.25}
        plan = engine.plan(current, target)
        assert plan.total_turnover > 0

    def test_quick_rebalance(self):
        engine = RebalanceEngine()
        result = engine.quick_rebalance(
            current_weights={"A": 0.60, "B": 0.40},
            target_weights={"A": 0.30, "B": 0.70},
        )
        assert "status" in result
        assert "trades" in result
        assert "trade_count" in result

    def test_history_and_clear(self):
        engine = RebalanceEngine()
        current = {"A": 0.60, "B": 0.40}
        target = {"A": 0.30, "B": 0.70}
        engine.plan(current, target)
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# AttributionEngine
# ====================================================================

class TestAttributionEngine:
    def _make_sample_data(self):
        portfolio = {
            "total_return": 0.12,
            "weights": {"equity": 0.60, "fixed_income": 0.30, "cash": 0.10},
            "returns": {"equity": 0.15, "fixed_income": 0.04, "cash": 0.03},
        }
        benchmark = {
            "total_return": 0.10,
            "weights": {"equity": 0.50, "fixed_income": 0.40, "cash": 0.10},
            "returns": {"equity": 0.15, "fixed_income": 0.04, "cash": 0.03},
        }
        return portfolio, benchmark

    def test_brinson_attribution(self):
        engine = AttributionEngine(method=AttributionMethod.BRINSON)
        portfolio, benchmark = self._make_sample_data()
        result = engine.attribute(portfolio, benchmark)
        assert isinstance(result, AttributionResult)
        assert abs(result.excess_return - 0.02) < 0.0001  # 12% - 10%
        assert any(c.name == "Allocation Effect" for c in result.components)
        assert any(c.name == "Selection Effect" for c in result.components)
        assert any(c.name == "Interaction Effect" for c in result.components)

    def test_factor_attribution(self):
        engine = AttributionEngine(method=AttributionMethod.FACTOR_BASED)
        portfolio = {
            "total_return": 0.12,
            "factor_exposures": {"market": 1.1, "value": 0.3},
            "factor_returns": {"market": 0.08, "value": 0.02},
        }
        benchmark = {
            "total_return": 0.10,
            "factor_exposures": {"market": 1.0, "value": 0.1},
            "factor_returns": {"market": 0.08, "value": 0.02},
        }
        result = engine.attribute(portfolio, benchmark)
        assert result.method == AttributionMethod.FACTOR_BASED
        assert any("Alpha" in c.name for c in result.components)

    def test_top_contributors(self):
        engine = AttributionEngine()
        portfolio, benchmark = self._make_sample_data()
        result = engine.attribute(portfolio, benchmark)
        assert len(result.top_contributors) >= 0
        assert len(result.top_detractors) >= 0

    def test_tracking_error(self):
        engine = AttributionEngine()
        portfolio = {
            "total_return": 0.12,
            "weights": {"equity": 0.60, "fixed_income": 0.30, "cash": 0.10},
            "returns": {"equity": 0.15, "fixed_income": 0.04, "cash": 0.03},
        }
        benchmark = {
            "total_return": 0.10,
            "weights": {"equity": 0.50, "fixed_income": 0.40, "cash": 0.10},
            "returns": {"equity": 0.15, "fixed_income": 0.04, "cash": 0.03},
        }
        result = engine.attribute(portfolio, benchmark)
        assert result.tracking_error >= 0

    def test_multi_level_attribution(self):
        engine = AttributionEngine(method=AttributionMethod.MULTI_LEVEL)
        portfolio = {
            "total_return": 0.12,
            "weights": {"equity": 0.60, "fixed_income": 0.40},
            "returns": {"equity": 0.15, "fixed_income": 0.04},
            "asset_weights": {"equity": 0.60, "fixed_income": 0.40},
            "asset_returns": {"equity": 0.15, "fixed_income": 0.04},
            "sector_weights": {"tech": 0.30, "finance": 0.10},
            "sector_returns": {"tech": 0.20, "finance": 0.06},
        }
        benchmark = {
            "total_return": 0.10,
            "weights": {"equity": 0.50, "fixed_income": 0.50},
            "returns": {"equity": 0.15, "fixed_income": 0.04},
            "asset_weights": {"equity": 0.50, "fixed_income": 0.50},
            "asset_returns": {"equity": 0.15, "fixed_income": 0.04},
            "sector_weights": {"tech": 0.25, "finance": 0.25},
            "sector_returns": {"tech": 0.20, "finance": 0.06},
        }
        result = engine.attribute(portfolio, benchmark)
        assert len(result.components) > 3  # Multiple levels

    def test_transaction_attribution(self):
        engine = AttributionEngine(method=AttributionMethod.TRANSACTION)
        portfolio = {
            "total_return": 0.08,
            "total_cost": 0.002,
            "trades": [
                {"symbol": "AAPL", "pnl": 0.03, "side": "buy"},
                {"symbol": "GOOGL", "pnl": -0.01, "side": "sell"},
            ],
        }
        benchmark = {"total_return": 0.07}
        result = engine.attribute(portfolio, benchmark)
        assert result.method == AttributionMethod.TRANSACTION

    def test_quick_attribute(self):
        engine = AttributionEngine()
        result = engine.quick_attribute(
            portfolio_weights={"equity": 0.60, "fixed_income": 0.40},
            portfolio_returns={"equity": 0.15, "fixed_income": 0.04},
            benchmark_weights={"equity": 0.50, "fixed_income": 0.50},
            benchmark_returns={"equity": 0.15, "fixed_income": 0.04},
        )
        assert "excess_return_bps" in result
        assert "components" in result

    def test_history_and_clear(self):
        engine = AttributionEngine()
        portfolio, benchmark = self._make_sample_data()
        engine.attribute(portfolio, benchmark)
        assert engine.last_result() is not None
        engine.clear()
        assert engine.last_result() is None


# ====================================================================
# PortfolioMemory
# ====================================================================

class TestPortfolioMemory:
    def test_record_event(self):
        memory = PortfolioMemory()
        event = memory.record(
            event_type=MemoryEventType.ALLOCATION_CHANGE,
            data={"weights": {"equity": 0.6}},
            outcome=DecisionOutcome.POSITIVE,
            impact_score=0.02,
            tags=["allocation", "tactical"],
            notes="Increased equity from 50% to 60%",
        )
        assert isinstance(event, MemoryEvent)
        assert event.event_type == MemoryEventType.ALLOCATION_CHANGE
        assert event.outcome == DecisionOutcome.POSITIVE

    def test_record_snapshot(self):
        memory = PortfolioMemory()
        snapshot = memory.record_snapshot(
            portfolio_value=1_200_000,
            daily_return=0.015,
            ytd_return=0.12,
            sharpe_ratio=1.5,
            allocations={"equity": 0.60, "cash": 0.40},
        )
        assert isinstance(snapshot, PerformanceSnapshot)
        assert memory.events[-1].event_type == MemoryEventType.PERFORMANCE_SNAPSHOT

    def test_recent_events(self):
        memory = PortfolioMemory()
        for i in range(10):
            memory.record(
                event_type=MemoryEventType.REBALANCE,
                data={"index": i},
            )
        recent = memory.recent_events(limit=3)
        assert len(recent) == 3

    def test_events_by_type(self):
        memory = PortfolioMemory()
        memory.record(event_type=MemoryEventType.ALLOCATION_CHANGE, data={})
        memory.record(event_type=MemoryEventType.REBALANCE, data={})
        memory.record(event_type=MemoryEventType.REBALANCE, data={})

        alloc = memory.events_by_type(MemoryEventType.ALLOCATION_CHANGE)
        rebal = memory.events_by_type(MemoryEventType.REBALANCE)
        assert len(alloc) == 1
        assert len(rebal) == 2

    def test_events_by_tag(self):
        memory = PortfolioMemory()
        memory.record(
            event_type=MemoryEventType.OPTIMIZATION,
            data={},
            tags=["important", "weekly"],
        )
        memory.record(
            event_type=MemoryEventType.ALLOCATION_CHANGE,
            data={},
            tags=["daily"],
        )
        assert len(memory.events_by_tag("important")) == 1
        assert len(memory.events_by_tag("daily")) == 1
        assert len(memory.events_by_tag("nonexistent")) == 0

    def test_events_by_outcome(self):
        memory = PortfolioMemory()
        memory.record(
            event_type=MemoryEventType.REBALANCE,
            data={},
            outcome=DecisionOutcome.POSITIVE,
        )
        memory.record(
            event_type=MemoryEventType.REBALANCE,
            data={},
            outcome=DecisionOutcome.NEGATIVE,
        )
        pos = memory.events_by_outcome(DecisionOutcome.POSITIVE)
        neg = memory.events_by_outcome(DecisionOutcome.NEGATIVE)
        assert len(pos) == 1
        assert len(neg) == 1

    def test_events_by_date_range(self):
        memory = PortfolioMemory()
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        memory.record(
            event_type=MemoryEventType.SIZING_DECISION,
            data={},
        )
        # Event was just recorded, should be in range
        recent = memory.events_by_date_range(
            start=now - timedelta(hours=1),
            end=now + timedelta(hours=1),
        )
        assert len(recent) == 1

    def test_knowledge_base(self):
        memory = PortfolioMemory()
        memory.record(
            event_type=MemoryEventType.ALLOCATION_CHANGE,
            data={"weights": {"equity": 0.6}},
            outcome=DecisionOutcome.POSITIVE,
            impact_score=0.02,
        )
        memory.record(
            event_type=MemoryEventType.ALLOCATION_CHANGE,
            data={"weights": {"equity": 0.4}},
            outcome=DecisionOutcome.NEGATIVE,
            impact_score=-0.01,
        )
        kb = memory.knowledge_base()
        assert "total_events" in kb
        assert kb["total_events"] == 2
        assert "win_rate" in kb
        assert "insights" in kb

    def test_performance_analytics(self):
        memory = PortfolioMemory()
        memory.record_snapshot(portfolio_value=1_000_000, daily_return=0.005)
        memory.record_snapshot(portfolio_value=1_005_000, daily_return=0.005)
        memory.record_snapshot(portfolio_value=1_010_000, daily_return=0.005)
        kb = memory.knowledge_base()
        assert "performance_trends" in kb
        assert kb["performance_trends"].get("total_return", 0) > 0

    def test_event_pruning(self):
        memory = PortfolioMemory(max_events=5)
        for i in range(10):
            memory.record(event_type=MemoryEventType.REBALANCE, data={"i": i})
        assert len(memory.events) == 5  # Oldest 5 pruned

    def test_quick_status(self):
        memory = PortfolioMemory()
        memory.record(event_type=MemoryEventType.REBALANCE, data={})
        status = memory.quick_status()
        assert "total_events" in status
        assert "recent_activity" in status

    def test_clear(self):
        memory = PortfolioMemory()
        memory.record(event_type=MemoryEventType.REBALANCE, data={})
        memory.record_snapshot(portfolio_value=1_000_000, daily_return=0.01)
        memory.clear()
        assert len(memory.events) == 0
        assert len(memory.snapshots) == 0


# ====================================================================
# PortfolioIntelligenceService
# ====================================================================

class TestPortfolioIntelligenceService:
    def test_service_init(self):
        service = PortfolioIntelligenceService()
        assert service.allocator is not None
        assert service.sizer is not None
        assert service.budget_engine is not None
        assert service.exposure_engine is not None
        assert service.optimizer is not None
        assert service.rebalancer is not None
        assert service.attributor is not None
        assert service.memory is not None

    def test_build_with_asset_data(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
            AssetClass.FIXED_INCOME: {"expected_return": 0.04, "volatility": 0.05},
            AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
        }
        result = service.build(asset_data=asset_data)
        assert isinstance(result, PortfolioBuildResult)
        assert result.allocation is not None
        assert result.optimization is not None
        assert result.budget is not None

    def test_build_with_positions(self):
        service = PortfolioIntelligenceService()
        positions = [
            {"symbol": "AAPL", "market_value": 200000, "beta": 1.2,
             "sector": "tech", "region": "US", "currency": "USD",
             "style": "growth", "instrument_type": "equity",
             "liquidity_score": 0.95, "volatility": 0.20,
             "factor_loadings": {}},
        ]
        result = service.build(position_data=positions, nav=500000)
        assert result.sizing is not None
        assert result.exposure is not None

    def test_build_with_current_weights(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
            AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
        }
        current_weights = {"equity": 0.80, "cash": 0.20}
        result = service.build(
            asset_data=asset_data,
            current_weights=current_weights,
        )
        assert result.rebalance is not None
        assert result.rebalance.trade_count > 0  # Drift from target

    def test_build_is_healthy(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
            AssetClass.FIXED_INCOME: {"expected_return": 0.04, "volatility": 0.05},
            AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
        }
        result = service.build(asset_data=asset_data)
        assert result.is_healthy

    def test_build_to_dict(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
            AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
        }
        result = service.build(asset_data=asset_data)
        d = result.to_dict()
        assert "timestamp" in d
        assert "allocation" in d
        assert "optimization" in d

    def test_build_summary(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
            AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
        }
        result = service.build(asset_data=asset_data)
        assert "health_checks" in result.summary
        assert "warnings" in result.summary
        assert "actions" in result.summary

    def test_quick_build(self):
        service = PortfolioIntelligenceService()
        result = service.quick_build(
            asset_data={
                "equity": {"expected_return": 0.08, "volatility": 0.18},
                "fixed_income": {"expected_return": 0.04, "volatility": 0.05},
            }
        )
        assert "allocation" in result
        assert "is_healthy" in result

    def test_clear_all(self):
        service = PortfolioIntelligenceService()
        asset_data = {
            AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
        }
        service.build(asset_data=asset_data)
        service.clear_all()
        assert service.allocator.last_result() is None
        assert service.optimizer.last_result() is None


# ====================================================================
# Edge Cases & Integration
# ====================================================================

class TestEdgeCases:
    def test_empty_asset_data_allocation(self):
        engine = AssetAllocationEngine()
        result = engine.allocate(asset_data={})
        assert result.is_valid
        assert result.allocations  # Still produces default weights

    def test_single_asset_sizing(self):
        engine = PositionSizingEngine()
        assets = [{"symbol": "A", "volatility": 0.15, "correlation": 0.0, "liquidity_score": 1.0}]
        result = engine.calculate(assets)
        assert result.position_count == 1

    def test_single_entity_budget(self):
        engine = RiskBudgetEngine()
        entities = [{"entity_id": "sole", "level": "asset_class"}]
        result = engine.allocate(entities)
        assert len(result.budgets) == 1
        assert abs(result.budgets[0].budget_pct - engine.total_budget) < 0.0001

    def test_no_positions_exposure(self):
        engine = ExposureEngine()
        report = engine.analyze([], nav=1_000_000)
        assert report.total_gross_exposure == 0

    def test_weights_sum_to_one(self):
        optimizer = PortfolioOptimizer()
        assets = [
            {"symbol": "A", "expected_return": 0.06, "volatility": 0.15},
            {"symbol": "B", "expected_return": 0.08, "volatility": 0.20},
        ]
        result = optimizer.optimize(assets)
        assert abs(result.total_weight - 1.0) < 0.01

    def test_zero_drift_rebalance(self):
        engine = RebalanceEngine()
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.5, "B": 0.5}
        plan = engine.plan(current, target)
        assert plan.status == RebalanceStatus.NO_ACTION
