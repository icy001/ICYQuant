"""测试 Multi-Objective Evaluator。

覆盖: Sharpe、Sortino、MaxDD、Calmar、Win Rate、Turnover、
IC/IR/RankIC、Stability、加权复合评分。
"""

import numpy as np
import pytest

from services.automl.evaluator import (
    EvaluationMetric,
    EvaluationResult,
    MultiObjectiveEvaluator,
    ObjectiveConfig,
)


# =================================================================
# Test data
# =================================================================

@pytest.fixture
def returns():
    """50 days of returns with positive drift."""
    rng = np.random.RandomState(42)
    return (rng.randn(500) * 0.01 + 0.0005).tolist()


@pytest.fixture
def flat_returns():
    """Constant returns."""
    return [0.001] * 252


@pytest.fixture
def evaluator():
    return MultiObjectiveEvaluator()


@pytest.fixture
def custom_evaluator():
    config = ObjectiveConfig(
        metrics=[
            EvaluationMetric.SHARPE,
            EvaluationMetric.SORTINO,
            EvaluationMetric.MAX_DRAWDOWN,
            EvaluationMetric.CALMAR,
            EvaluationMetric.WIN_RATE,
        ],
        weights={
            "sharpe": 0.4,
            "sortino": 0.2,
            "max_drawdown": 0.2,
            "calmar": 0.1,
            "win_rate": 0.1,
        },
        directions={
            "sharpe": "maximize",
            "sortino": "maximize",
            "max_drawdown": "minimize",
            "calmar": "maximize",
            "win_rate": "maximize",
        },
    )
    return MultiObjectiveEvaluator(config)


# =================================================================
# Basic Metrics
# =================================================================


class TestSharpeRatio:
    def test_positive_drift(self, evaluator, returns):
        sr = evaluator.sharpe_ratio(returns)
        assert sr > 0.5  # positive drift

    def test_zero_returns(self, evaluator):
        sr = evaluator.sharpe_ratio([0.0] * 100)
        assert isinstance(sr, float)

    def test_constant_positive(self, evaluator):
        sr = evaluator.sharpe_ratio([0.01] * 252)
        assert isinstance(sr, float)

    def test_all_nan_returns(self, evaluator):
        sr = evaluator.sharpe_ratio([np.nan] * 10)
        assert sr == 0.0

    def test_single_value(self, evaluator):
        sr = evaluator.sharpe_ratio([0.01])
        assert sr == 0.0  # not enough data


class TestSortinoRatio:
    def test_positive(self, evaluator, returns):
        sr = evaluator.sortino_ratio(returns)
        assert sr > 0

    def test_no_downside(self, evaluator):
        sr = evaluator.sortino_ratio([0.01, 0.02, 0.03, 0.04, 0.05])
        assert sr == float("inf")  # no downside deviations

    def test_only_downside(self, evaluator):
        sr = evaluator.sortino_ratio([-0.01, -0.02, -0.01])
        assert sr < 0


class TestMaxDrawdown:
    def test_no_drawdown(self, evaluator):
        mdd = evaluator.max_drawdown([0.01, 0.02, 0.03])
        assert mdd == 0.0

    def test_significant_drawdown(self):
        returns = [0.01, -0.10, -0.05, 0.02, 0.03]
        ev = MultiObjectiveEvaluator()
        mdd = ev.max_drawdown(returns)
        assert mdd > 0.05  # experienced drawdown

    def test_crash_scenario(self, evaluator):
        returns = [0.0] * 100 + [-0.30] + [0.0] * 100
        mdd = evaluator.max_drawdown(returns)
        assert 0.20 <= mdd <= 0.40


class TestAnnualReturn:
    def test_positive(self, evaluator, returns):
        ann = evaluator.annual_return(returns)
        assert ann > 0

    def test_empty(self, evaluator):
        assert evaluator.annual_return([]) == 0.0

    def test_flat(self, evaluator):
        assert evaluator.annual_return([0.0] * 252) == 0.0


class TestCalmarRatio:
    def test_positive(self, evaluator, returns):
        cr = evaluator.calmar_ratio(returns)
        assert isinstance(cr, float)

    def test_zero_drawdown(self, evaluator):
        cr = evaluator.calmar_ratio([0.001] * 252)
        assert cr == float("inf")


class TestWinRate:
    def test_positive_drift(self, evaluator, returns):
        wr = evaluator.win_rate(returns)
        assert 0.0 <= wr <= 1.0

    def test_all_wins(self, evaluator):
        wr = evaluator.win_rate([0.01, 0.02, 0.03])
        assert wr == 1.0

    def test_all_losses(self, evaluator):
        wr = evaluator.win_rate([-0.01, -0.02, -0.03])
        assert wr == 0.0


class TestTurnover:
    def test_basic(self, evaluator):
        to = evaluator.turnover([0.1, 0.2, 0.1, 0.3])
        assert to >= 0

    def test_constant_signal(self, evaluator):
        to = evaluator.turnover([0.5, 0.5, 0.5, 0.5])
        assert to == 0.0

    def test_short_signal(self, evaluator):
        to = evaluator.turnover([0.1])
        assert to == 0.0


# =================================================================
# IC Metrics
# =================================================================


class TestICMetrics:
    def test_ic_mean_perfect(self, evaluator):
        ic = evaluator.ic_mean([1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0, 4.0, 5.0])
        assert ic > 0.99

    def test_ic_mean_negative(self, evaluator):
        ic = evaluator.ic_mean([1.0, 2.0, 3.0], [-1.0, -2.0, -3.0])
        assert ic < -0.99

    def test_ic_mean_with_nans(self, evaluator):
        ic = evaluator.ic_mean(
            [1.0, np.nan, 3.0, 4.0],
            [1.0, 2.0, 3.0, 4.0],
        )
        assert abs(ic - 1.0) < 0.01

    def test_ic_ir(self, evaluator):
        """IC IR across 5 periods."""
        preds_list = [[1.0, 2.0, 3.0] for _ in range(5)]
        targs_list = [[1.0, 2.0, 3.0] for _ in range(5)]
        icir = evaluator.ic_ir(preds_list, targs_list)
        # All ICs = 1.0, std = 0 -> ICIR = 0
        assert icir == 0.0

    def test_ic_ir_variable(self, evaluator):
        rng = np.random.RandomState(42)
        preds_list = [rng.randn(50).tolist() for _ in range(10)]
        targs_list = [rng.randn(50).tolist() for _ in range(10)]
        icir = evaluator.ic_ir(preds_list, targs_list)
        assert isinstance(icir, float)

    def test_ic_ir_single_period(self, evaluator):
        icir = evaluator.ic_ir([[1.0, 2.0]], [[1.0, 2.0]])
        assert icir == 0.0  # std requires 2+ periods

    def test_rank_ic(self, evaluator):
        ric = evaluator.rank_ic(
            [1.0, 2.0, 3.0, 4.0, 5.0],
            [1.0, 2.0, 3.0, 4.0, 5.0],
        )
        assert ric > 0.99  # perfect monotonic

    def test_rank_ic_reversed(self, evaluator):
        ric = evaluator.rank_ic(
            [5.0, 4.0, 3.0, 2.0, 1.0],
            [1.0, 2.0, 3.0, 4.0, 5.0],
        )
        assert ric < -0.99


# =================================================================
# Stability
# =================================================================


class TestStability:
    def test_high_stability(self, evaluator):
        """Constant returns -> constant Sharpe across chunks -> max stability."""
        returns = [0.001] * 252
        s = evaluator.stability(returns)
        assert s == 1.0  # std=0 means perfect stability

    def test_random_returns(self, evaluator, returns):
        s = evaluator.stability(returns)
        assert 0.0 <= s <= 1.0

    def test_insufficient_data(self, evaluator):
        s = evaluator.stability([0.01, 0.02])
        assert s == 0.0


# =================================================================
# Full Evaluation
# =================================================================


class TestEvaluate:
    def test_evaluate_all_metrics(self, evaluator, returns):
        result = evaluator.evaluate(returns)
        assert isinstance(result, EvaluationResult)
        assert "sharpe" in result.metrics
        assert "sortino" in result.metrics
        assert "max_drawdown" in result.metrics
        assert "stability" in result.metrics
        assert isinstance(result.composite_score, float)

    def test_evaluate_with_predictions(self, evaluator, returns):
        result = evaluator.evaluate(returns, predictions=returns, targets=returns)
        assert "ic_mean" in result.metrics

    def test_evaluate_batch(self, evaluator):
        rng = np.random.RandomState(42)
        returns_batch = [(rng.randn(100) * 0.01 + 0.001).tolist() for _ in range(3)]
        results = evaluator.evaluate_batch(returns_batch)
        assert len(results) == 3
        assert all(isinstance(r, EvaluationResult) for r in results)

    def test_custom_weights(self, custom_evaluator, returns):
        result = custom_evaluator.evaluate(returns)
        assert isinstance(result.composite_score, float)

    def test_default_direction_minimize_mdd(self, evaluator):
        """MaxDD should be treated as minimize by default."""
        config = ObjectiveConfig(
            metrics=[EvaluationMetric.MAX_DRAWDOWN],
            weights={"max_drawdown": 1.0},
        )
        ev = MultiObjectiveEvaluator(config)
        result = ev.evaluate([0.01, -0.05, -0.03, 0.02])
        # Since MaxDD is minimize, higher MaxDD (more negative composite) -> worse
        assert isinstance(result.composite_score, float)

    def test_objective_config_defaults(self):
        config = ObjectiveConfig()
        assert EvaluationMetric.SHARPE in config.metrics
        assert EvaluationMetric.SORTINO in config.metrics

    def test_evaluate_handles_all_nan_returns(self, evaluator):
        result = evaluator.evaluate([np.nan] * 100)
        assert isinstance(result, EvaluationResult)
        assert result.metrics["sharpe"] == 0.0
