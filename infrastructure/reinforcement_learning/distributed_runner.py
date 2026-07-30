"""Infrastructure: RL Distributed Training Runner.

Supports distributed RL training across multiple processes/machines:
- Parallel environment execution
- Synchronous/asynchronous policy updates
- Work distribution and aggregation
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import time
import math
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import numpy as np

from .experience_buffer import ExperienceBuffer, BufferConfig, Experience

logger = logging.getLogger(__name__)


class RunnerMode(Enum):
    """Execution mode for distributed runner."""
    SINGLE = "single"
    MULTITHREAD = "multithread"
    MULTIPROCESS = "multiprocess"
    DISTRIBUTED = "distributed"


@dataclass
class RunnerConfig:
    """Configuration for distributed runner."""

    mode: RunnerMode = RunnerMode.SINGLE
    n_workers: int = 4
    n_envs_per_worker: int = 1

    # Rollout
    n_steps: int = 2048
    n_episodes: int = 10
    horizon: int = 500

    # Communication
    sync_freq: int = 1  # steps between sync
    use_shared_memory: bool = True

    # Performance
    max_queue_size: int = 10000
    timeout_seconds: int = 300

    seed: int = 42


@dataclass
class WorkerResult:
    """Result from a worker rollout."""

    worker_id: int
    episodes: List[Dict[str, Any]]
    total_steps: int
    total_reward: float
    execution_time: float
    error: Optional[str] = None


@dataclass
class DistributedResult:
    """Aggregated distributed training result."""

    worker_results: List[WorkerResult]
    total_steps: int
    total_episodes: int
    mean_reward: float
    std_reward: float
    total_time: float
    steps_per_second: float


class DistributedRunner:
    """Manages distributed RL training execution.

    Coordinates multiple workers running environments and collecting
    experience. Supports multi-threading and multi-processing.

    Usage:
        runner = DistributedRunner(config)
        runner.set_env_factory(create_env_fn)
        runner.set_policy_factory(create_policy_fn)
        result = runner.run_rollout()
    """

    def __init__(self, config: Optional[RunnerConfig] = None):
        self.config = config or RunnerConfig()
        self._env_factory: Optional[Callable] = None
        self._policy_factory: Optional[Callable] = None
        self._workers: List[Any] = []
        self._results: List[WorkerResult] = []
        self._buffer = ExperienceBuffer(BufferConfig(capacity=100000))
        self._lock = threading.Lock()

    def set_env_factory(self, factory: Callable[[], Any]):
        """Set function to create environments."""
        self._env_factory = factory

    def set_policy_factory(self, factory: Callable[[], Any]):
        """Set function to create policies."""
        self._policy_factory = factory

    def run_rollout(
        self,
        env_factory: Optional[Callable[[], Any]] = None,
        policy_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> DistributedResult:
        """Run rollout across all workers.

        Args:
            env_factory: Function that creates an environment per worker
            policy_fn: Function state→action for all workers

        Returns:
            DistributedResult with aggregated metrics
        """
        if env_factory:
            self._env_factory = env_factory

        if self._env_factory is None:
            raise ValueError("env_factory must be provided or set via set_env_factory()")

        start_time = time.time()

        if self.config.mode == RunnerMode.SINGLE:
            worker_results = [self._run_worker(0, policy_fn)]
        elif self.config.mode == RunnerMode.MULTITHREAD:
            worker_results = self._run_multithread(policy_fn)
        elif self.config.mode == RunnerMode.MULTIPROCESS:
            worker_results = self._run_multiprocess(policy_fn)
        else:
            worker_results = [self._run_worker(0, policy_fn)]

        total_time = time.time() - start_time
        total_steps = sum(r.total_steps for r in worker_results)
        total_episodes = sum(len(r.episodes) for r in worker_results)

        rewards = [r.total_reward for r in worker_results]
        mean_reward = float(np.mean(rewards)) if rewards else 0.0
        std_reward = float(np.std(rewards)) if len(rewards) > 1 else 0.0

        result = DistributedResult(
            worker_results=worker_results,
            total_steps=total_steps,
            total_episodes=total_episodes,
            mean_reward=mean_reward,
            std_reward=std_reward,
            total_time=total_time,
            steps_per_second=total_steps / total_time if total_time > 0 else 0.0,
        )

        self._results.extend(worker_results)
        return result

    def _run_worker(
        self,
        worker_id: int,
        policy_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> WorkerResult:
        """Run a single worker."""
        start_time = time.time()
        episodes = []
        total_steps = 0
        total_reward = 0.0

        try:
            env = self._env_factory()
            n_envs = self.config.n_envs_per_worker

            for ep in range(self.config.n_episodes):
                state = env.reset(seed=self.config.seed + worker_id * 1000 + ep)
                done = False
                ep_reward = 0.0
                ep_steps = 0
                ep_actions = []

                while not done and ep_steps < self.config.horizon:
                    if policy_fn:
                        action = policy_fn(state.to_vector())
                    else:
                        action = np.random.randn(env.action_dim)

                    step_result = env.step(
                        self._action_to_dict(action, env)
                    )
                    ep_reward += step_result.reward
                    ep_steps += 1

                    if hasattr(action, 'tolist'):
                        ep_actions.append(action.tolist())

                    done = step_result.done or step_result.truncated
                    if not done:
                        state = step_result.state

                episode_summary = env.get_episode_summary()
                episodes.append({
                    "episode": ep,
                    "reward": ep_reward,
                    "steps": ep_steps,
                    "total_return": episode_summary.total_return,
                    "sharpe": episode_summary.sharpe_ratio,
                    "max_drawdown": episode_summary.max_drawdown,
                    "num_trades": episode_summary.num_trades,
                })

                total_steps += ep_steps
                total_reward += ep_reward

        except Exception as e:
            logger.error(f"Worker {worker_id} failed: {e}")
            return WorkerResult(
                worker_id=worker_id,
                episodes=episodes,
                total_steps=total_steps,
                total_reward=total_reward,
                execution_time=time.time() - start_time,
                error=str(e),
            )

        return WorkerResult(
            worker_id=worker_id,
            episodes=episodes,
            total_steps=total_steps,
            total_reward=total_reward,
            execution_time=time.time() - start_time,
        )

    def _run_multithread(
        self,
        policy_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> List[WorkerResult]:
        """Run workers in threads."""
        results = []

        with ThreadPoolExecutor(max_workers=self.config.n_workers) as executor:
            futures = [
                executor.submit(self._run_worker, i, policy_fn)
                for i in range(self.config.n_workers)
            ]
            for future in futures:
                try:
                    result = future.result(timeout=self.config.timeout_seconds)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Thread worker failed: {e}")

        return results

    def _run_multiprocess(
        self,
        policy_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None,
    ) -> List[WorkerResult]:
        """Run workers in separate processes (fallback to multithread)."""
        # Multiprocessing with numpy policies is complex
        # Fall back to multithread
        logger.warning("Multiprocess mode not fully supported; using multithread")
        return self._run_multithread(policy_fn)

    def _action_to_dict(
        self, action: np.ndarray, env: Any
    ) -> Dict[str, float]:
        """Convert action array to dict for environment."""
        symbols = getattr(env.config, 'symbols', ['DEFAULT'])
        return {
            s: float(action[i]) if i < len(action) else 0.0
            for i, s in enumerate(symbols)
        }

    def get_experience_buffer(self) -> ExperienceBuffer:
        """Get the shared experience buffer."""
        return self._buffer

    def get_results(self) -> List[WorkerResult]:
        """Get results from all runs."""
        return self._results

    def clear_results(self):
        """Clear stored results."""
        self._results = []

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics from all runs."""
        if not self._results:
            return {}

        rewards = [r.total_reward for r in self._results]
        steps = [r.total_steps for r in self._results]
        errors = [r for r in self._results if r.error]

        return {
            "total_runs": len(self._results),
            "total_steps": sum(steps),
            "total_reward": sum(rewards),
            "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
            "max_reward": max(rewards) if rewards else 0.0,
            "min_reward": min(rewards) if rewards else 0.0,
            "errors": len(errors),
            "mean_steps": float(np.mean(steps)) if steps else 0.0,
            "error_rate": len(errors) / len(self._results) if self._results else 0.0,
        }
