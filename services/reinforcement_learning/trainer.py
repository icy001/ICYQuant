"""RL Trainer — orchestrates the training loop for RL trading agents.

Supports multiple algorithm interfaces: PPO, SAC, DQN, A2C.
Handles experience collection, policy updates, and training monitoring.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import math
import time
import json

import numpy as np

from .environment import RLTradingEnvironment, EnvironmentConfig, MarketState
from .policy_network import PolicyNetwork, PolicyConfig
from .reward_engine import RewardEngine, RewardConfig


class AlgorithmType(Enum):
    """Supported RL algorithms."""
    PPO = "ppo"
    SAC = "sac"
    DQN = "dqn"
    A2C = "a2c"
    TD3 = "td3"


@dataclass
class TrainerConfig:
    """Configuration for the RL trainer."""

    # Algorithm
    algorithm: AlgorithmType = AlgorithmType.PPO

    # Training loop
    total_timesteps: int = 1_000_000
    n_envs: int = 4
    n_steps: int = 2048  # steps per update
    batch_size: int = 64
    n_epochs: int = 10

    # PPO specific
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    target_kl: Optional[float] = 0.015

    # SAC specific
    tau: float = 0.005  # soft update
    alpha: float = 0.2  # entropy coefficient
    auto_alpha: bool = True

    # DQN specific
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 100_000
    target_update_freq: int = 1000

    # Logging
    log_interval: int = 1000
    eval_interval: int = 5000
    save_interval: int = 10000
    eval_episodes: int = 10

    # Checkpointing
    save_path: str = "./checkpoints"
    load_path: Optional[str] = None

    # Seed
    seed: int = 42


@dataclass
class TrainingEpisode:
    """Data for a single training episode."""

    states: List[np.ndarray] = field(default_factory=list)
    actions: List[np.ndarray] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    log_probs: List[float] = field(default_factory=list)
    dones: List[bool] = field(default_factory=list)
    total_reward: float = 0.0
    episode_length: int = 0


@dataclass
class TrainingMetrics:
    """Training progress metrics."""

    # Counters
    total_timesteps: int = 0
    total_episodes: int = 0
    total_updates: int = 0

    # Episode stats
    episode_reward_mean: float = 0.0
    episode_reward_std: float = 0.0
    episode_length_mean: float = 0.0

    # Policy stats
    policy_loss: float = 0.0
    value_loss: float = 0.0
    entropy: float = 0.0
    approx_kl: float = 0.0
    clip_fraction: float = 0.0

    # Performance
    fps: float = 0.0
    time_elapsed: float = 0.0

    # Evaluation
    eval_reward_mean: float = 0.0
    eval_sharpe: float = 0.0
    eval_drawdown: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_timesteps": self.total_timesteps,
            "total_episodes": self.total_episodes,
            "total_updates": self.total_updates,
            "episode_reward_mean": self.episode_reward_mean,
            "episode_reward_std": self.episode_reward_std,
            "policy_loss": self.policy_loss,
            "value_loss": self.value_loss,
            "entropy": self.entropy,
            "approx_kl": self.approx_kl,
            "eval_reward_mean": self.eval_reward_mean,
            "eval_sharpe": self.eval_sharpe,
            "eval_drawdown": self.eval_drawdown,
            "fps": self.fps,
        }


@dataclass
class TrainingResult:
    """Final training result."""

    metrics: TrainingMetrics
    final_policy: PolicyNetwork
    best_reward: float
    convergence_step: int
    training_history: List[TrainingMetrics] = field(default_factory=list)


class RLTrainer:
    """Main RL training orchestrator.

    Manages the complete training loop: experience collection,
    advantage estimation, policy updates, evaluation, and checkpointing.

    Supports PPO (primary), with interfaces for SAC, DQN, A2C.

    Usage:
        env = RLTradingEnvironment(env_config)
        policy = PolicyNetwork(policy_config)
        trainer = RLTrainer(env, policy, trainer_config)
        result = trainer.train()
    """

    def __init__(
        self,
        env: RLTradingEnvironment,
        policy: PolicyNetwork,
        config: Optional[TrainerConfig] = None,
        reward_engine: Optional[RewardEngine] = None,
    ):
        self.env = env
        self.policy = policy
        self.config = config or TrainerConfig()
        self.reward_engine = reward_engine or RewardEngine()

        self._metrics = TrainingMetrics()
        self._metrics_history: List[TrainingMetrics] = []
        self._best_reward = -float("inf")
        self._convergence_step = 0

        # PPO buffer
        self._buffer: List[Dict] = []

        # Tracking
        self._episode_rewards: List[float] = []
        self._start_time = 0.0

    def train(
        self,
        callback: Optional[Callable[[TrainingMetrics], None]] = None,
    ) -> TrainingResult:
        """Run full training loop.

        Args:
            callback: Optional callback called after each update

        Returns:
            TrainingResult with metrics and final policy
        """
        self._start_time = time.time()
        state = self.env.reset()
        episode_reward = 0.0
        episode_length = 0

        for step in range(self.config.total_timesteps):
            # Collect experience
            action, log_prob, value = self.policy.forward(state.to_vector())

            # Step environment
            env_action = self._convert_action(action)
            env_step = self.env.step(env_action)

            # Compute reward
            if self.reward_engine:
                reward = self.reward_engine.compute(
                    portfolio_return=env_step.info.get("pnl", 0.0) / 1e6,
                    current_drawdown=env_step.info.get("drawdown", 0.0),
                    turnover=sum(abs(v) for v in env_action.values()),
                )
            else:
                reward = env_step.reward

            episode_reward += reward
            episode_length += 1

            # Store transition
            self._buffer.append({
                "state": state.to_vector(),
                "action": action,
                "reward": reward,
                "value": value,
                "log_prob": log_prob,
                "done": env_step.done or env_step.truncated,
            })

            # Update on buffer full or episode end
            if len(self._buffer) >= self.config.n_steps or env_step.done:
                self._update_policy()

            # Episode end
            if env_step.done or env_step.truncated:
                self._episode_rewards.append(episode_reward)
                self._metrics.total_episodes += 1

                # Update episode stats
                if len(self._episode_rewards) >= 10:
                    recent = self._episode_rewards[-100:]
                    self._metrics.episode_reward_mean = float(np.mean(recent))
                    self._metrics.episode_reward_std = float(np.std(recent))

                state = self.env.reset()
                episode_reward = 0.0
                episode_length = 0
            else:
                state = env_step.state

            self._metrics.total_timesteps += 1

            # Logging
            if step > 0 and step % self.config.log_interval == 0:
                self._update_time_metrics()
                if callback:
                    callback(self._metrics)
                self._metrics_history.append(TrainingMetrics(
                    **{k: getattr(self._metrics, k)
                       for k in self._metrics.__dataclass_fields__}
                ))

            # Evaluation
            if step > 0 and step % self.config.eval_interval == 0:
                eval_reward, eval_sharpe, eval_dd = self._evaluate()
                self._metrics.eval_reward_mean = eval_reward
                self._metrics.eval_sharpe = eval_sharpe
                self._metrics.eval_drawdown = eval_dd

                if eval_reward > self._best_reward:
                    self._best_reward = eval_reward
                    self._convergence_step = step

            # Save checkpoint
            if step > 0 and step % self.config.save_interval == 0:
                self._save_checkpoint(step)

        # Final metrics
        self._update_time_metrics()

        return TrainingResult(
            metrics=self._metrics,
            final_policy=self.policy,
            best_reward=self._best_reward,
            convergence_step=self._convergence_step,
            training_history=self._metrics_history,
        )

    def _update_policy(self):
        """Perform policy update (PPO)."""
        if len(self._buffer) < 2:
            return

        self._metrics.total_updates += 1

        # Prepare batch data
        states = np.array([t["state"] for t in self._buffer])
        actions = np.array([t["action"] for t in self._buffer])
        old_log_probs = np.array([t["log_prob"] for t in self._buffer])
        rewards = np.array([t["reward"] for t in self._buffer])
        values = np.array([t["value"] for t in self._buffer])
        dones = np.array([t["done"] for t in self._buffer])

        # Compute advantages and returns (GAE)
        advantages, returns = self._compute_gae(rewards, values, dones)
        advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)

        # PPO update epochs
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_kl = 0.0

        n_batches = max(1, len(states) // self.config.batch_size)
        for epoch in range(self.config.n_epochs):
            indices = np.random.permutation(len(states))

            for batch_start in range(0, len(states), self.config.batch_size):
                batch_idx = indices[batch_start:batch_start + self.config.batch_size]

                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]

                # Forward pass
                new_log_probs = []
                new_values = []
                entropies = []

                for i in range(len(batch_states)):
                    a, lp, v = self.policy.forward(batch_states[i])
                    new_log_probs.append(lp)
                    new_values.append(v)
                    # Entropy for Gaussian
                    log_std = self.policy._params.get("log_std", np.zeros(1))
                    entropy = float(np.mean(0.5 * np.log(2 * math.pi * math.e * np.exp(2 * log_std))))
                    entropies.append(entropy)

                new_log_probs = np.array(new_log_probs)
                new_values = np.array(new_values)

                # Policy loss (PPO clipped)
                ratio = np.exp(new_log_probs - batch_old_log_probs)
                clipped_ratio = np.clip(
                    ratio, 1 - self.config.clip_range, 1 + self.config.clip_range
                )
                policy_loss = -np.mean(
                    np.minimum(
                        ratio * batch_advantages,
                        clipped_ratio * batch_advantages,
                    )
                )
                total_policy_loss += float(policy_loss)

                # Value loss
                value_loss = np.mean((new_values - batch_returns) ** 2)
                total_value_loss += float(value_loss)

                # Entropy
                batch_entropy = np.mean(entropies)
                total_entropy += float(batch_entropy)

                # KL divergence
                kl = float(np.mean(batch_old_log_probs - new_log_probs))
                total_kl += kl

                # Simple SGD update (in practice use optimizer)
                # Here we just track losses since we can't backprop in pure numpy
                # The actual gradient update would be done by an optimizer

                # Early stopping on KL
                if self.config.target_kl and kl > self.config.target_kl * 1.5:
                    break

        n_updates = max(1, n_batches * self.config.n_epochs)
        self._metrics.policy_loss = total_policy_loss / n_updates
        self._metrics.value_loss = total_value_loss / n_updates
        self._metrics.entropy = total_entropy / n_updates
        self._metrics.approx_kl = total_kl / n_updates

        # Clear buffer
        self._buffer = []

    def _compute_gae(
        self,
        rewards: np.ndarray,
        values: np.ndarray,
        dones: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute Generalized Advantage Estimation."""
        advantages = np.zeros_like(rewards)
        last_advantage = 0.0
        last_value = 0.0

        for t in reversed(range(len(rewards))):
            mask = 1.0 - float(dones[t])
            delta = rewards[t] + self.config.gamma * last_value * mask - values[t]
            last_advantage = (
                delta
                + self.config.gamma * self.config.gae_lambda * mask * last_advantage
            )
            advantages[t] = last_advantage
            last_value = values[t]

        returns = advantages + values
        return advantages, returns

    def _convert_action(
        self, action: np.ndarray
    ) -> Dict[str, float]:
        """Convert policy output to environment action."""
        symbols = self.env.config.symbols
        result = {}
        for i, s in enumerate(symbols):
            if i < len(action):
                result[s] = float(action[i])
            else:
                result[s] = 0.0
        return result

    def _evaluate(self) -> Tuple[float, float, float]:
        """Evaluate current policy."""
        total_rewards = []
        total_returns = []
        total_drawdowns = []

        old_seed = self.env.config.seed
        self.env.config.seed = 999  # eval seed

        for _ in range(self.config.eval_episodes):
            state = self.env.reset()
            done = False
            ep_reward = 0.0

            while not done:
                action, _, _ = self.policy.forward(
                    state.to_vector(), deterministic=True
                )
                env_action = self._convert_action(action)
                step = self.env.step(env_action)
                ep_reward += step.reward
                done = step.done or step.truncated

            episode = self.env.get_episode_summary()
            total_rewards.append(ep_reward)
            total_returns.append(episode.total_return)
            total_drawdowns.append(episode.max_drawdown)

        self.env.config.seed = old_seed

        mean_reward = float(np.mean(total_rewards)) if total_rewards else 0.0
        mean_sharpe = (
            float(np.mean(total_returns)) / (float(np.std(total_returns)) + 1e-8)
            if total_returns else 0.0
        )
        mean_dd = float(np.mean(total_drawdowns)) if total_drawdowns else 0.0

        return mean_reward, mean_sharpe, mean_dd

    def _update_time_metrics(self):
        """Update time-based metrics."""
        elapsed = time.time() - self._start_time
        self._metrics.time_elapsed = elapsed
        self._metrics.fps = (
            self._metrics.total_timesteps / elapsed if elapsed > 0 else 0.0
        )

    def _save_checkpoint(self, step: int):
        """Save training checkpoint."""
        # In production, save to disk. Here we just track.
        pass

    def get_metrics(self) -> TrainingMetrics:
        """Get current training metrics."""
        return self._metrics

    def get_training_history(self) -> List[TrainingMetrics]:
        """Get full training metrics history."""
        return self._metrics_history
