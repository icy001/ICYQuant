"""RL Trading Environment — simulates market for reinforcement learning.

Models a realistic trading environment with price dynamics, order flow,
and portfolio state. Compliant with OpenAI Gym-like interface.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math
import random
from enum import Enum

import numpy as np


class EnvironmentMode(Enum):
    """Operating mode for the RL environment."""
    TRAIN = "train"
    EVAL = "eval"
    BACKTEST = "backtest"
    LIVE = "live"


@dataclass
class EnvironmentConfig:
    """Configuration for the RL trading environment."""

    # Market data
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA"])
    initial_balance: float = 1_000_000.0
    max_position_pct: float = 0.25
    commission_rate: float = 0.001
    slippage_bps: float = 1.0
    spread_bps: float = 2.0

    # Episode settings
    max_steps: int = 252  # ~1 trading year
    window_size: int = 50  # lookback window for state

    # Environment settings
    mode: EnvironmentMode = EnvironmentMode.TRAIN
    seed: Optional[int] = None
    render: bool = False

    # Risk limits
    max_drawdown_pct: float = 0.20
    max_leverage: float = 2.0
    var_limit_pct: float = 0.05


@dataclass
class MarketState:
    """Current market state observation."""

    # Price data per symbol
    prices: Dict[str, float] = field(default_factory=dict)
    returns: Dict[str, float] = field(default_factory=dict)
    volumes: Dict[str, float] = field(default_factory=dict)
    volatility: Dict[str, float] = field(default_factory=dict)
    spreads: Dict[str, float] = field(default_factory=dict)

    # Aggregate market metrics
    market_sentiment: float = 0.0
    market_regime: str = "neutral"
    vix_level: float = 20.0

    # Portfolio state
    portfolio_value: float = 0.0
    cash: float = 0.0
    positions: Dict[str, float] = field(default_factory=dict)
    position_pct: Dict[str, float] = field(default_factory=dict)
    total_exposure: float = 0.0
    leverage: float = 0.0

    # Risk metrics
    current_drawdown: float = 0.0
    portfolio_var: float = 0.0
    sharpe_ratio: float = 0.0

    # Time
    step: int = 0
    timestamp: Optional[str] = None

    def to_vector(self) -> np.ndarray:
        """Convert state to flat feature vector."""
        vec = []
        for s in sorted(self.prices.keys()):
            vec.extend([
                self.prices.get(s, 0.0),
                self.returns.get(s, 0.0),
                self.volumes.get(s, 0.0),
                self.volatility.get(s, 0.0),
                self.position_pct.get(s, 0.0),
            ])
        vec.extend([
            self.market_sentiment,
            self.portfolio_value,
            self.cash,
            self.total_exposure,
            self.leverage,
            self.current_drawdown,
        ])
        return np.array(vec, dtype=np.float32)


@dataclass
class EnvironmentStep:
    """Result of one environment step."""

    state: MarketState
    action: Any
    reward: float
    done: bool
    truncated: bool = False
    info: Dict[str, Any] = field(default_factory=dict)
    next_state: Optional[MarketState] = None


@dataclass
class EnvironmentEpisode:
    """Summary of a complete episode."""

    total_reward: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    num_trades: int = 0
    steps: List[EnvironmentStep] = field(default_factory=list)
    final_value: float = 0.0


class RLTradingEnvironment:
    """Main RL trading environment.

    Simulates a multi-asset trading environment with realistic market
    dynamics, transaction costs, and risk constraints.

    Usage:
        env = RLTradingEnvironment(config)
        state = env.reset()
        while not done:
            action = agent.act(state)
            next_state, reward, done, info = env.step(action)
    """

    def __init__(self, config: Optional[EnvironmentConfig] = None):
        self.config = config or EnvironmentConfig()
        self._rng = random.Random(self.config.seed)

        # Internal state
        self._current_step: int = 0
        self._initial_balance: float = self.config.initial_balance
        self._portfolio_value: float = self.config.initial_balance
        self._peak_value: float = self.config.initial_balance
        self._cash: float = self.config.initial_balance
        self._positions: Dict[str, float] = {}
        self._price_history: Dict[str, List[float]] = {}
        self._return_history: List[float] = []
        self._episode_steps: List[EnvironmentStep] = []

        # Market data simulation
        self._init_market_data()

    def _init_market_data(self):
        """Initialize simulated market data."""
        for symbol in self.config.symbols:
            self._positions[symbol] = 0.0
            self._price_history[symbol] = [100.0 + self._rng.uniform(-20, 20)]

    def reset(self, seed: Optional[int] = None) -> MarketState:
        """Reset environment to initial state."""
        if seed is not None:
            self._rng = random.Random(seed)
            self.config.seed = seed

        self._current_step = 0
        self._portfolio_value = self._initial_balance
        self._peak_value = self._initial_balance
        self._cash = self._initial_balance
        self._return_history = []
        self._episode_steps = []

        for symbol in self.config.symbols:
            self._positions[symbol] = 0.0
            self._price_history[symbol] = [self._price_history[symbol][0]]

        return self._get_observation()

    def step(self, action: Dict[str, float]) -> EnvironmentStep:
        """Execute one step in the environment.

        Args:
            action: Dict mapping symbol -> target position weight
                    e.g. {"AAPL": 0.2, "MSFT": -0.1, "NVDA": 0.0}
        """
        self._current_step += 1
        old_value = self._portfolio_value

        # Update market prices
        self._update_market_prices()

        # Execute trades
        trade_pnl, trade_cost = self._execute_trades(action)

        # Update portfolio value
        self._portfolio_value = self._cash + sum(
            self._positions[s] * self._price_history[s][-1]
            for s in self.config.symbols
        )

        if self._portfolio_value > self._peak_value:
            self._peak_value = self._portfolio_value

        portfolio_return = (
            (self._portfolio_value - old_value) / old_value
            if old_value > 0 else 0.0
        )
        self._return_history.append(portfolio_return)

        # Get observation
        state = self._get_observation()

        # Check termination
        done, truncated = self._check_termination()

        # Compute reward
        reward = self._compute_default_reward(trade_pnl, trade_cost)

        step_result = EnvironmentStep(
            state=state,
            action=action,
            reward=reward,
            done=done,
            truncated=truncated,
            info={
                "step": self._current_step,
                "portfolio_value": self._portfolio_value,
                "pnl": trade_pnl,
                "cost": trade_cost,
                "drawdown": state.current_drawdown,
                "sharpe": state.sharpe_ratio,
            },
        )
        self._episode_steps.append(step_result)
        return step_result

    def _update_market_prices(self):
        """Update simulated market prices with stochastic dynamics."""
        for symbol in self.config.symbols:
            last_price = self._price_history[symbol][-1]
            # Geometric Brownian motion with mean reversion
            drift = 0.0001 * self._rng.gauss(0, 1)
            vol = 0.02 * abs(self._rng.gauss(0, 1))
            returns = drift + vol * self._rng.gauss(0, 1)
            new_price = last_price * math.exp(returns)
            new_price = max(new_price, last_price * 0.01)  # floor
            self._price_history[symbol].append(new_price)

    def _execute_trades(
        self, action: Dict[str, float]
    ) -> Tuple[float, float]:
        """Execute trades from action and compute PnL and costs."""
        total_pnl = 0.0
        total_cost = 0.0

        for symbol, target_weight in action.items():
            if symbol not in self.config.symbols:
                continue

            current_price = self._price_history[symbol][-1]
            current_position = self._positions.get(symbol, 0.0)
            current_value = current_position * current_price

            target_value = target_weight * self._portfolio_value
            target_value = max(
                target_value,
                -self.config.max_position_pct * self._portfolio_value,
            )
            target_value = min(
                target_value,
                self.config.max_position_pct * self._portfolio_value,
            )

            delta_value = target_value - current_value

            if abs(delta_value) < 1.0:
                continue

            # Apply slippage and commission
            slippage = abs(delta_value) * self.config.slippage_bps / 10000.0
            commission = abs(delta_value) * self.config.commission_rate
            cost = slippage + commission

            # Execute
            new_position = target_value / current_price if current_price > 0 else 0.0
            self._cash -= (delta_value + cost)
            self._positions[symbol] = new_position

            total_pnl += delta_value
            total_cost += cost

        return total_pnl, total_cost

    def _get_observation(self) -> MarketState:
        """Build current market state observation."""
        prices = {}
        returns = {}
        volumes = {}
        volatility = {}
        spreads = {}
        position_pct = {}

        for symbol in self.config.symbols:
            history = self._price_history[symbol]
            prices[symbol] = history[-1]
            returns[symbol] = (
                (history[-1] - history[-2]) / history[-2]
                if len(history) >= 2 else 0.0
            )
            volumes[symbol] = abs(self._rng.gauss(1_000_000, 200_000))
            # Simple historical volatility
            if len(history) >= 21:
                rets = [
                    (history[i] - history[i - 1]) / history[i - 1]
                    for i in range(-20, 0) if len(history) > abs(i)
                ]
                volatility[symbol] = np.std(rets) * math.sqrt(252) if rets else 0.0
            else:
                volatility[symbol] = 0.3
            spreads[symbol] = prices[symbol] * self.config.spread_bps / 10000.0
            position_pct[symbol] = (
                self._positions.get(symbol, 0.0) * prices[symbol]
                / self._portfolio_value
                if self._portfolio_value > 0 else 0.0
            )

        total_exposure = sum(
            abs(self._positions.get(s, 0.0) * prices.get(s, 0.0))
            for s in self.config.symbols
        )

        current_drawdown = (
            (self._peak_value - self._portfolio_value) / self._peak_value
            if self._peak_value > 0 else 0.0
        )

        # Sharpe ratio
        if len(self._return_history) > 1:
            ret_arr = np.array(self._return_history)
            mean_ret = np.mean(ret_arr)
            std_ret = np.std(ret_arr)
            sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        else:
            sharpe = 0.0

        return MarketState(
            prices=prices,
            returns=returns,
            volumes=volumes,
            volatility=volatility,
            spreads=spreads,
            market_sentiment=self._rng.uniform(-1, 1),
            market_regime="bull" if self._rng.random() > 0.5 else "bear",
            portfolio_value=self._portfolio_value,
            cash=self._cash,
            positions=self._positions.copy(),
            position_pct=position_pct,
            total_exposure=total_exposure,
            leverage=total_exposure / self._portfolio_value if self._portfolio_value > 0 else 0.0,
            current_drawdown=current_drawdown,
            portfolio_var=0.02,
            sharpe_ratio=sharpe,
            step=self._current_step,
        )

    def _check_termination(self) -> Tuple[bool, bool]:
        """Check if episode should end."""
        done = False
        truncated = False

        # Max steps reached
        if self._current_step >= self.config.max_steps:
            truncated = True
            return done, truncated

        # Drawdown limit
        dd = (
            (self._peak_value - self._portfolio_value) / self._peak_value
            if self._peak_value > 0 else 0.0
        )
        if dd >= self.config.max_drawdown_pct:
            done = True

        # Bankruptcy
        if self._portfolio_value <= self._initial_balance * 0.01:
            done = True

        return done, truncated

    def _compute_default_reward(self, pnl: float, cost: float) -> float:
        """Compute default reward: return minus costs."""
        return pnl - cost

    def get_episode_summary(self) -> EnvironmentEpisode:
        """Get summary of current episode."""
        total_reward = sum(s.reward for s in self._episode_steps)
        total_return = (
            (self._portfolio_value - self._initial_balance) / self._initial_balance
            if self._initial_balance > 0 else 0.0
        )
        max_dd = max(
            (s.state.current_drawdown for s in self._episode_steps),
            default=0.0,
        )
        sharpe = (
            self._episode_steps[-1].state.sharpe_ratio
            if self._episode_steps else 0.0
        )

        return EnvironmentEpisode(
            total_reward=total_reward,
            total_return=total_return,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            num_trades=sum(
                1 for s in self._episode_steps
                if any(abs(v) > 1e-6 for v in s.action.values())
            ),
            steps=self._episode_steps.copy(),
            final_value=self._portfolio_value,
        )

    @property
    def action_dim(self) -> int:
        """Dimension of action space."""
        return len(self.config.symbols)

    @property
    def state_dim(self) -> int:
        """Dimension of state space."""
        return len(self.config.symbols) * 5 + 6
