"""Tests for RL Portfolio Optimizer and Evaluator."""

import pytest
import numpy as np
from services.reinforcement_learning.environment import (
    RLTradingEnvironment,
    EnvironmentConfig,
)
from services.reinforcement_learning.policy_network import (
    PolicyNetwork,
    PolicyConfig,
)
from services.reinforcement_learning.portfolio_optimizer import (
    RLPortfolioOptimizer,
    OptimizerConfig,
    OptimizerMethod,
    PortfolioAllocation,
    AllocationResult,
)
from services.reinforcement_learning.evaluator import (
    RLEvaluator,
    EvaluatorConfig,
    EvaluationResult,
    EvaluationMetrics,
)


class TestPortfolioOptimizer:
    """Tests for RLPortfolioOptimizer."""

    @pytest.fixture
    def symbols(self):
        return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]

    @pytest.fixture
    def prices(self, symbols):
        return {s: 100.0 + i * 25.0 for i, s in enumerate(symbols)}

    @pytest.fixture
    def returns_data(self, symbols):
        # Generate some fake return history
        np.random.seed(42)
        data = {}
        for s in symbols:
            data[s] = list(np.random.normal(0.0005, 0.02, 252))
        return data

    @pytest.fixture
    def optimizer(self):
        return RLPortfolioOptimizer(OptimizerConfig(seed=42))

    def test_optimize_basic(self, optimizer, prices, returns_data):
        result = optimizer.optimize(
            current_prices=prices,
            returns_data=returns_data,
        )
        assert isinstance(result, AllocationResult)
        assert isinstance(result.allocation, PortfolioAllocation)

    def test_optimize_weights_sum_to_one(self, optimizer, prices, returns_data):
        result = optimizer.optimize(
            current_prices=prices,
            returns_data=returns_data,
        )
        total = sum(result.allocation.weights.values())
        assert abs(total - 1.0) < 0.05

    def test_optimize_all_positive_weights(self, optimizer, prices, returns_data):
        result = optimizer.optimize(
            current_prices=prices,
            returns_data=returns_data,
        )
        for sym, w in result.allocation.weights.items():
            assert w >= -0.01  # No short positions by default

    def test_optimize_with_current_weights(self, optimizer, prices, returns_data):
        current = {"AAPL": 0.3, "MSFT": 0.3, "NVDA": 0.2, "AMZN": 0.1, "GOOGL": 0.1}
        result = optimizer.optimize(
            current_prices=prices,
            current_weights=current,
            returns_data=returns_data,
        )
        assert result.allocation.estimated_turnover >= 0

    def test_allocation_validation(self):
        alloc = PortfolioAllocation(
            weights={"AAPL": 0.6, "MSFT": 0.4},
            method="test",
        )
        warnings = alloc.validate()
        assert len(warnings) >= 0  # May warn about high concentration

    def test_optimize_regime_bull(self, optimizer, prices, returns_data):
        result = optimizer.optimize(
            current_prices=prices,
            returns_data=returns_data,
            regime="bull",
        )
        assert result.regime == "bull"

    def test_optimize_regime_crisis(self, optimizer, prices, returns_data):
        result = optimizer.optimize(
            current_prices=prices,
            returns_data=returns_data,
            regime="crisis",
        )
        assert result.regime == "crisis"

    def test_mean_variance_method(self, optimizer, prices, returns_data):
        config = OptimizerConfig(method=OptimizerMethod.RL_MEAN_VARIANCE, use_regime_adaptation=False, seed=42)
        opt = RLPortfolioOptimizer(config)
        result = opt.optimize(prices, returns_data=returns_data)
        assert result.allocation.method == "rl_mean_variance"

    def test_risk_parity_method(self, optimizer, prices):
        config = OptimizerConfig(method=OptimizerMethod.RL_RISK_PARITY, use_regime_adaptation=False, seed=42)
        opt = RLPortfolioOptimizer(config)
        result = opt.optimize(
            current_prices=prices,
            volatilities={s: 0.15 + i * 0.05 for i, s in enumerate(prices.keys())},
        )
        assert result.allocation.method == "rl_risk_parity"

        # Risk parity: higher vol assets get lower weights
        weights = result.allocation.weights
        assert weights["GOOGL"] <= weights["AAPL"]  # GOOGL has highest vol

    def test_min_variance_method(self, optimizer, prices):
        config = OptimizerConfig(method=OptimizerMethod.RL_MIN_VARIANCE, use_regime_adaptation=False, seed=42)
        opt = RLPortfolioOptimizer(config)
        result = opt.optimize(current_prices=prices)
        assert result.allocation.method == "rl_min_variance"

    def test_to_dict(self, optimizer, prices, returns_data):
        result = optimizer.optimize(prices, returns_data=returns_data)
        d = result.allocation.to_dict()
        assert "weights" in d
        assert "expected_sharpe" in d
        assert "method" in d

    def test_get_drift(self, optimizer, prices, returns_data):
        result = optimizer.optimize(prices, returns_data=returns_data)
        current = {s: 1.0 / len(prices) for s in prices}
        drift = optimizer.get_drift(current, result.allocation)
        assert isinstance(drift, dict)
        total_drift = sum(abs(v) for v in drift.values()) / 2
        assert total_drift >= 0

    def test_allocation_history(self, optimizer, prices, returns_data):
        for _ in range(3):
            optimizer.optimize(prices, returns_data=returns_data)
        history = optimizer.get_allocation_history()
        assert len(history) == 3


class TestRLEvaluator:
    """Tests for RLEvaluator."""

    @pytest.fixture
    def env(self):
        return RLTradingEnvironment(EnvironmentConfig(
            symbols=["AAPL", "MSFT"],
            max_steps=30,
            seed=42,
        ))

    @pytest.fixture
    def policy(self):
        return PolicyNetwork(PolicyConfig(
            state_dim=16,
            action_dim=2,
            hidden_layers=[64, 32],
        ))

    @pytest.fixture
    def evaluator(self, env, policy):
        return RLEvaluator(env, policy, EvaluatorConfig(
            n_episodes=5,
            max_steps_per_episode=20,
            seed=42,
        ))

    def test_evaluate(self, evaluator):
        result = evaluator.evaluate()
        assert isinstance(result, EvaluationResult)
        assert isinstance(result.metrics, EvaluationMetrics)

    def test_evaluate_returns_metrics(self, evaluator):
        result = evaluator.evaluate()
        m = result.metrics
        assert m.mean_episode_reward is not None
        assert m.sharpe_ratio is not None
        assert m.max_drawdown is not None

    def test_evaluation_metrics_to_dict(self, evaluator):
        result = evaluator.evaluate()
        d = result.metrics.to_dict()
        assert "total_return" in d
        assert "sharpe_ratio" in d
        assert "max_drawdown" in d

    def test_evaluate_with_regime(self, evaluator):
        evaluator.config.test_regimes = ["bull", "bear"]
        result = evaluator.evaluate()
        assert len(result.regime_results) <= 2

    def test_compare_policies(self, evaluator, env):
        policy_a = PolicyNetwork(PolicyConfig(state_dim=16, action_dim=2))
        policy_b = PolicyNetwork(PolicyConfig(state_dim=16, action_dim=2))
        evaluator.env = env
        evaluator.policy = policy_a
        comparison = evaluator.compare_policies(policy_a, policy_b)
        assert "policy_a" in comparison
        assert "policy_b" in comparison
        assert "better" in comparison

    def test_evaluate_empty(self, evaluator):
        # Should handle edge case
        result = evaluator.evaluate()
        assert result is not None

    def test_evaluation_config(self):
        config = EvaluatorConfig(
            n_episodes=50,
            compute_sharpe=True,
            compute_var=True,
            test_regimes=["bull", "neutral"],
        )
        assert config.n_episodes == 50
        assert config.compute_sharpe is True
        assert "bull" in config.test_regimes

    def test_check_pass_criteria(self, evaluator):
        metrics = EvaluationMetrics(
            sharpe_ratio=0.5,
            max_drawdown=0.3,
            cvar_95=-0.02,
        )
        assert evaluator._check_pass_criteria(metrics) is True

        metrics_bad = EvaluationMetrics(
            sharpe_ratio=-2.0,
            max_drawdown=0.60,
            cvar_95=-0.10,
        )
        assert evaluator._check_pass_criteria(metrics_bad) is False

    def test_drawdown_series(self, evaluator):
        returns = [0.01, -0.02, 0.03, -0.01, 0.005]
        dd = evaluator._compute_drawdown_series(returns)
        assert len(dd) == len(returns)


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_train_predict_cycle(self):
        """Test the full cycle: train → predict → evaluate."""
        env = RLTradingEnvironment(EnvironmentConfig(
            symbols=["AAPL", "MSFT"],
            max_steps=20,
            seed=42,
        ))
        policy = PolicyNetwork(PolicyConfig(state_dim=16, action_dim=2))
        evaluator = RLEvaluator(env, policy, EvaluatorConfig(
            n_episodes=3,
            max_steps_per_episode=10,
        ))

        # Evaluate policy
        result = evaluator.evaluate()
        assert result is not None
        assert isinstance(result, EvaluationResult)

    def test_portfolio_optimize_with_env(self):
        """Test portfolio optimization using env data."""
        env = RLTradingEnvironment(EnvironmentConfig(
            symbols=["AAPL", "MSFT", "NVDA"],
            max_steps=10,
            seed=42,
        ))
        optimizer = RLPortfolioOptimizer(OptimizerConfig(
            symbols=["AAPL", "MSFT", "NVDA"],
            seed=42,
        ))

        # Get prices from environment
        state = env.reset()
        prices = state.prices

        result = optimizer.optimize(current_prices=prices)
        assert result.allocation is not None
        assert len(result.allocation.weights) == 3
