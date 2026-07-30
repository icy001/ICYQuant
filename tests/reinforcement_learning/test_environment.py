"""Tests for RL Environment component."""

import pytest
import numpy as np
from services.reinforcement_learning.environment import (
    RLTradingEnvironment,
    EnvironmentConfig,
    EnvironmentMode,
    MarketState,
    EnvironmentStep,
    EnvironmentEpisode,
)


class TestEnvironmentConfig:
    """Tests for EnvironmentConfig."""

    def test_default_config(self):
        config = EnvironmentConfig()
        assert config.symbols == ["AAPL", "MSFT", "NVDA"]
        assert config.initial_balance == 1_000_000.0
        assert config.max_steps == 252
        assert config.mode == EnvironmentMode.TRAIN

    def test_custom_config(self):
        config = EnvironmentConfig(
            symbols=["BTC", "ETH"],
            initial_balance=100_000.0,
            max_steps=100,
            seed=42,
        )
        assert config.symbols == ["BTC", "ETH"]
        assert config.initial_balance == 100_000.0
        assert config.max_steps == 100
        assert config.seed == 42


class TestMarketState:
    """Tests for MarketState."""

    def test_to_vector(self):
        state = MarketState(
            prices={"AAPL": 150.0, "MSFT": 300.0, "NVDA": 500.0},
            returns={"AAPL": 0.01, "MSFT": -0.02, "NVDA": 0.03},
            volumes={"AAPL": 1_000_000, "MSFT": 2_000_000, "NVDA": 3_000_000},
            portfolio_value=1_000_000.0,
            cash=500_000.0,
            positions={"AAPL": 100.0, "MSFT": 200.0, "NVDA": 300.0},
        )
        vec = state.to_vector()
        assert isinstance(vec, np.ndarray)
        assert vec.dtype == np.float32
        # 3 symbols * 5 features + 6 aggregate = 21
        assert len(vec) == 21


class TestRLTradingEnvironment:
    """Tests for RLTradingEnvironment."""

    @pytest.fixture
    def env(self):
        config = EnvironmentConfig(
            symbols=["AAPL", "MSFT"],
            max_steps=50,
            seed=42,
        )
        return RLTradingEnvironment(config)

    def test_reset(self, env):
        state = env.reset()
        assert isinstance(state, MarketState)
        assert state.portfolio_value == 1_000_000.0
        assert state.cash == 1_000_000.0
        assert state.step == 0
        assert state.current_drawdown == 0.0

    def test_reset_with_seed(self, env):
        state1 = env.reset(seed=99)
        state2 = env.reset(seed=99)
        # Same seed should produce same initial market state
        assert state1.prices == state2.prices

    def test_step_returns_discount_step(self, env):
        state = env.reset()
        action = {"AAPL": 0.1, "MSFT": 0.0}
        step = env.step(action)
        assert isinstance(step, EnvironmentStep)
        assert step.state.step == 1
        assert isinstance(step.reward, float)
        assert isinstance(step.done, bool)
        assert "pnl" in step.info
        assert "cost" in step.info
        assert "portfolio_value" in step.info

    def test_step_updates_portfolio(self, env):
        env.reset()
        action = {"AAPL": 0.2, "MSFT": 0.0}
        step = env.step(action)
        assert step.state.portfolio_value > 0

    def test_episode_summary(self, env):
        env.reset()
        for _ in range(10):
            action = {"AAPL": 0.05, "MSFT": -0.05}
            step = env.step(action)
            if step.done or step.truncated:
                break
        summary = env.get_episode_summary()
        assert isinstance(summary, EnvironmentEpisode)
        assert summary.final_value > 0
        assert isinstance(summary.num_trades, int)

    def test_max_steps_truncation(self, env):
        env.reset()
        for _ in range(60):
            action = {"AAPL": 0.0, "MSFT": 0.0}
            step = env.step(action)
            if step.done or step.truncated:
                break
        # Should truncate at max_steps=50
        assert step.truncated or step.done

    def test_action_dim(self, env):
        assert env.action_dim == 2  # Two symbols

    def test_state_dim(self, env):
        # 2 symbols * 5 features + 6 aggregate = 16
        assert env.state_dim == 16

    def test_environment_modes(self):
        for mode in EnvironmentMode:
            config = EnvironmentConfig(mode=mode)
            env = RLTradingEnvironment(config)
            assert env.config.mode == mode

    def test_bankruptcy_termination(self, env):
        env.reset()
        env._portfolio_value = 100.0  # Set near bankruptcy
        done, truncated = env._check_termination()
        assert done
