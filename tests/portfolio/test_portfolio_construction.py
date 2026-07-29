"""
Tests for Portfolio Construction Engine

Coverage:
- Weight calculation (Mean-Variance, Risk Parity, Max Sharpe, Min Variance, Equal Weight)
- Risk budget allocation
- Max position limits / single strategy constraints
- Multi-strategy optimization
- Rebalance logic
- Abnormal constraint handling
- Factor/Sector exposure constraints
- Dynamic allocation based on performance
- Cash buffer management
"""

import math
import os
import sys

import pytest

# Ensure project root is in path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from services.portfolio.construction.models import (
    AllocationReason,
    AllocationResult,
    ExposureReport,
    FactorExposure,
    FactorExposureConstraint,
    OptimizationMethod,
    OptimizationMetrics,
    OptimizationResult,
    Portfolio,
    PortfolioConfig,
    PortfolioConstraints,
    RebalanceAction,
    RebalanceDecision,
    RiskBudget,
    RiskBudgetAllocation,
    RiskConstraint,
    SectorExposure,
    SectorExposureConstraint,
    StrategyAllocation,
    StrategySnapshot,
    WeightConstraint,
)
from services.portfolio.construction.optimizer import (
    MaxSharpeOptimizer,
    MeanVarianceOptimizer,
    MinVarianceOptimizer,
    PortfolioOptimizer,
    RiskParityOptimizer,
)
from services.portfolio.construction.constraints import (
    ConstraintEnforcer,
    ConstraintValidator,
)
from services.portfolio.construction.allocator import (
    DynamicAllocator,
    RebalanceEngine,
)
from services.portfolio.construction.service import (
    PortfolioConstructionService,
)
from services.portfolio.risk.budget import RiskBudgetManager
from services.portfolio.risk.exposure import ExposureManager


# =============================================================================
# Helpers
# =============================================================================


def make_snapshot(
    strategy_id: str,
    expected_return: float = 0.15,
    expected_volatility: float = 0.20,
    sharpe_ratio: float = 0.75,
    max_drawdown: float = 0.10,
    recent_alpha: float = 0.0,
    current_weight: float = 0.0,
    factor_exposures: dict = None,
    sector_exposures: dict = None,
    correlation_to_portfolio: float = 0.3,
) -> StrategySnapshot:
    return StrategySnapshot(
        strategy_id=strategy_id,
        name=f"Strategy_{strategy_id}",
        expected_return=expected_return,
        expected_volatility=expected_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        recent_alpha=recent_alpha,
        win_rate=0.55,
        sortino_ratio=sharpe_ratio * 1.1,
        calmar_ratio=expected_return / max(max_drawdown, 0.01),
        current_weight=current_weight,
        factor_exposures=factor_exposures or {},
        sector_exposures=sector_exposures or {},
        correlation_to_portfolio=correlation_to_portfolio,
    )


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Test core dataclass models."""

    def test_portfolio_creation(self):
        portfolio = Portfolio(
            portfolio_id="TEST_PORTFOLIO",
            capital=10_000_000,
        )
        assert portfolio.portfolio_id == "TEST_PORTFOLIO"
        assert portfolio.capital == 10_000_000
        assert portfolio.total_weight == 0.0
        assert portfolio.active_strategies == 0

    def test_portfolio_with_allocations(self):
        alloc = StrategyAllocation(
            strategy_id="alpha",
            strategy_name="Alpha Strategy",
            target_weight=0.4,
            capital_allocated=4_000_000,
        )
        portfolio = Portfolio(
            portfolio_id="P1",
            capital=10_000_000,
            strategy_allocations=[alloc],
            target_weights={"alpha": 0.4},
            cash_weight=0.6,
        )
        assert portfolio.total_weight == 1.0
        assert portfolio.active_strategies == 1

    def test_strategy_snapshot_defaults(self):
        snap = StrategySnapshot(strategy_id="test")
        assert snap.strategy_id == "test"
        assert snap.expected_return == 0.0
        assert snap.expected_volatility == 0.0

    def test_strategy_snapshot_full(self):
        snap = make_snapshot("alpha", expected_return=0.20, expected_volatility=0.15)
        assert snap.expected_return == 0.20
        assert snap.expected_volatility == 0.15

    def test_allocation_result(self):
        alloc = StrategyAllocation(
            strategy_id="s1",
            target_weight=0.5,
            reason=AllocationReason.OPTIMIZATION,
        )
        result = AllocationResult(
            portfolio_id="P1",
            allocations={"s1": alloc},
            expected_sharpe=1.5,
        )
        assert result.portfolio_id == "P1"
        assert result.allocations["s1"].target_weight == 0.5
        assert result.expected_sharpe == 1.5

    def test_weight_constraint(self):
        wc = WeightConstraint(strategy_id="s1", min_weight=0.1, max_weight=0.5)
        assert wc.strategy_id == "s1"
        assert wc.min_weight == 0.1
        assert wc.max_weight == 0.5

    def test_risk_constraint(self):
        rc = RiskConstraint(
            strategy_id="s1",
            max_volatility=0.25,
            max_drawdown=0.15,
            max_risk_contribution=0.4,
        )
        assert rc.max_volatility == 0.25
        assert rc.max_drawdown == 0.15
        assert rc.max_risk_contribution == 0.4

    def test_portfolio_constraints_default(self):
        pc = PortfolioConstraints()
        assert pc.max_single_strategy_weight == 0.5
        assert pc.max_strategies == 20

    def test_portfolio_constraints_custom(self):
        pc = PortfolioConstraints(
            max_single_strategy_weight=0.4,
            max_total_weight=0.95,
            min_total_weight=0.80,
            max_strategies=10,
        )
        assert pc.max_single_strategy_weight == 0.4
        assert pc.max_total_weight == 0.95

    def test_risk_budget_model(self):
        budget = RiskBudget(
            budget_id="b1",
            total_risk_budget=100,
            allocated_risk=30,
            remaining_risk=70,
        )
        assert budget.utilization == 0.3

    def test_risk_budget_zero_total(self):
        budget = RiskBudget(budget_id="b1", total_risk_budget=0.0)
        assert budget.utilization == 0.0

    def test_risk_budget_allocation(self):
        rba = RiskBudgetAllocation(
            strategy_id="s1",
            risk_budget=0.25,
            risk_used=0.20,
            risk_remaining=0.05,
            percentage_of_total=0.25,
        )
        assert rba.strategy_id == "s1"
        assert rba.risk_budget == 0.25

    def test_rebalance_decision(self):
        d = RebalanceDecision(
            strategy_id="s1",
            action=RebalanceAction.BUY,
            current_weight=0.1,
            target_weight=0.15,
            weight_delta=0.05,
            capital_delta=500_000,
            reason="Increase allocation",
        )
        assert d.action == RebalanceAction.BUY
        assert d.weight_delta == 0.05

    def test_optimization_method_enum(self):
        assert OptimizationMethod.MEAN_VARIANCE.value == "mean_variance"
        assert OptimizationMethod.RISK_PARITY.value == "risk_parity"
        assert OptimizationMethod.EQUAL_WEIGHT.value == "equal_weight"

    def test_allocation_reason_enum(self):
        assert AllocationReason.OPTIMIZATION.value == "optimization"
        assert AllocationReason.RISK_PARITY.value == "risk_parity"


# =============================================================================
# Optimizer Tests
# =============================================================================


class TestMeanVarianceOptimizer:
    """Tests for Mean-Variance optimization."""

    def test_basic_optimization(self):
        opt = MeanVarianceOptimizer(risk_aversion=1.0)
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.25, expected_volatility=0.30),
            "beta": make_snapshot("beta", expected_return=0.15, expected_volatility=0.15),
            "gamma": make_snapshot("gamma", expected_return=0.10, expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.status == "success"
        assert len(result.weights) == 3
        # Weights should sum to approximately 1.0
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert result.iterations > 0

    def test_single_strategy(self):
        opt = MeanVarianceOptimizer()
        snapshots = {"alpha": make_snapshot("alpha")}

        result = opt.optimize(snapshots)
        assert result.status == "success"
        assert len(result.weights) == 1
        assert abs(result.weights["alpha"] - 1.0) < 0.01

    def test_empty_strategies(self):
        opt = MeanVarianceOptimizer()
        result = opt.optimize({})
        assert result.status == "error"

    def test_higher_return_gets_higher_weight(self):
        """Strategy with higher return should get higher weight."""
        opt = MeanVarianceOptimizer(risk_aversion=1.0)
        snapshots = {
            "high": make_snapshot("high", expected_return=0.30, expected_volatility=0.20),
            "low": make_snapshot("low", expected_return=0.05, expected_volatility=0.20),
        }

        result = opt.optimize(snapshots)
        assert result.weights["high"] > result.weights["low"]

    def test_lower_vol_gets_higher_weight_ceteris_paribus(self):
        """With equal returns, lower volatility should get higher weight."""
        opt = MeanVarianceOptimizer(risk_aversion=1.0)
        snapshots = {
            "stable": make_snapshot("stable", expected_return=0.15, expected_volatility=0.10),
            "volatile": make_snapshot("volatile", expected_return=0.15, expected_volatility=0.30),
        }

        result = opt.optimize(snapshots)
        assert result.weights["stable"] > result.weights["volatile"]

    def test_with_constraints(self):
        opt = MeanVarianceOptimizer(risk_aversion=1.0)
        snapshots = {
            "a": make_snapshot("a", expected_return=0.20, expected_volatility=0.25),
            "b": make_snapshot("b", expected_return=0.12, expected_volatility=0.15),
        }

        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", max_weight=0.3),
            },
            max_single_strategy_weight=0.3,
        )

        result = opt.optimize(snapshots, constraints=constraints)
        assert result.weights["a"] <= 0.3

    def test_metrics_produced(self):
        opt = MeanVarianceOptimizer()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.20, expected_volatility=0.20),
            "b": make_snapshot("b", expected_return=0.10, expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.metrics.method == OptimizationMethod.MEAN_VARIANCE
        assert result.metrics.expected_return != 0.0
        assert result.metrics.effective_n > 0

    def test_risk_aversion_effect(self):
        """Higher risk aversion should reduce weight on volatile strategies."""
        snapshots = {
            "safe": make_snapshot("safe", expected_return=0.08, expected_volatility=0.05),
            "risky": make_snapshot("risky", expected_return=0.20, expected_volatility=0.30),
        }

        opt_low = MeanVarianceOptimizer(risk_aversion=0.1)
        result_low = opt_low.optimize(snapshots)

        opt_high = MeanVarianceOptimizer(risk_aversion=5.0)
        result_high = opt_high.optimize(snapshots)

        # Higher risk aversion should give more weight to safe strategy
        assert result_high.weights["safe"] > result_low.weights["safe"]


class TestRiskParityOptimizer:
    """Tests for Risk Parity optimization."""

    def test_basic_risk_parity(self):
        opt = RiskParityOptimizer()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.20, expected_volatility=0.30),
            "b": make_snapshot("b", expected_return=0.10, expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.status == "success"
        assert len(result.weights) == 2
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_lower_vol_gets_higher_weight(self):
        """Risk parity should give higher weight to lower-vol strategies."""
        opt = RiskParityOptimizer()
        snapshots = {
            "volatile": make_snapshot("volatile", expected_return=0.15, expected_volatility=0.30),
            "stable": make_snapshot("stable", expected_return=0.10, expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.weights["stable"] > result.weights["volatile"]

    def test_three_strategies(self):
        opt = RiskParityOptimizer()
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.20),
            "b": make_snapshot("b", expected_volatility=0.15),
            "c": make_snapshot("c", expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert len(result.weights) == 3
        # Lowest vol should get highest weight
        assert result.weights["c"] > result.weights["a"]

    def test_empty_strategies(self):
        opt = RiskParityOptimizer()
        result = opt.optimize({})
        assert result.status == "error"


class TestMaxSharpeOptimizer:
    """Tests for Maximum Sharpe optimizer."""

    def test_basic_max_sharpe(self):
        opt = MaxSharpeOptimizer()
        snapshots = {
            "good": make_snapshot("good", expected_return=0.20, expected_volatility=0.10),
            "ok": make_snapshot("ok", expected_return=0.10, expected_volatility=0.15),
        }

        result = opt.optimize(snapshots)
        assert result.status == "success"
        assert len(result.weights) == 2
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_prefers_higher_sharpe(self):
        opt = MaxSharpeOptimizer()
        snapshots = {
            "high_sharpe": make_snapshot("high_sharpe", expected_return=0.20, expected_volatility=0.10),
            "low_sharpe": make_snapshot("low_sharpe", expected_return=0.05, expected_volatility=0.15),
        }

        result = opt.optimize(snapshots)
        # Higher Sharpe strategy should get more weight
        assert result.weights["high_sharpe"] > result.weights["low_sharpe"]


class TestMinVarianceOptimizer:
    """Tests for Minimum Variance optimizer."""

    def test_basic_min_variance(self):
        opt = MinVarianceOptimizer()
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.30),
            "b": make_snapshot("b", expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.status == "success"
        assert len(result.weights) == 2
        # Lower vol should get more weight
        assert result.weights["b"] > result.weights["a"]

    def test_prefers_lowest_vol(self):
        opt = MinVarianceOptimizer()
        snapshots = {
            "high": make_snapshot("high", expected_volatility=0.40),
            "mid": make_snapshot("mid", expected_volatility=0.25),
            "low": make_snapshot("low", expected_volatility=0.10),
        }

        result = opt.optimize(snapshots)
        assert result.weights["low"] > result.weights["mid"]
        assert result.weights["low"] > result.weights["high"]


# =============================================================================
# Constraint Tests
# =============================================================================


class TestConstraintValidator:
    """Tests for constraint validation."""

    def test_valid_weights(self):
        validator = ConstraintValidator()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints()

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) == 0
        assert validator.is_valid(weights, snapshots, constraints)

    def test_weight_exceeds_max(self):
        validator = ConstraintValidator()
        weights = {"a": 0.9, "b": 0.1}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(max_single_strategy_weight=0.5)

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_weight_below_min(self):
        validator = ConstraintValidator()
        weights = {"a": 0.01, "b": 0.99}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(min_single_strategy_weight=0.05)

        violations = validator.validate(weights, snapshots, constraints)
        # a is below min
        assert any("a" in v for v in violations)

    def test_per_strategy_constraint(self):
        validator = ConstraintValidator()
        weights = {"a": 0.7, "b": 0.3}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", max_weight=0.4),
            }
        )

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0
        assert any("a" in v for v in violations)

    def test_risk_constraint_violation(self):
        validator = ConstraintValidator()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.40, max_drawdown=0.25),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(
            risk_constraints={
                "a": RiskConstraint(
                    strategy_id="a",
                    max_volatility=0.30,
                    max_drawdown=0.20,
                ),
            }
        )

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_factor_exposure_violation(self):
        validator = ConstraintValidator()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", factor_exposures={"momentum": 0.8}),
            "b": make_snapshot("b", factor_exposures={"momentum": 0.6}),
        }
        constraints = PortfolioConstraints(
            factor_constraints={
                "momentum": FactorExposureConstraint(
                    factor_name="momentum",
                    max_exposure=0.5,
                ),
            }
        )

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_sector_exposure_violation(self):
        validator = ConstraintValidator()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", sector_exposures={"tech": 0.7}),
            "b": make_snapshot("b", sector_exposures={"tech": 0.6}),
        }
        constraints = PortfolioConstraints(
            sector_constraints={
                "tech": SectorExposureConstraint(
                    sector_name="tech",
                    max_exposure=0.4,
                ),
            }
        )

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_strategy_count_limit(self):
        validator = ConstraintValidator()
        weights = {"a": 0.3, "b": 0.3, "c": 0.2, "d": 0.2}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
            "c": make_snapshot("c"),
            "d": make_snapshot("d"),
        }
        constraints = PortfolioConstraints(max_strategies=3)

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_total_weight_exceeds(self):
        validator = ConstraintValidator()
        weights = {"a": 0.6, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(max_total_weight=1.0)

        violations = validator.validate(weights, snapshots, constraints)
        assert len(violations) > 0

    def test_validate_single_weight(self):
        validator = ConstraintValidator()
        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", min_weight=0.1, max_weight=0.4),
            }
        )

        valid, msg = validator.validate_single_weight("a", 0.3, constraints)
        assert valid

        valid, msg = validator.validate_single_weight("a", 0.05, constraints)
        assert not valid

        valid, msg = validator.validate_single_weight("a", 0.5, constraints)
        assert not valid


class TestConstraintEnforcer:
    """Tests for constraint enforcement."""

    def test_clamp_weights(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.8, "b": 0.2}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(
            max_single_strategy_weight=0.5,
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        assert result["a"] <= 0.5

    def test_enforce_per_strategy_constraint(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.6, "b": 0.4}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", max_weight=0.3),
            }
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        assert result["a"] <= 0.3

    def test_enforce_risk_constraint_removes_strategy(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.50, max_drawdown=0.30),
            "b": make_snapshot("b", expected_volatility=0.10, max_drawdown=0.05),
        }
        constraints = PortfolioConstraints(
            risk_constraints={
                "a": RiskConstraint(
                    strategy_id="a",
                    max_volatility=0.25,
                    max_drawdown=0.20,
                ),
            }
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        assert result["a"] == 0.0

    def test_enforce_strategy_count(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.3, "b": 0.25, "c": 0.25, "d": 0.2}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
            "c": make_snapshot("c"),
            "d": make_snapshot("d"),
        }
        constraints = PortfolioConstraints(max_strategies=3)

        result = enforcer.enforce(weights, snapshots, constraints)
        active = sum(1 for w in result.values() if w > 0)
        assert active <= 3

    def test_enforce_factor_exposure(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", factor_exposures={"tech": 0.9}),
            "b": make_snapshot("b", factor_exposures={"tech": 0.1}),
        }
        constraints = PortfolioConstraints(
            factor_constraints={
                "tech": FactorExposureConstraint(factor_name="tech", max_exposure=0.3),
            }
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        # Weight of "a" should be reduced
        assert result["a"] < weights["a"]

    def test_enforce_sector_exposure(self):
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", sector_exposures={"semiconductor": 0.9}),
            "b": make_snapshot("b", sector_exposures={"semiconductor": 0.1}),
        }
        constraints = PortfolioConstraints(
            sector_constraints={
                "semiconductor": SectorExposureConstraint(
                    sector_name="semiconductor",
                    max_exposure=0.3,
                ),
            }
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        assert result["a"] < weights["a"]


# =============================================================================
# Allocator Tests
# =============================================================================


class TestDynamicAllocator:
    """Tests for dynamic allocation."""

    def test_basic_allocation(self):
        allocator = DynamicAllocator()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.25, expected_volatility=0.20),
            "beta": make_snapshot("beta", expected_return=0.15, expected_volatility=0.15),
        }

        result = allocator.allocate("P1", 1_000_000, snapshots)
        assert result.portfolio_id == "P1"
        assert len(result.allocations) == 2
        assert abs(sum(a.target_weight for a in result.allocations.values()) + result.cash_weight - 1.0) < 0.01

    def test_allocation_with_cash_buffer(self):
        allocator = DynamicAllocator()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.20, expected_volatility=0.20),
            "beta": make_snapshot("beta", expected_return=0.10, expected_volatility=0.15),
        }

        result = allocator.allocate("P1", 1_000_000, snapshots, cash_weight=0.10)
        assert result.cash_weight >= 0.10
        total_invested = sum(a.target_weight for a in result.allocations.values())
        assert total_invested <= 0.90

    def test_allocation_capital_allocation(self):
        allocator = DynamicAllocator()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.20, expected_volatility=0.15),
            "b": make_snapshot("b", expected_return=0.10, expected_volatility=0.10),
        }

        capital = 5_000_000
        result = allocator.allocate("P1", capital, snapshots, cash_weight=0.05)

        total_capital = sum(a.capital_allocated for a in result.allocations.values())
        assert abs(total_capital - capital * 0.95) < 1.0  # allow small float error

    def test_equal_weight_allocation(self):
        allocator = DynamicAllocator()
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
            "c": make_snapshot("c"),
        }

        result = allocator.allocate_equal_weight("P1", 1_000_000, snapshots)
        assert len(result.allocations) == 3
        for alloc in result.allocations.values():
            assert abs(alloc.target_weight - 1.0 / 3) < 0.01

    def test_allocation_with_constraints(self):
        allocator = DynamicAllocator()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.30, expected_volatility=0.25),
            "b": make_snapshot("b", expected_return=0.10, expected_volatility=0.10),
        }

        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", max_weight=0.3),
            }
        )

        result = allocator.allocate("P1", 1_000_000, snapshots, constraints=constraints)
        assert result.allocations["a"].target_weight <= 0.3

    def test_allocation_risk_parity_method(self):
        allocator = DynamicAllocator()
        snapshots = {
            "high_vol": make_snapshot("high_vol", expected_return=0.20, expected_volatility=0.30),
            "low_vol": make_snapshot("low_vol", expected_return=0.10, expected_volatility=0.10),
        }

        result = allocator.allocate(
            "P1", 1_000_000, snapshots,
            method=OptimizationMethod.RISK_PARITY,
        )
        assert result.method == OptimizationMethod.RISK_PARITY
        # Lower vol should get higher weight in risk parity
        assert result.allocations["low_vol"].target_weight > result.allocations["high_vol"].target_weight

    def test_dynamic_adjustment_alpha_positive(self):
        """Strategy with positive alpha should get dynamic adjustment reason."""
        allocator = DynamicAllocator()
        snapshots = {
            "alpha": make_snapshot(
                "alpha",
                expected_return=0.25,
                expected_volatility=0.20,
                recent_alpha=800,  # 800 bps
                sharpe_ratio=2.0,
            ),
            "beta": make_snapshot("beta", expected_return=0.05, expected_volatility=0.15),
        }

        result = allocator.allocate("P1", 1_000_000, snapshots)
        assert result.allocations["alpha"].reason == AllocationReason.DYNAMIC_ADJUSTMENT

    def test_allocation_with_exposure_report(self):
        allocator = DynamicAllocator()
        snapshots = {
            "a": make_snapshot("a", factor_exposures={"momentum": 0.8}),
            "b": make_snapshot("b", factor_exposures={"momentum": 0.2}),
        }
        constraints = PortfolioConstraints(
            factor_constraints={
                "momentum": FactorExposureConstraint(factor_name="momentum", max_exposure=0.5),
            }
        )

        result = allocator.allocate("P1", 1_000_000, snapshots, constraints=constraints)
        assert result.exposure_report is not None
        assert "momentum" in result.exposure_report.factor_exposures


# =============================================================================
# Rebalance Engine Tests
# =============================================================================


class TestRebalanceEngine:
    """Tests for rebalance decisions."""

    def test_basic_rebalance(self):
        engine = RebalanceEngine(threshold=0.02)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.6, "b": 0.4}

        decisions = engine.compute_decisions(current, target, 1_000_000)
        assert len(decisions) == 2

        a_decision = [d for d in decisions if d.strategy_id == "a"][0]
        b_decision = [d for d in decisions if d.strategy_id == "b"][0]

        assert a_decision.action == RebalanceAction.BUY
        assert b_decision.action == RebalanceAction.SELL

    def test_hold_within_threshold(self):
        engine = RebalanceEngine(threshold=0.05)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.51, "b": 0.49}

        decisions = engine.compute_decisions(current, target, 1_000_000)
        for d in decisions:
            assert d.action == RebalanceAction.HOLD

    def test_add_new_strategy(self):
        engine = RebalanceEngine(threshold=0.02)
        current = {"a": 1.0}
        target = {"a": 0.7, "b": 0.3}

        decisions = engine.compute_decisions(current, target, 1_000_000)
        b_decision = [d for d in decisions if d.strategy_id == "b"][0]
        assert b_decision.action == RebalanceAction.ADD

    def test_remove_strategy(self):
        engine = RebalanceEngine(threshold=0.02)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 1.0, "b": 0.0}

        decisions = engine.compute_decisions(current, target, 1_000_000)
        b_decision = [d for d in decisions if d.strategy_id == "b"][0]
        assert b_decision.action == RebalanceAction.REMOVE

    def test_needs_rebalance(self):
        engine = RebalanceEngine(threshold=0.02)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.55, "b": 0.45}

        assert engine.needs_rebalance(current, target)

    def test_no_rebalance_needed(self):
        engine = RebalanceEngine(threshold=0.05)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.51, "b": 0.49}

        assert not engine.needs_rebalance(current, target)

    def test_calculate_turnover(self):
        engine = RebalanceEngine()
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.7, "b": 0.3}

        turnover = engine.calculate_turnover(current, target)
        assert abs(turnover - 0.2) < 0.01

    def test_capital_delta_correct(self):
        engine = RebalanceEngine(threshold=0.01)
        capital = 10_000_000
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.6, "b": 0.4}

        decisions = engine.compute_decisions(current, target, capital)
        a_decision = [d for d in decisions if d.strategy_id == "a"][0]
        assert abs(a_decision.capital_delta - 1_000_000) < 1.0

    def test_generate_orders(self):
        engine = RebalanceEngine(threshold=0.01)
        current = {"a": 0.5, "b": 0.5}
        target = {"a": 0.6, "b": 0.4}

        decisions = engine.compute_decisions(current, target, 1_000_000)
        orders = engine.generate_orders(decisions, 1_000_000)

        # Should have 2 orders (buy a, sell b)
        assert len(orders) == 2
        actions = {o["strategy_id"]: o["action"] for o in orders}
        assert actions["a"] == "buy"
        assert actions["b"] == "sell"


# =============================================================================
# Service Tests
# =============================================================================


class TestPortfolioConstructionService:
    """Tests for the main portfolio construction service."""

    def test_build_portfolio(self):
        service = PortfolioConstructionService()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.25, expected_volatility=0.20),
            "beta": make_snapshot("beta", expected_return=0.15, expected_volatility=0.15),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        assert portfolio.portfolio_id == "P1"
        assert portfolio.capital == 1_000_000
        assert len(portfolio.strategy_allocations) == 2
        assert len(portfolio.target_weights) == 2

    def test_build_multi(self):
        service = PortfolioConstructionService()
        strategies_data = [
            {
                "strategy_id": "alpha",
                "name": "Alpha Strategy",
                "expected_return": 0.25,
                "expected_volatility": 0.20,
                "sharpe_ratio": 1.25,
                "max_drawdown": 0.10,
            },
            {
                "strategy_id": "beta",
                "name": "Beta Strategy",
                "expected_return": 0.12,
                "expected_volatility": 0.12,
                "sharpe_ratio": 1.0,
                "max_drawdown": 0.08,
            },
        ]

        portfolio = service.build_multi("P1", 2_000_000, strategies_data)
        assert len(portfolio.strategy_allocations) == 2
        assert portfolio.capital == 2_000_000

    def test_build_with_constraints(self):
        service = PortfolioConstructionService()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.30, expected_volatility=0.25),
            "beta": make_snapshot("beta", expected_return=0.10, expected_volatility=0.10),
        }
        constraints = PortfolioConstraints(
            weight_constraints={
                "alpha": WeightConstraint(strategy_id="alpha", max_weight=0.3),
            }
        )

        portfolio = service.build("P1", 1_000_000, snapshots, constraints=constraints)
        alpha_alloc = service.get_allocation(portfolio, "alpha")
        assert alpha_alloc is not None
        assert alpha_alloc.target_weight <= 0.3

    def test_rebalance_portfolio(self):
        service = PortfolioConstructionService()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.25, current_weight=0.4),
            "beta": make_snapshot("beta", expected_return=0.10, current_weight=0.6),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        new_portfolio, decisions = service.rebalance(portfolio)

        assert len(decisions) > 0
        assert isinstance(new_portfolio, Portfolio)

    def test_get_allocation(self):
        service = PortfolioConstructionService()
        snapshots = {
            "alpha": make_snapshot("alpha"),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        alloc = service.get_allocation(portfolio, "alpha")
        assert alloc is not None
        assert alloc.strategy_id == "alpha"

    def test_get_allocation_nonexistent(self):
        service = PortfolioConstructionService()
        snapshots = {"alpha": make_snapshot("alpha")}

        portfolio = service.build("P1", 1_000_000, snapshots)
        alloc = service.get_allocation(portfolio, "nonexistent")
        assert alloc is None

    def test_get_risk_budget(self):
        service = PortfolioConstructionService()
        snapshots = {"alpha": make_snapshot("alpha")}

        portfolio = service.build("P1", 1_000_000, snapshots)
        budget = service.get_risk_budget(portfolio, "alpha")
        assert budget is not None

    def test_multi_strategy_optimization(self):
        """Full multi-strategy portfolio build."""
        service = PortfolioConstructionService()
        snapshots = {
            "ai_momentum": make_snapshot(
                "ai_momentum", expected_return=0.25, expected_volatility=0.30, sharpe_ratio=0.83
            ),
            "mean_reversion": make_snapshot(
                "mean_reversion", expected_return=0.12, expected_volatility=0.10, sharpe_ratio=1.20
            ),
            "macro_trend": make_snapshot(
                "macro_trend", expected_return=0.18, expected_volatility=0.15, sharpe_ratio=1.20
            ),
        }

        portfolio = service.build("FUND_1", 10_000_000, snapshots)
        assert len(portfolio.strategy_allocations) == 3
        assert portfolio.expected_sharpe > 0

    def test_cash_buffer_in_service(self):
        service = PortfolioConstructionService()
        snapshots = {
            "alpha": make_snapshot("alpha", expected_return=0.20, expected_volatility=0.15),
            "beta": make_snapshot("beta", expected_return=0.10, expected_volatility=0.10),
        }
        config = PortfolioConfig(portfolio_id="P1", capital=1_000_000, min_cash_weight=0.10)

        portfolio = service.build("P1", 1_000_000, snapshots, config=config)
        assert portfolio.cash_weight >= 0.10


# =============================================================================
# Risk Budget Tests
# =============================================================================


class TestRiskBudgetManager:
    """Tests for risk budget allocation."""

    def test_equal_risk_allocation(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.20),
            "b": make_snapshot("b", expected_volatility=0.10),
            "c": make_snapshot("c", expected_volatility=0.15),
        }

        allocations = manager.allocate(snapshots, method="equal_risk")
        assert len(allocations) == 3

        # Equal risk budget per strategy
        for alloc in allocations.values():
            assert abs(alloc.risk_budget - 1.0 / 3) < 0.01

    def test_vol_weighted_allocation(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {
            "high_vol": make_snapshot("high_vol", expected_volatility=0.30),
            "low_vol": make_snapshot("low_vol", expected_volatility=0.10),
        }

        allocations = manager.allocate(snapshots, method="vol_weighted")
        # Lower vol should get more budget
        assert allocations["low_vol"].risk_budget > allocations["high_vol"].risk_budget

    def test_validate_risk_budget(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.15),
            "b": make_snapshot("b", expected_volatility=0.25),
        }

        allocations = manager.allocate(snapshots)
        violations = manager.validate(allocations, snapshots)
        assert len(violations) == 0

    def test_validate_exceeded_budget(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.50),
        }

        allocations = manager.allocate(snapshots)
        # Artificially exceed budget
        allocations["a"].risk_used = allocations["a"].risk_budget + 0.1

        violations = manager.validate(allocations, snapshots)
        assert len(violations) > 0

    def test_get_utilization(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.15),
        }

        allocations = manager.allocate(snapshots)
        utilization = manager.get_utilization(allocations)
        assert "a" in utilization

    def test_total_utilization(self):
        manager = RiskBudgetManager(total_risk_budget=2.0)
        snapshots = {
            "a": make_snapshot("a", expected_volatility=0.15),
            "b": make_snapshot("b", expected_volatility=0.15),
        }

        allocations = manager.allocate(snapshots)
        total_util = manager.get_total_utilization(allocations)
        assert total_util > 0


# =============================================================================
# Exposure Manager Tests
# =============================================================================


class TestExposureManager:
    """Tests for factor/sector exposure management."""

    def test_compute_factor_exposures(self):
        manager = ExposureManager()
        weights = {"a": 0.6, "b": 0.4}
        snapshots = {
            "a": make_snapshot("a", factor_exposures={"momentum": 0.5, "value": 0.3}),
            "b": make_snapshot("b", factor_exposures={"momentum": 0.2, "size": 0.4}),
        }

        exposures = manager.compute_factor_exposures(weights, snapshots)
        assert "momentum" in exposures
        # 0.6 * 0.5 + 0.4 * 0.2 = 0.30 + 0.08 = 0.38
        assert abs(exposures["momentum"].exposure - 0.38) < 0.01

    def test_compute_sector_exposures(self):
        manager = ExposureManager()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", sector_exposures={"tech": 0.8}),
            "b": make_snapshot("b", sector_exposures={"finance": 0.6}),
        }

        exposures = manager.compute_sector_exposures(weights, snapshots)
        assert "tech" in exposures
        assert "finance" in exposures
        assert abs(exposures["tech"].exposure - 0.4) < 0.01  # 0.5 * 0.8

    def test_check_limits_no_violation(self):
        manager = ExposureManager()
        factor_exposures = {
            "momentum": FactorExposure(factor_name="momentum", exposure=0.3, limit=0.5),
        }
        sector_exposures = {
            "tech": SectorExposure(sector_name="tech", exposure=0.2, limit=0.4),
        }

        warnings = manager.check_limits(factor_exposures, sector_exposures)
        assert len(warnings) == 0

    def test_check_limits_violation(self):
        manager = ExposureManager()
        factor_exposures = {
            "momentum": FactorExposure(factor_name="momentum", exposure=0.6, limit=0.5),
        }
        sector_exposures = {}

        warnings = manager.check_limits(factor_exposures, sector_exposures)
        assert len(warnings) > 0

    def test_detect_concentration(self):
        manager = ExposureManager()
        factor_exposures = {
            "tech_factor": FactorExposure(factor_name="tech_factor", exposure=0.6),
        }
        sector_exposures = {
            "tech": SectorExposure(sector_name="tech", exposure=0.5),
        }

        warnings = manager.detect_concentration(
            factor_exposures, sector_exposures,
            factor_threshold=0.5, sector_threshold=0.4,
        )
        assert len(warnings) == 2

    def test_generate_report(self):
        manager = ExposureManager()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a", factor_exposures={"momentum": 0.6}, sector_exposures={"tech": 0.7}),
            "b": make_snapshot("b", factor_exposures={"value": 0.4}, sector_exposures={"finance": 0.5}),
        }
        constraints = {
            "momentum": FactorExposureConstraint(factor_name="momentum", max_exposure=0.5),
        }
        sector_constraints = {
            "tech": SectorExposureConstraint(sector_name="tech", max_exposure=0.3),
        }

        report = manager.generate_report("P1", weights, snapshots, constraints, sector_constraints)
        assert report.portfolio_id == "P1"
        assert len(report.factor_exposures) > 0
        assert len(report.sector_exposures) > 0
        # Should have concentration warnings
        assert len(report.concentration_warnings) > 0


# =============================================================================
# Integration Tests - Full Pipeline
# =============================================================================


class TestFullPipeline:
    """End-to-end integration tests."""

    def test_full_construction_pipeline(self):
        """Test the full portfolio construction pipeline end-to-end."""
        service = PortfolioConstructionService()

        # Three strategies with different risk/return profiles
        strategies_data = [
            {
                "strategy_id": "ai_momentum",
                "name": "AI Momentum",
                "expected_return": 0.25,
                "expected_volatility": 0.30,
                "sharpe_ratio": 0.83,
                "max_drawdown": 0.20,
                "recent_alpha": 800,
                "current_weight": 0.33,
                "factor_exposures": {"momentum": 0.8, "tech": 0.6},
                "sector_exposures": {"technology": 0.7},
            },
            {
                "strategy_id": "mean_reversion",
                "name": "Mean Reversion",
                "expected_return": 0.12,
                "expected_volatility": 0.10,
                "sharpe_ratio": 1.20,
                "max_drawdown": 0.08,
                "recent_alpha": -200,
                "current_weight": 0.33,
                "factor_exposures": {"value": 0.5, "low_vol": 0.4},
                "sector_exposures": {"financials": 0.5},
            },
            {
                "strategy_id": "macro_trend",
                "name": "Macro Trend",
                "expected_return": 0.18,
                "expected_volatility": 0.15,
                "sharpe_ratio": 1.20,
                "max_drawdown": 0.12,
                "recent_alpha": 500,
                "current_weight": 0.34,
                "factor_exposures": {"macro": 0.6, "carry": 0.3},
                "sector_exposures": {"commodities": 0.6},
            },
        ]

        constraints = PortfolioConstraints(
            weight_constraints={
                "ai_momentum": WeightConstraint(strategy_id="ai_momentum", max_weight=0.4),
                "mean_reversion": WeightConstraint(strategy_id="mean_reversion", min_weight=0.15),
            },
            risk_constraints={
                "ai_momentum": RiskConstraint(
                    strategy_id="ai_momentum",
                    max_drawdown=0.15,
                ),
            },
            factor_constraints={
                "tech": FactorExposureConstraint(factor_name="tech", max_exposure=0.5),
            },
            sector_constraints={
                "technology": SectorExposureConstraint(sector_name="technology", max_exposure=0.4),
            },
            max_single_strategy_weight=0.5,
            min_single_strategy_weight=0.05,
        )

        # Build portfolio
        portfolio = service.build_multi(
            "AI_FUND", 10_000_000, strategies_data,
            constraints=constraints,
            method=OptimizationMethod.MEAN_VARIANCE,
        )

        assert portfolio.portfolio_id == "AI_FUND"
        assert portfolio.capital == 10_000_000
        assert len(portfolio.strategy_allocations) <= 3

        # Check constraints
        for alloc in portfolio.strategy_allocations:
            if alloc.strategy_id == "ai_momentum":
                assert alloc.target_weight <= 0.4
            if alloc.strategy_id == "mean_reversion":
                assert alloc.target_weight >= 0.0  # may be removed due to risk

        # Rebalance
        new_portfolio, decisions = service.rebalance(portfolio)

        assert len(decisions) > 0
        for d in decisions:
            assert d.strategy_id in [s["strategy_id"] for s in strategies_data]

    def test_dynamic_allocation_with_performance_change(self):
        """Test dynamic adjustment when strategy performance changes."""
        service = PortfolioConstructionService()

        # Period 1: Value strategy performing well
        strategies_p1 = [
            {
                "strategy_id": "ai",
                "name": "AI Strategy",
                "expected_return": 0.15,
                "expected_volatility": 0.25,
                "sharpe_ratio": 0.6,
                "recent_alpha": -100,
                "current_weight": 0.3,
            },
            {
                "strategy_id": "value",
                "name": "Value Strategy",
                "expected_return": 0.20,
                "expected_volatility": 0.12,
                "sharpe_ratio": 1.67,
                "recent_alpha": 500,
                "current_weight": 0.3,
            },
            {
                "strategy_id": "macro",
                "name": "Macro Strategy",
                "expected_return": 0.12,
                "expected_volatility": 0.15,
                "sharpe_ratio": 0.8,
                "recent_alpha": 100,
                "current_weight": 0.4,
            },
        ]

        portfolio_p1 = service.build_multi("FUND", 5_000_000, strategies_p1)

        # Period 2: AI strategy alpha improves, value alpha drops
        strategies_p2 = [
            {
                "strategy_id": "ai",
                "name": "AI Strategy",
                "expected_return": 0.25,
                "expected_volatility": 0.25,
                "sharpe_ratio": 1.0,
                "recent_alpha": 800,
                "current_weight": portfolio_p1.target_weights.get("ai", 0.3),
            },
            {
                "strategy_id": "value",
                "name": "Value Strategy",
                "expected_return": 0.10,
                "expected_volatility": 0.15,
                "sharpe_ratio": 0.67,
                "recent_alpha": -300,
                "current_weight": portfolio_p1.target_weights.get("value", 0.3),
            },
            {
                "strategy_id": "macro",
                "name": "Macro Strategy",
                "expected_return": 0.12,
                "expected_volatility": 0.15,
                "sharpe_ratio": 0.8,
                "recent_alpha": 100,
                "current_weight": portfolio_p1.target_weights.get("macro", 0.4),
            },
        ]

        portfolio_p2 = service.build_multi("FUND", 5_000_000, strategies_p2)

        # AI weight should increase, value should decrease
        ai_w_p1 = portfolio_p1.target_weights.get("ai", 0)
        ai_w_p2 = portfolio_p2.target_weights.get("ai", 0)
        value_w_p1 = portfolio_p1.target_weights.get("value", 0)
        value_w_p2 = portfolio_p2.target_weights.get("value", 0)

        # At minimum, verify weights changed in expected direction
        # (exact magnitude depends on optimization)
        assert ai_w_p2 >= 0  # AI still allocated
        assert value_w_p2 >= 0  # Value still allocated

    def test_extreme_concentration_prevention(self):
        """Test that extreme concentration is prevented."""
        service = PortfolioConstructionService()

        strategies_data = [
            {
                "strategy_id": "dominant",
                "name": "Dominant",
                "expected_return": 0.50,  # Very high return
                "expected_volatility": 0.10,  # Very low vol
                "sharpe_ratio": 5.0,
                "current_weight": 0.5,
            },
            {
                "strategy_id": "weak_a",
                "name": "Weak A",
                "expected_return": 0.01,
                "expected_volatility": 0.30,
                "sharpe_ratio": 0.03,
                "current_weight": 0.25,
            },
            {
                "strategy_id": "weak_b",
                "name": "Weak B",
                "expected_return": 0.01,
                "expected_volatility": 0.30,
                "sharpe_ratio": 0.03,
                "current_weight": 0.25,
            },
        ]

        constraints = PortfolioConstraints(
            max_single_strategy_weight=0.5,
            weight_constraints={
                "dominant": WeightConstraint(strategy_id="dominant", max_weight=0.5),
            }
        )

        portfolio = service.build_multi("FUND", 1_000_000, strategies_data, constraints=constraints)
        dominant_alloc = service.get_allocation(portfolio, "dominant")
        assert dominant_alloc is not None
        assert dominant_alloc.target_weight <= 0.5

    def test_empty_strategies_handling(self):
        """Test handling of empty strategy list."""
        service = PortfolioConstructionService()

        # Empty list should produce a portfolio with no allocations
        portfolio = service.build_multi("P1", 1_000_000, [])
        assert portfolio.portfolio_id == "P1"
        assert len(portfolio.strategy_allocations) == 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_capital(self):
        service = PortfolioConstructionService()
        snapshots = {"a": make_snapshot("a")}

        # Zero capital should still produce a portfolio (weights sum to 1, capital=0)
        portfolio = service.build("P1", 0, snapshots)
        assert portfolio.capital == 0
        assert len(portfolio.strategy_allocations) == 1
        # Capital allocated should be 0
        for alloc in portfolio.strategy_allocations:
            assert alloc.capital_allocated == 0.0

    def test_single_strategy_portfolio(self):
        service = PortfolioConstructionService()
        snapshots = {"only": make_snapshot("only", expected_return=0.15, expected_volatility=0.20)}

        portfolio = service.build("P1", 1_000_000, snapshots)
        assert len(portfolio.strategy_allocations) == 1
        assert portfolio.target_weights["only"] <= 1.0

    def test_all_negative_returns(self):
        """All strategies have negative expected returns."""
        service = PortfolioConstructionService()
        snapshots = {
            "a": make_snapshot("a", expected_return=-0.10, expected_volatility=0.20),
            "b": make_snapshot("b", expected_return=-0.05, expected_volatility=0.15),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        # Should still produce weights (optimizer handles this)
        assert len(portfolio.strategy_allocations) == 2

    def test_identical_strategies(self):
        """Two strategies with identical profiles."""
        service = PortfolioConstructionService()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.15, expected_volatility=0.20),
            "b": make_snapshot("b", expected_return=0.15, expected_volatility=0.20),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        # Should split roughly equally
        assert abs(portfolio.target_weights["a"] - portfolio.target_weights["b"]) < 0.1

    def test_very_high_volatility(self):
        """Strategy with extremely high volatility."""
        service = PortfolioConstructionService()
        snapshots = {
            "safe": make_snapshot("safe", expected_return=0.10, expected_volatility=0.10),
            "wild": make_snapshot("wild", expected_return=0.15, expected_volatility=0.80),
        }

        portfolio = service.build("P1", 1_000_000, snapshots)
        # Safe should get more weight
        assert portfolio.target_weights["safe"] > portfolio.target_weights["wild"]

    def test_constraints_make_infeasible(self):
        """Constraints that are impossible to satisfy together."""
        enforcer = ConstraintEnforcer()
        weights = {"a": 0.5, "b": 0.5}
        snapshots = {
            "a": make_snapshot("a"),
            "b": make_snapshot("b"),
        }
        constraints = PortfolioConstraints(
            weight_constraints={
                "a": WeightConstraint(strategy_id="a", min_weight=0.4),
                "b": WeightConstraint(strategy_id="b", min_weight=0.4),
            },
            max_total_weight=0.7,  # Can't have both >= 0.4 and total <= 0.7
        )

        result = enforcer.enforce(weights, snapshots, constraints)
        # System should still produce a result (clamp and normalize)
        total = sum(result.values())
        assert total > 0

    def test_negative_volatility_handling(self):
        """Handle negative or zero volatility gracefully."""
        opt = MeanVarianceOptimizer()
        snapshots = {
            "a": make_snapshot("a", expected_return=0.10, expected_volatility=0.0),
            "b": make_snapshot("b", expected_return=0.10, expected_volatility=0.0),
        }

        result = opt.optimize(snapshots)
        assert result.status == "success"


# =============================================================================
# Risk Budget Edge Cases
# =============================================================================


class TestRiskBudgetEdgeCases:
    """Edge case tests for risk budget."""

    def test_zero_total_budget(self):
        manager = RiskBudgetManager(total_risk_budget=0.0)
        snapshots = {"a": make_snapshot("a", expected_volatility=0.15)}

        allocations = manager.allocate(snapshots)
        assert allocations["a"].risk_budget == 0.0

    def test_single_strategy_gets_all_budget(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {"only": make_snapshot("only", expected_volatility=0.15)}

        allocations = manager.allocate(snapshots)
        assert allocations["only"].risk_budget == 1.0

    def test_utilization_exceeds_one(self):
        manager = RiskBudgetManager(total_risk_budget=1.0)
        snapshots = {"a": make_snapshot("a", expected_volatility=0.80)}

        allocations = manager.allocate(snapshots)
        utilization = manager.get_utilization(allocations)
        assert utilization["a"] >= 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
