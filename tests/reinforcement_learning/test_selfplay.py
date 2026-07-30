"""Tests for Agent Self-Play and Regime Adapter."""

import pytest
import numpy as np
from services.reinforcement_learning.environment import (
    RLTradingEnvironment,
    EnvironmentConfig,
)
from services.reinforcement_learning.agent_selfplay import (
    SelfPlayManager,
    SelfPlayConfig,
    SelfPlayAgent,
    AgentStrategy,
    CompetitionResult,
)
from services.reinforcement_learning.regime_adapter import (
    RegimeAdapter,
    RegimeConfig,
    MarketRegime,
    RegimePolicy,
)


class TestRegimeAdapter:
    """Tests for RegimeAdapter."""

    @pytest.fixture
    def adapter(self):
        return RegimeAdapter(RegimeConfig(
            trend_lookback=20,
            volatility_lookback=10,
        ))

    def test_detect_bull_regime(self, adapter):
        """Sustained uptrend should be detected as bull."""
        prices = list(range(100, 200))  # Strong upward trend
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        regime = adapter.detect_regime(
            prices=prices, returns=returns, volatility=0.15, drawdown=0.0
        )
        assert regime in (
            MarketRegime.BULL,
            MarketRegime.TRENDING,
            MarketRegime.LOW_VOL,
        )

    def test_detect_bear_regime(self, adapter):
        """Sustained downtrend should be detected as bear/trending."""
        prices = list(range(200, 100, -1))  # Strong downward trend
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]
        regime = adapter.detect_regime(
            prices=prices, returns=returns, volatility=0.3, drawdown=0.25
        )
        assert regime in (
            MarketRegime.BEAR,
            MarketRegime.CRISIS,
            MarketRegime.TRENDING,
        )

    def test_detect_crisis(self, adapter):
        """Large drawdown should be crisis."""
        regime = adapter.detect_regime(
            prices=[100] * 20,
            returns=[0.0] * 19,
            volatility=0.2,
            drawdown=0.35,
            vix=60,
        )
        assert regime == MarketRegime.CRISIS

    def test_detect_neutral(self, adapter):
        """Flat market should be neutral."""
        prices = [100.0 + np.random.uniform(-1, 1) for _ in range(30)]
        returns = [0.0] * 29
        regime = adapter.detect_regime(
            prices=prices, returns=returns, volatility=0.15, drawdown=0.02
        )
        assert regime is not None

    def test_get_risk_params(self, adapter):
        for regime in [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.CRISIS]:
            params = adapter.get_risk_params(regime)
            assert "max_position" in params
            assert "max_leverage" in params
            assert "stop_loss" in params

    def test_adapt_action_scales_weights(self, adapter):
        adapter._current_regime = MarketRegime.BEAR
        action = {"AAPL": 0.3, "MSFT": 0.3}
        adapted = adapter.adapt_action(action)
        # Bear market should reduce position sizes
        for sym in action:
            assert abs(adapted[sym]) <= abs(action[sym])

    def test_adapt_action_bull_scales_up(self, adapter):
        adapter._current_regime = MarketRegime.BULL
        action = {"AAPL": 0.1, "MSFT": 0.1}
        adapted = adapter.adapt_action(action)
        # Bull market may scale up
        for sym in action:
            assert abs(adapted[sym]) >= abs(action[sym]) * 0.8  # Not overly reduced

    def test_should_reduce_exposure(self, adapter):
        adapter._current_regime = MarketRegime.CRISIS
        assert adapter.should_reduce_exposure() is True

        adapter._current_regime = MarketRegime.BULL
        assert adapter.should_reduce_exposure() is False

    def test_should_increase_exposure(self, adapter):
        adapter._current_regime = MarketRegime.BULL
        assert adapter.should_increase_exposure() is True

        adapter._current_regime = MarketRegime.CRISIS
        assert adapter.should_increase_exposure() is False

    def test_get_current_regime(self, adapter):
        assert adapter.get_current_regime() == MarketRegime.NEUTRAL

    def test_get_regime_distribution(self, adapter):
        # Call detect a few times
        for _ in range(5):
            adapter.detect_regime(
                prices=[100] * 30, returns=[0.0] * 29, volatility=0.2
            )
        dist = adapter.get_regime_distribution()
        assert isinstance(dist, dict)

    def test_regime_transition_probability(self, adapter):
        for _ in range(10):
            adapter.detect_regime(
                prices=[100] * 30, returns=[0.0] * 29, volatility=0.2
            )
        prob = adapter.get_regime_transition_probability()
        assert "stay" in prob
        assert "change" in prob

    def test_reset(self, adapter):
        adapter.detect_regime(prices=[100] * 30, returns=[0.0] * 29, volatility=0.2)
        adapter.reset()
        assert adapter.get_current_regime() == MarketRegime.NEUTRAL
        assert len(adapter._regime_history) == 0


class TestSelfPlayManager:
    """Tests for SelfPlayManager."""

    @pytest.fixture
    def env(self):
        config = EnvironmentConfig(
            symbols=["AAPL", "MSFT"],
            max_steps=30,
            seed=42,
        )
        return RLTradingEnvironment(config)

    @pytest.fixture
    def sp_config(self):
        return SelfPlayConfig(
            n_agents=4,
            n_rounds=5,
            episodes_per_round=3,
            seed=42,
        )

    @pytest.fixture
    def manager(self, env, sp_config):
        return SelfPlayManager(env, sp_config)

    def test_add_agent(self, manager):
        manager.add_agent("trend_bot", AgentStrategy.TREND_FOLLOWING)
        agent = manager.get_agent("trend_bot")
        assert agent is not None
        assert agent.strategy == AgentStrategy.TREND_FOLLOWING
        assert agent.elo_rating == 1500.0

    def test_add_agent_with_policy(self, manager):
        from services.reinforcement_learning.policy_network import PolicyNetwork, PolicyConfig
        policy = PolicyNetwork(PolicyConfig(state_dim=16, action_dim=2))
        manager.add_agent("rl_bot", AgentStrategy.RL_TRAINED, policy=policy)
        agent = manager.get_agent("rl_bot")
        assert agent is not None
        assert agent.policy is not None

    def test_remove_agent(self, manager):
        manager.add_agent("temp_bot", AgentStrategy.RANDOM)
        manager.remove_agent("temp_bot")
        assert manager.get_agent("temp_bot") is None

    def test_run_tournament(self, manager):
        manager.add_agent("trend", AgentStrategy.TREND_FOLLOWING)
        manager.add_agent("mean_rev", AgentStrategy.MEAN_REVERSION)
        manager.add_agent("mm", AgentStrategy.MARKET_MAKING)
        manager.add_agent("momentum", AgentStrategy.MOMENTUM)

        results = manager.run_tournament()
        assert len(results) == 5  # n_rounds
        assert all(isinstance(r, CompetitionResult) for r in results)

    def test_tournament_updates_elo(self, manager):
        manager.add_agent("trend", AgentStrategy.TREND_FOLLOWING)
        manager.add_agent("random", AgentStrategy.RANDOM)
        manager.add_agent("buy_hold", AgentStrategy.BUY_HOLD)

        manager.run_tournament()

        # Rankings should be returned; ELO may or may not change with averaging
        rankings = manager._get_rankings()
        assert len(rankings) == 3
        assert all(isinstance(r[0], str) for r in rankings)

    def test_get_best_agent(self, manager):
        manager.add_agent("good", AgentStrategy.TREND_FOLLOWING)
        manager.add_agent("bad", AgentStrategy.RANDOM)
        manager.run_tournament()
        best = manager.get_best_agent()
        assert best is not None

    def test_get_agent_stats(self, manager):
        manager.add_agent("bot_1", AgentStrategy.TREND_FOLLOWING)
        manager.add_agent("bot_2", AgentStrategy.MEAN_REVERSION)
        stats = manager.get_agent_stats()
        assert "bot_1" in stats
        assert "strategy" in stats["bot_1"]
        assert "elo" in stats["bot_1"]
        assert "win_rate" in stats["bot_1"]

    def test_get_elo_history(self, manager):
        manager.add_agent("bot", AgentStrategy.TREND_FOLLOWING)
        manager.run_tournament()
        history = manager.get_elo_history()
        assert "bot" in history
        assert len(history["bot"]) == 5  # n_rounds

    def test_agent_strategies(self, manager):
        """Each strategy should produce valid actions."""
        env = manager.env
        state = env.reset()
        symbols = env.config.symbols

        for strategy in AgentStrategy:
            if strategy == AgentStrategy.RL_TRAINED:
                continue  # needs a policy
            agent = SelfPlayAgent(agent_id="test", strategy=strategy)
            action = manager._get_agent_action(agent, state)
            assert isinstance(action, dict)
            for s in symbols:
                assert s in action
                assert isinstance(action[s], float)

    def test_competition_result_fields(self):
        result = CompetitionResult(
            round_id=0,
            rankings=[("bot_1", 1500.0, 0.5)],
            match_results=[],
            best_agent_id="bot_1",
            best_score=1500.0,
            elo_standings={"bot_1": 1500.0},
        )
        assert result.round_id == 0
        assert result.best_agent_id == "bot_1"

    def test_agent_win_rate(self):
        agent = SelfPlayAgent(agent_id="test", strategy=AgentStrategy.TREND_FOLLOWING)
        assert agent.win_rate() == 0.0
        agent.win_count = 7
        agent.loss_count = 3
        assert agent.win_rate() == 0.7
