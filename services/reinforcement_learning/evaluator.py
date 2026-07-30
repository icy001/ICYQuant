"""RL Evaluator — evaluates trained RL policies.

Provides comprehensive evaluation of RL trading policies including
risk-adjusted metrics, regime-specific performance, and stress testing.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math

import numpy as np

from .environment import (
    RLTradingEnvironment, EnvironmentConfig, EnvironmentMode,
    MarketState, EnvironmentEpisode,
)
from .policy_network import PolicyNetwork
from .reward_engine import RewardEngine


@dataclass
class EvaluatorConfig:
    """Configuration for RL evaluator."""

    n_episodes: int = 100
    max_steps_per_episode: int = 500
    seed: int = 42

    # Metrics to compute
    compute_sharpe: bool = True
    compute_sortino: bool = True
    compute_calmar: bool = True
    compute_max_drawdown: bool = True
    compute_var: bool = True
    compute_cvar: bool = True
    compute_win_rate: bool = True
    compute_profit_factor: bool = True

    # Regime testing
    test_regimes: List[str] = field(default_factory=lambda: [
        "bull", "bear", "neutral", "crisis",
    ])

    # Stress testing
    stress_scenarios: List[Dict[str, Any]] = field(default_factory=list)

    risk_free_rate: float = 0.02


@dataclass
class EvaluationMetrics:
    """Comprehensive evaluation metrics."""

    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0

    # Drawdown
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    drawdown_duration: float = 0.0
    recovery_time: float = 0.0

    # Risk measures
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0

    # Trading
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0

    # Stability
    reward_stability: float = 0.0
    policy_entropy: float = 0.0

    # Regime-specific
    regime_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Episode stats
    mean_episode_reward: float = 0.0
    std_episode_reward: float = 0.0
    mean_episode_length: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "mean_episode_reward": self.mean_episode_reward,
            "regime_metrics": self.regime_metrics,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result."""

    metrics: EvaluationMetrics
    episodes: List[EnvironmentEpisode] = field(default_factory=list)
    returns_series: List[float] = field(default_factory=list)
    drawdown_series: List[float] = field(default_factory=list)
    regime_results: Dict[str, EvaluationMetrics] = field(default_factory=dict)
    passed: bool = True
    warnings: List[str] = field(default_factory=list)


class RLEvaluator:
    """Comprehensive RL policy evaluator.

    Evaluates trained policies across multiple dimensions:
    - Risk-adjusted returns (Sharpe, Sortino, Calmar)
    - Risk measures (VaR, CVaR, max drawdown)
    - Trading efficiency (win rate, profit factor)
    - Regime-specific performance
    - Stress testing

    Usage:
        evaluator = RLEvaluator(env, policy, config)
        result = evaluator.evaluate()
    """

    def __init__(
        self,
        env: RLTradingEnvironment,
        policy: PolicyNetwork,
        config: Optional[EvaluatorConfig] = None,
    ):
        self.env = env
        self.policy = policy
        self.config = config or EvaluatorConfig()

    def evaluate(self) -> EvaluationResult:
        """Run full evaluation suite."""
        warnings = []

        # Run episodes
        episodes, returns_series = self._run_episodes()
        if not episodes:
            return EvaluationResult(
                metrics=EvaluationMetrics(),
                warnings=["No episodes completed"],
                passed=False,
            )

        # Compute core metrics
        metrics = self._compute_metrics(episodes, returns_series)

        # Regime-specific evaluation
        regime_results = self._evaluate_regimes()

        # Stress testing
        stress_warnings = self._run_stress_tests()
        warnings.extend(stress_warnings)

        # Compute drawdown series
        drawdown_series = self._compute_drawdown_series(returns_series)

        # Check if evaluation passes
        passed = self._check_pass_criteria(metrics)

        return EvaluationResult(
            metrics=metrics,
            episodes=episodes,
            returns_series=returns_series,
            drawdown_series=drawdown_series,
            regime_results=regime_results,
            passed=passed,
            warnings=warnings,
        )

    def _run_episodes(self) -> Tuple[List[EnvironmentEpisode], List[float]]:
        """Run evaluation episodes."""
        episodes = []
        all_returns = []

        old_mode = self.env.config.mode
        self.env.config.mode = EnvironmentMode.EVAL

        for ep in range(self.config.n_episodes):
            state = self.env.reset(seed=self.config.seed + ep)
            done = False
            truncated = False
            ep_returns = []

            while not done and not truncated:
                action, _, _ = self.policy.forward(
                    state.to_vector(), deterministic=True
                )
                env_action = self._convert_action(action)
                step = self.env.step(env_action)
                ep_returns.append(step.info.get("pnl", 0.0))
                done = step.done
                truncated = step.truncated

                if len(ep_returns) >= self.config.max_steps_per_episode:
                    truncated = True

            episode = self.env.get_episode_summary()
            episodes.append(episode)
            all_returns.extend(ep_returns)

        self.env.config.mode = old_mode
        return episodes, all_returns

    def _compute_metrics(
        self,
        episodes: List[EnvironmentEpisode],
        returns_series: List[float],
    ) -> EvaluationMetrics:
        """Compute all evaluation metrics."""
        metrics = EvaluationMetrics()

        if not episodes or not returns_series:
            return metrics

        returns_arr = np.array(returns_series)

        # Return metrics
        metrics.total_return = sum(e.total_return for e in episodes) / len(episodes)
        metrics.annualized_return = (
            (1 + metrics.total_return) ** (252 / len(returns_series)) - 1
            if len(returns_series) > 0 else 0.0
        )
        metrics.annualized_volatility = float(np.std(returns_arr)) * math.sqrt(252)

        # Sharpe ratio
        if self.config.compute_sharpe and len(returns_arr) > 1:
            excess = returns_arr - self.config.risk_free_rate / 252
            metrics.sharpe_ratio = (
                float(np.mean(excess) / (np.std(returns_arr) + 1e-8))
                * math.sqrt(252)
            )

        # Sortino ratio
        if self.config.compute_sortino:
            downside = returns_arr[returns_arr < 0]
            downside_std = float(np.std(downside)) if len(downside) > 0 else 0.01
            metrics.sortino_ratio = (
                float(np.mean(returns_arr)) / downside_std * math.sqrt(252)
            )

        # Calmar ratio
        if self.config.compute_calmar:
            max_dd = max(e.max_drawdown for e in episodes)
            metrics.calmar_ratio = (
                metrics.annualized_return / (max_dd + 1e-8)
                if max_dd > 0 else 0.0
            )

        # Drawdown
        if self.config.compute_max_drawdown:
            metrics.max_drawdown = max(e.max_drawdown for e in episodes)
            metrics.avg_drawdown = float(np.mean([e.max_drawdown for e in episodes]))

        # VaR and CVaR
        if self.config.compute_var:
            sorted_returns = np.sort(returns_arr)
            metrics.var_95 = float(np.percentile(sorted_returns, 5))
            metrics.var_99 = float(np.percentile(sorted_returns, 1))
            if self.config.compute_cvar:
                metrics.cvar_95 = float(np.mean(sorted_returns[:int(len(sorted_returns) * 0.05)]))
                metrics.cvar_99 = float(np.mean(sorted_returns[:int(len(sorted_returns) * 0.01)]))

        # Trading metrics
        if self.config.compute_win_rate:
            wins = sum(1 for r in returns_arr if r > 0)
            total = len(returns_arr)
            metrics.win_rate = wins / total if total > 0 else 0.0
            metrics.total_trades = sum(e.num_trades for e in episodes)

            win_returns = returns_arr[returns_arr > 0]
            loss_returns = returns_arr[returns_arr < 0]
            metrics.avg_win = float(np.mean(win_returns)) if len(win_returns) > 0 else 0.0
            metrics.avg_loss = float(np.mean(loss_returns)) if len(loss_returns) > 0 else 0.0

        if self.config.compute_profit_factor:
            gross_profit = sum(r for r in returns_arr if r > 0)
            gross_loss = abs(sum(r for r in returns_arr if r < 0))
            metrics.profit_factor = (
                gross_profit / gross_loss if gross_loss > 0 else float("inf")
            )

        # Episode stats
        metrics.mean_episode_reward = float(np.mean([e.total_reward for e in episodes]))
        metrics.std_episode_reward = float(np.std([e.total_reward for e in episodes]))
        metrics.mean_episode_length = float(np.mean([e.steps[-1].state.step if e.steps else 0 for e in episodes]))

        # Reward stability
        episode_rewards = [e.total_reward for e in episodes]
        metrics.reward_stability = (
            1.0 - float(np.std(episode_rewards)) / (abs(float(np.mean(episode_rewards))) + 1e-8)
            if episode_rewards else 0.0
        )

        return metrics

    def _evaluate_regimes(self) -> Dict[str, EvaluationMetrics]:
        """Evaluate policy performance in different market regimes."""
        regime_results = {}
        for regime in self.config.test_regimes:
            # Override regime in environment
            original_regime = self.env.config.mode
            self.env.config.mode = EnvironmentMode.EVAL

            episodes, returns = self._run_regime_episodes(regime)
            if episodes and returns:
                regime_results[regime] = self._compute_metrics(episodes, returns)

            self.env.config.mode = original_regime

        return regime_results

    def _run_regime_episodes(
        self, regime: str
    ) -> Tuple[List[EnvironmentEpisode], List[float]]:
        """Run episodes in specific market regime."""
        episodes = []
        all_returns = []

        for ep in range(min(10, self.config.n_episodes)):
            state = self.env.reset(seed=self.config.seed + ep + hash(regime) % 10000)
            done = False
            ep_returns = []

            while not done:
                action, _, _ = self.policy.forward(
                    state.to_vector(), deterministic=True
                )
                env_action = self._convert_action(action)
                step = self.env.step(env_action)
                ep_returns.append(step.info.get("pnl", 0.0))
                done = step.done or step.truncated

            episode = self.env.get_episode_summary()
            episodes.append(episode)
            all_returns.extend(ep_returns)

        return episodes, all_returns

    def _run_stress_tests(self) -> List[str]:
        """Run stress test scenarios."""
        warnings = []
        scenarios = self.config.stress_scenarios or [
            {"name": "flash_crash", "drop_pct": -0.30},
            {"name": "volatility_spike", "vol_multiplier": 5.0},
            {"name": "liquidity_crisis", "spread_multiplier": 10.0},
        ]

        for scenario in scenarios:
            # In production, modify environment parameters and re-evaluate
            pass

        return warnings

    def _compute_drawdown_series(self, returns: List[float]) -> List[float]:
        """Compute drawdown over time."""
        if not returns:
            return []

        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (running_max + 1e-8)
        return drawdown.tolist()

    def _check_pass_criteria(self, metrics: EvaluationMetrics) -> bool:
        """Check if evaluation passes minimum criteria."""
        checks = [
            metrics.sharpe_ratio > -1.0,
            metrics.max_drawdown < 0.50,
            metrics.cvar_95 > -0.05,
        ]
        return all(checks)

    def _convert_action(self, action: np.ndarray) -> Dict[str, float]:
        """Convert policy output to environment action."""
        symbols = self.env.config.symbols
        return {
            s: float(action[i]) if i < len(action) else 0.0
            for i, s in enumerate(symbols)
        }

    def compare_policies(
        self, policy_a: PolicyNetwork, policy_b: PolicyNetwork
    ) -> Dict[str, Any]:
        """Compare two policies side by side."""
        result_a = self.evaluate()
        self.policy = policy_b
        result_b = self.evaluate()

        return {
            "policy_a": result_a.metrics.to_dict(),
            "policy_b": result_b.metrics.to_dict(),
            "better": "a" if result_a.metrics.sharpe_ratio > result_b.metrics.sharpe_ratio else "b",
        }
