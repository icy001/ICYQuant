"""Tests for RL Trainer, Policy, Action Space, and Simulator."""

import pytest
import numpy as np
from services.reinforcement_learning.environment import (
    RLTradingEnvironment,
    EnvironmentConfig,
)
from services.reinforcement_learning.policy_network import (
    PolicyNetwork,
    PolicyConfig,
    ActorCriticNetwork,
    NetworkType,
    ActivationType,
)
from services.reinforcement_learning.action_space import (
    ActionSpace,
    DiscreteActionSpace,
    ContinuousActionSpace,
    ActionType,
    ActionConfig,
)
from services.reinforcement_learning.simulator import (
    TradingSimulator,
    SimulatorConfig,
    TradeResult,
    OrderSide,
    OrderType,
    MarketImpactModel,
)


class TestPolicyNetwork:
    """Tests for PolicyNetwork."""

    @pytest.fixture
    def policy_config(self):
        return PolicyConfig(
            state_dim=21,
            action_dim=3,
            hidden_layers=[128, 64],
            orthogonal_init=True,
        )

    @pytest.fixture
    def policy(self, policy_config):
        return PolicyNetwork(policy_config)

    def test_init_parameters(self, policy):
        params = policy.get_parameters()
        assert len(params) > 0
        assert "w_0" in params
        assert "log_std" in params

    def test_forward_continuous(self, policy):
        state = np.random.randn(21).astype(np.float32)
        action, log_prob, value = policy.forward(state)
        assert isinstance(action, np.ndarray)
        assert len(action) == 3
        assert isinstance(log_prob, float)
        assert isinstance(value, float)

    def test_forward_deterministic(self, policy):
        state = np.random.randn(21).astype(np.float32)
        a1, _, _ = policy.forward(state, deterministic=True)
        a2, _, _ = policy.forward(state, deterministic=True)
        np.testing.assert_array_almost_equal(a1, a2)

    def test_forward_stochastic(self, policy):
        state = np.random.randn(21).astype(np.float32)
        # Stochastic should potentially give different results
        actions = [policy.forward(state)[0] for _ in range(10)]
        # Not all identical (very unlikely)
        assert not all(np.array_equal(actions[0], a) for a in actions)

    def test_get_value(self, policy):
        state = np.random.randn(21).astype(np.float32)
        value = policy.get_value(state)
        assert isinstance(value, float)

    def test_act(self, policy):
        state = np.random.randn(21).astype(np.float32)
        action, log_prob = policy.act(state)
        assert isinstance(action, np.ndarray)
        assert isinstance(log_prob, float)

    def test_train_eval_modes(self, policy):
        policy.train()
        assert policy._training is True
        policy.eval()
        assert policy._training is False

    def test_discrete_policy(self):
        config = PolicyConfig(
            state_dim=10,
            action_dim=6,
            use_discrete_actions=True,
        )
        policy = PolicyNetwork(config)
        state = np.random.randn(10).astype(np.float32)
        action, log_prob, value = policy.forward(state)
        assert isinstance(action, np.ndarray)
        assert len(action) == 6
        assert abs(action.sum() - 1.0) < 1e-6  # softmax sums to 1

    def test_network_types(self):
        config = PolicyConfig(
            state_dim=10,
            action_dim=3,
            network_type=NetworkType.MLP,
        )
        policy = PolicyNetwork(config)
        state = np.random.randn(10).astype(np.float32)
        action, _, _ = policy.forward(state)
        assert len(action) == 3

    def test_actor_critic_network(self):
        config = PolicyConfig(state_dim=10, action_dim=3)
        net = ActorCriticNetwork(config)
        state = np.random.randn(10).astype(np.float32)
        action = net.actor_forward(state)
        value = net.critic_forward(state)
        assert len(action) == 3
        assert isinstance(value, float)

    def test_activation_types(self):
        for act in ActivationType:
            config = PolicyConfig(
                state_dim=10, action_dim=2, activation=act,
                hidden_layers=[16],
            )
            policy = PolicyNetwork(config)
            state = np.random.randn(10).astype(np.float32)
            action, _, _ = policy.forward(state)
            assert len(action) == 2

    def test_save_load_params(self, policy, tmp_path):
        path = tmp_path / "test_policy.pkl"
        policy.save(str(path))
        loaded = PolicyNetwork(policy.config)
        loaded.load(str(path))
        for k in policy.get_parameters():
            np.testing.assert_array_almost_equal(
                policy.get_parameters()[k],
                loaded.get_parameters()[k],
            )


class TestActionSpace:
    """Tests for action spaces."""

    def test_discrete_action_space(self):
        config = ActionConfig(
            action_type=ActionType.DISCRETE,
            symbols=["AAPL", "MSFT"],
        )
        space = DiscreteActionSpace(config)
        assert space.dim == 12  # 6 actions * 2 symbols

    def test_discrete_sample(self):
        config = ActionConfig(
            action_type=ActionType.DISCRETE,
            symbols=["AAPL"],
        )
        space = DiscreteActionSpace(config)
        action = space.sample()
        assert "AAPL" in action
        assert 0 <= action["AAPL"] < 6

    def test_discrete_contains(self):
        config = ActionConfig(
            action_type=ActionType.DISCRETE,
            symbols=["AAPL"],
        )
        space = DiscreteActionSpace(config)
        assert space.contains({"AAPL": 3}) is True
        assert space.contains({"AAPL": 10}) is False

    def test_discrete_to_weight(self):
        config = ActionConfig(
            action_type=ActionType.DISCRETE,
            symbols=["AAPL"],
        )
        space = DiscreteActionSpace(config)
        weights = space.action_to_weight({"AAPL": 0})  # BUY
        assert weights["AAPL"] > 0

        weights = space.action_to_weight({"AAPL": 1})  # SELL
        assert weights["AAPL"] < 0

        weights = space.action_to_weight({"AAPL": 2})  # HOLD
        assert weights["AAPL"] == 0.0

    def test_continuous_action_space(self):
        config = ActionConfig(
            action_type=ActionType.CONTINUOUS,
            symbols=["AAPL", "MSFT", "NVDA"],
        )
        space = ContinuousActionSpace(config)
        assert space.dim == 3

    def test_continuous_sample(self):
        config = ActionConfig(
            action_type=ActionType.CONTINUOUS,
            symbols=["AAPL"],
            continuous_bounds=(-1.0, 1.0),
        )
        space = ContinuousActionSpace(config)
        action = space.sample()
        assert -1.0 <= action[0] <= 1.0

    def test_continuous_contains(self):
        config = ActionConfig(
            action_type=ActionType.CONTINUOUS,
            symbols=["AAPL"],
        )
        space = ContinuousActionSpace(config)
        assert space.contains(np.array([0.5])) is True
        assert space.contains(np.array([1.5])) is False
        assert space.contains(np.array([-1.5])) is False

    def test_continuous_to_weights(self):
        config = ActionConfig(
            action_type=ActionType.CONTINUOUS,
            symbols=["AAPL"],
            max_position_pct=0.25,
        )
        space = ContinuousActionSpace(config)
        weights = space.action_to_weights(np.array([0.5]))
        assert abs(weights["AAPL"]) <= 0.25

    def test_n_actions(self):
        config = ActionConfig(action_type=ActionType.DISCRETE)
        space = DiscreteActionSpace(config)
        assert space.n_actions == 6


class TestTradingSimulator:
    """Tests for TradingSimulator."""

    @pytest.fixture
    def sim(self):
        return TradingSimulator(SimulatorConfig(seed=42))

    def test_execute_market_order(self, sim):
        result = sim.execute_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            current_price=150.0,
            daily_volume=1_000_000,
            volatility=0.3,
        )
        assert isinstance(result, TradeResult)
        assert result.symbol == "AAPL"
        assert result.side == OrderSide.BUY
        assert result.success is True
        assert result.filled_quantity > 0
        assert result.commission > 0

    def test_execute_sell_order(self, sim):
        result = sim.execute_order(
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=50,
            current_price=300.0,
        )
        assert result.side == OrderSide.SELL
        assert result.success is True

    def test_execute_order_above_max(self, sim):
        sim.config.max_order_value = 100_000
        result = sim.execute_order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1_000_000,
            current_price=150.0,
        )
        assert result.success is False
        assert result.rejection_reason is not None

    def test_execute_basket(self, sim):
        orders = [
            {"symbol": "AAPL", "side": OrderSide.BUY, "quantity": 100},
            {"symbol": "MSFT", "side": OrderSide.SELL, "quantity": 50},
        ]
        results = sim.execute_basket(
            orders=orders,
            current_prices={"AAPL": 150.0, "MSFT": 300.0},
            daily_volumes={"AAPL": 1_000_000, "MSFT": 2_000_000},
            volatilities={"AAPL": 0.3, "MSFT": 0.25},
        )
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_total_costs(self, sim):
        sim.execute_order("AAPL", OrderSide.BUY, 100, current_price=150.0)
        sim.execute_order("MSFT", OrderSide.SELL, 50, current_price=300.0)
        costs = sim.get_total_costs()
        assert costs["num_trades"] == 2
        assert costs["total_cost"] > 0

    def test_market_impact_model(self):
        config = SimulatorConfig()
        impact_model = MarketImpactModel(config)
        cost = impact_model.compute_impact(
            order_value=100_000, daily_volume=1_000_000, volatility=0.3
        )
        assert cost > 0

    def test_reset_clears_history(self, sim):
        sim.execute_order("AAPL", OrderSide.BUY, 100)
        sim.reset()
        costs = sim.get_total_costs()
        assert costs["num_trades"] == 0
