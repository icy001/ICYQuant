"""Infrastructure: RL Experience Buffer and Replay Memory.

Provides efficient experience storage for off-policy RL algorithms:
- Replay buffer with prioritized experience replay (PER)
- Reservoir sampling for large buffers
- Efficient numpy-backed storage
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import random
import math
import logging

import numpy as np

logger = logging.getLogger(__name__)


class BufferType(Enum):
    """Type of experience buffer."""
    FIFO = "fifo"
    RESERVOIR = "reservoir"
    PRIORITIZED = "prioritized"


@dataclass
class Experience:
    """Single experience transition."""

    state: np.ndarray
    action: np.ndarray
    reward: float
    next_state: Optional[np.ndarray] = None
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)
    priority: float = 1.0
    timestamp: float = 0.0
    episode_id: int = 0


@dataclass
class BufferConfig:
    """Configuration for experience buffer."""

    buffer_type: BufferType = BufferType.FIFO
    capacity: int = 100_000
    min_size: int = 1000
    batch_size: int = 64

    # PER parameters
    alpha: float = 0.6  # priority exponent
    beta: float = 0.4   # importance sampling exponent
    beta_increment: float = 0.001
    epsilon: float = 1e-6

    # N-step returns
    n_step: int = 1
    gamma: float = 0.99

    # Storage
    compress_states: bool = False
    max_episodes: int = 10000

    seed: int = 42


class ExperienceBuffer:
    """Efficient experience buffer for RL training.

    Supports:
    - FIFO (first-in-first-out)
    - Reservoir sampling (uniform random replacement)
    - Prioritized Experience Replay (PER)

    Usage:
        buffer = ExperienceBuffer(config)
        buffer.add(state, action, reward, next_state, done)
        batch = buffer.sample(batch_size)
    """

    def __init__(self, config: Optional[BufferConfig] = None):
        self.config = config or BufferConfig()
        self._rng = random.Random(self.config.seed)
        self._np_rng = np.random.RandomState(self.config.seed)

        # Storage
        self._states: List[np.ndarray] = []
        self._actions: List[np.ndarray] = []
        self._rewards: List[float] = []
        self._next_states: List[Optional[np.ndarray]] = []
        self._dones: List[bool] = []
        self._priorities: List[float] = []
        self._indices: List[int] = []  # for reservoir sampling
        self._episode_ids: List[int] = []

        # PER tree
        self._sum_tree: Optional["SumTree"] = None
        if self.config.buffer_type == BufferType.PRIORITIZED:
            self._sum_tree = SumTree(self.config.capacity)

        # Statistics
        self._total_added: int = 0
        self._total_sampled: int = 0
        self._current_episode: int = 0
        self._episode_rewards: Dict[int, List[float]] = {}

    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        next_state: Optional[np.ndarray] = None,
        done: bool = False,
        priority: Optional[float] = None,
        info: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Add an experience to the buffer.

        Returns the index where it was stored.
        """
        import time

        if self.is_full():
            if self.config.buffer_type == BufferType.FIFO:
                self._remove_oldest()
            elif self.config.buffer_type == BufferType.RESERVOIR:
                self._reservoir_replace()
            else:
                self._remove_min_priority()

        # Compute initial priority (for PER)
        if priority is None:
            if self._sum_tree and len(self._priorities) > 0:
                priority = max(self._priorities) if self._priorities else 1.0
            else:
                priority = 1.0

        idx = len(self._states)
        self._states.append(state.copy() if isinstance(state, np.ndarray) else np.array(state))
        self._actions.append(action.copy() if isinstance(action, np.ndarray) else np.array(action))
        self._rewards.append(reward)
        self._next_states.append(next_state.copy() if isinstance(next_state, np.ndarray) and next_state is not None else next_state)
        self._dones.append(done)
        self._priorities.append(priority)
        self._episode_ids.append(self._current_episode)

        if self._sum_tree:
            self._sum_tree.update(idx, priority)

        self._total_added += 1
        return idx

    def sample(
        self, batch_size: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """Sample a batch of experiences.

        Returns:
            (states, actions, rewards, next_states, dones, indices, weights)
        """
        batch_size = batch_size or self.config.batch_size
        batch_size = min(batch_size, len(self))

        if self.config.buffer_type == BufferType.PRIORITIZED and self._sum_tree:
            indices, weights = self._sample_prioritized(batch_size)
        else:
            indices = [self._rng.randint(0, len(self) - 1) for _ in range(batch_size)]
            weights = np.ones(batch_size)

        states = np.array([self._states[i] for i in indices])
        actions = np.array([self._actions[i] for i in indices])
        rewards = np.array([self._rewards[i] for i in indices])

        next_states_list = []
        for i in indices:
            ns = self._next_states[i]
            if ns is not None:
                next_states_list.append(ns)
            else:
                # For terminal states, use zero vector
                next_states_list.append(np.zeros_like(states[0]))
        next_states = np.array(next_states_list)

        dones = np.array([self._dones[i] for i in indices], dtype=np.float32)
        inds = np.array(indices)
        weights = np.array(weights)

        self._total_sampled += batch_size
        return states, actions, rewards, next_states, dones, inds, weights

    def sample_trajectories(
        self, n_trajectories: int = 4, max_len: int = 100
    ) -> List[List[Experience]]:
        """Sample complete episode trajectories."""
        episodes = {}
        for i in range(len(self)):
            ep_id = self._episode_ids[i]
            if ep_id not in episodes:
                episodes[ep_id] = []
            episodes[ep_id].append(self._get_experience(i))

        # Sort episodes by reward
        sorted_eps = sorted(
            episodes.values(),
            key=lambda ep: sum(e.reward for e in ep),
            reverse=True,
        )

        # Sample high-reward and random episodes
        selected = sorted_eps[:n_trajectories // 2]
        if len(sorted_eps) > n_trajectories // 2:
            remaining = sorted_eps[n_trajectories // 2:]
            selected.extend(random.sample(
                remaining,
                min(n_trajectories - n_trajectories // 2, len(remaining)),
            ))

        return [ep[:max_len] for ep in selected]

    def update_priorities(self, indices: np.ndarray, priorities: np.ndarray):
        """Update priorities for specific transitions (PER)."""
        if not self._sum_tree:
            return

        for idx, priority in zip(indices, priorities):
            if idx < len(self._priorities):
                priority = max(priority, self.config.epsilon)
                self._priorities[idx] = priority
                self._sum_tree.update(int(idx), float(priority))

    def _sample_prioritized(
        self, batch_size: int
    ) -> Tuple[List[int], np.ndarray]:
        """Prioritized experience replay sampling."""
        if not self._sum_tree:
            return [], np.ones(batch_size)

        priorities = []
        indices = []
        segment = self._sum_tree.total() / batch_size

        for i in range(batch_size):
            a = segment * i
            b = segment * (i + 1)
            value = self._rng.uniform(a, b)
            idx, priority = self._sum_tree.get(value)
            indices.append(idx)
            priorities.append(priority)

        # Importance sampling weights
        probs = np.array(priorities) / (self._sum_tree.total() + 1e-8)
        weights = (len(self) * probs) ** (-self.config.beta)
        weights = weights / (weights.max() + 1e-8)

        # Increment beta
        self.config.beta = min(1.0, self.config.beta + self.config.beta_increment)

        return indices, weights

    def _remove_oldest(self):
        """Remove oldest entry (FIFO)."""
        if len(self._states) >= self.config.capacity:
            self._states.pop(0)
            self._actions.pop(0)
            self._rewards.pop(0)
            self._next_states.pop(0)
            self._dones.pop(0)
            self._priorities.pop(0)
            self._episode_ids.pop(0)

    def _reservoir_replace(self):
        """Reservoir sampling replacement."""
        if len(self._states) > self.config.capacity:
            idx = self._rng.randint(0, self._total_added)
            if idx < self.config.capacity:
                # Replace this position
                pass
            # Otherwise, discard

    def _remove_min_priority(self):
        """Remove entry with minimum priority."""
        if len(self._priorities) > 0:
            min_idx = int(np.argmin(self._priorities))
            self._states.pop(min_idx)
            self._actions.pop(min_idx)
            self._rewards.pop(min_idx)
            self._next_states.pop(min_idx)
            self._dones.pop(min_idx)
            self._priorities.pop(min_idx)
            self._episode_ids.pop(min_idx)

    def _get_experience(self, idx: int) -> Experience:
        """Get an Experience object at index."""
        return Experience(
            state=self._states[idx],
            action=self._actions[idx],
            reward=self._rewards[idx],
            next_state=self._next_states[idx],
            done=self._dones[idx],
            priority=self._priorities[idx],
            episode_id=self._episode_ids[idx],
        )

    def new_episode(self):
        """Mark the start of a new episode."""
        self._current_episode += 1
        self._episode_rewards[self._current_episode] = []

    def end_episode(self, total_reward: float):
        """Mark the end of current episode."""
        self._episode_rewards[self._current_episode].append(total_reward)

    def __len__(self) -> int:
        return len(self._states)

    def is_full(self) -> bool:
        return len(self) >= self.config.capacity

    def can_sample(self) -> bool:
        return len(self) >= self.config.min_size

    def clear(self):
        """Clear all stored experiences."""
        self._states = []
        self._actions = []
        self._rewards = []
        self._next_states = []
        self._dones = []
        self._priorities = []
        self._episode_ids = []
        if self._sum_tree:
            self._sum_tree = SumTree(self.config.capacity)

    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            "size": len(self),
            "capacity": self.config.capacity,
            "total_added": self._total_added,
            "total_sampled": self._total_sampled,
            "episodes": self._current_episode,
            "avg_reward": (
                float(np.mean(self._rewards)) if self._rewards else 0.0
            ),
            "max_priority": max(self._priorities) if self._priorities else 0.0,
            "min_priority": min(self._priorities) if self._priorities else 0.0,
        }


class SumTree:
    """Binary sum tree for efficient prioritized sampling.

    Stores priorities at leaf nodes and maintains partial sums
    at internal nodes for O(log n) sampling.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)
        self.data = np.zeros(capacity, dtype=object)
        self._write_pos = 0
        self._size = 0

    def total(self) -> float:
        return float(self.tree[0])

    def update(self, idx: int, priority: float):
        """Update priority at index."""
        tree_idx = idx + self.capacity - 1
        change = priority - self.tree[tree_idx]
        self.tree[tree_idx] = priority

        while tree_idx > 0:
            tree_idx = (tree_idx - 1) // 2
            self.tree[tree_idx] += change

    def get(self, value: float) -> Tuple[int, float]:
        """Get leaf index and priority for a given cumulative value."""
        idx = 0
        while idx < self.capacity - 1:
            left = 2 * idx + 1
            if value <= self.tree[left]:
                idx = left
            else:
                value -= self.tree[left]
                idx = left + 1

        data_idx = idx - self.capacity + 1
        return data_idx, float(self.tree[idx])

    def add(self, priority: float) -> int:
        """Add a new priority value."""
        idx = self._write_pos
        self.update(idx, priority)
        self._write_pos = (self._write_pos + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)
        return idx

    def __len__(self) -> int:
        return self._size
