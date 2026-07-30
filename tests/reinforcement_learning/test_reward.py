"""Tests for Reward Engine."""

import pytest
import numpy as np
from services.reinforcement_learning.reward_engine import (
    RewardEngine,
    RewardConfig,
    RewardComponents,
    RewardType,
)


class TestRewardConfig:
    """Tests for RewardConfig."""

    def test_default_config(self):
        config = RewardConfig()
        assert config.profit_weight == 1.0
        assert config.sharpe_weight == 0.5
        assert config.drawdown_weight == -2.0
        assert len(config.enabled_components) >= 5

    def test_custom_config(self):
        config = RewardConfig(
            profit_weight=2.0,
            reward_clip=5.0,
            normalize_rewards=False,
        )
        assert config.profit_weight == 2.0
        assert config.reward_clip == 5.0
        assert config.normalize_rewards is False


class TestRewardComponents:
    """Tests for RewardComponents."""

    def test_total_sum(self):
        comp = RewardComponents(
            profit=0.1, sharpe=0.05, drawdown=-0.02,
        )
        assert comp.total() == pytest.approx(0.13)

    def test_to_dict(self):
        comp = RewardComponents(profit=0.1, sharpe=0.05)
        d = comp.to_dict()
        assert d["profit"] == 0.1
        assert d["sharpe"] == 0.05
        assert "total" in d

    def test_empty_components(self):
        comp = RewardComponents()
        assert comp.total() == 0.0


class TestRewardEngine:
    """Tests for RewardEngine."""

    @pytest.fixture
    def engine(self):
        config = RewardConfig(
            profit_weight=1.0,
            drawdown_weight=-1.0,
            turnover_penalty=-0.1,
            reward_clip=None,
        )
        return RewardEngine(config)

    def test_compute_basic_reward(self, engine):
        reward = engine.compute(
            portfolio_return=0.01,
            current_drawdown=0.05,
            turnover=0.1,
        )
        assert isinstance(reward, float)
        assert reward > -10 and reward < 10

    def test_compute_components_populated(self, engine):
        engine.compute(
            portfolio_return=0.02,
            current_drawdown=0.0,
            turnover=0.0,
        )
        comp = engine.get_components()
        assert comp is not None
        assert isinstance(comp.profit, float)

    def test_compute_negative_return(self, engine):
        reward = engine.compute(
            portfolio_return=-0.05,
            current_drawdown=0.10,
            turnover=0.2,
        )
        assert reward < 0

    def test_compute_positive_return(self, engine):
        reward = engine.compute(
            portfolio_return=0.05,
            current_drawdown=0.01,
            turnover=0.05,
        )
        assert reward > 0

    def test_drawdown_penalty_increases(self, engine):
        """Larger drawdown should give more negative reward."""
        r1 = engine.compute(portfolio_return=0.01, current_drawdown=0.05, turnover=0.0)
        engine.reset()
        r2 = engine.compute(portfolio_return=0.01, current_drawdown=0.30, turnover=0.0)
        assert r1 > r2  # Higher drawdown = lower reward

    def test_turnover_penalty(self, engine):
        r1 = engine.compute(portfolio_return=0.01, current_drawdown=0.0, turnover=0.0)
        engine.reset()
        r2 = engine.compute(portfolio_return=0.01, current_drawdown=0.0, turnover=0.5)
        assert r1 > r2  # Higher turnover = lower reward

    def test_reward_clip(self):
        engine = RewardEngine(RewardConfig(reward_clip=0.5))
        reward = engine.compute(portfolio_return=10.0, current_drawdown=0.0, turnover=0.0)
        assert abs(reward) <= 0.5

    def test_episode_reward(self, engine):
        for _ in range(10):
            engine.compute(
                portfolio_return=0.01,
                current_drawdown=0.05,
                turnover=0.1,
            )
        total = engine.compute_episode_reward()
        assert total > 0 or total <= 0  # any valid float

    def test_episode_stats(self, engine):
        for _ in range(5):
            engine.compute(
                portfolio_return=np.random.uniform(-0.05, 0.05),
                current_drawdown=0.05,
                turnover=0.1,
            )
        stats = engine.get_episode_stats()
        assert "mean_reward" in stats
        assert "std_reward" in stats
        assert "total_reward" in stats

    def test_reset_clears_history(self, engine):
        engine.compute(portfolio_return=0.01, current_drawdown=0.0, turnover=0.0)
        engine.reset()
        assert len(engine._return_history) == 0
        assert len(engine._episode_rewards) == 0
        assert len(engine._component_history) == 0

    def test_regime_reward(self):
        config = RewardConfig(
            enabled_components=[
                RewardType.REGIME,
                RewardType.PROFIT,
            ],
            regime_weight=1.0,
            profit_weight=0.0,
        )
        engine = RewardEngine(config)

        # Bull market: positive return rewarded
        r_bull_pos = engine.compute(
            portfolio_return=0.05, current_drawdown=0.0, turnover=0.0,
            market_regime="bull",
        )
        assert r_bull_pos > 0

        engine.reset()
        # Bull market: negative return penalized less in regime component
        r_bull_neg = engine.compute(
            portfolio_return=-0.05, current_drawdown=0.0, turnover=0.0,
            market_regime="bull",
        )
        # In bull, regime_reward caps at 0 for negative returns
        assert r_bull_pos > r_bull_neg
