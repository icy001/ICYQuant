"""Action Space — defines what actions the RL agent can take.

Supports both discrete and continuous action spaces for trading:
- Discrete: BUY/SELL/HOLD per asset
- Continuous: target portfolio weights
- Hierarchical: asset selection → position sizing
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
from enum import Enum
import math

import numpy as np


class ActionType(Enum):
    """Type of action space."""
    DISCRETE = "discrete"
    CONTINUOUS = "continuous"
    HIERARCHICAL = "hierarchical"
    MULTI_DISCRETE = "multi_discrete"


@dataclass
class ActionConfig:
    """Configuration for action space."""

    action_type: ActionType = ActionType.CONTINUOUS

    # Discrete actions
    discrete_actions: List[str] = field(default_factory=lambda: [
        "BUY", "SELL", "HOLD", "INCREASE", "REDUCE", "CLOSE",
    ])

    # Continuous actions
    continuous_bounds: Tuple[float, float] = (-1.0, 1.0)
    num_continuous_dims: int = 1

    # For multi-asset
    symbols: List[str] = field(default_factory=list)
    max_position_pct: float = 0.25

    # Constraints
    enforce_sum_to_one: bool = False
    enforce_no_short: bool = False
    min_trade_size: float = 0.01


class ActionSpace:
    """Base class for action spaces."""

    def __init__(self, config: Optional[ActionConfig] = None):
        self.config = config or ActionConfig()

    @property
    def dim(self) -> int:
        """Dimension of action space."""
        raise NotImplementedError

    def sample(self) -> Any:
        """Sample a random action."""
        raise NotImplementedError

    def contains(self, action: Any) -> bool:
        """Check if action is valid."""
        raise NotImplementedError

    def to_dict(self, action: Any) -> Dict[str, Any]:
        """Convert action to human-readable dict."""
        raise NotImplementedError


class DiscreteActionSpace(ActionSpace):
    """Discrete action space: pick one of N actions per asset."""

    def __init__(self, config: Optional[ActionConfig] = None):
        super().__init__(config)
        self._actions = self.config.discrete_actions
        self._n_actions = len(self._actions)

    @property
    def dim(self) -> int:
        return self._n_actions * len(self.config.symbols) if self.config.symbols else self._n_actions

    def sample(self) -> Dict[str, int]:
        """Sample random discrete actions."""
        symbols = self.config.symbols or ["DEFAULT"]
        return {s: np.random.randint(0, self._n_actions) for s in symbols}

    def contains(self, action: Dict[str, int]) -> bool:
        for s, a in action.items():
            if s not in (self.config.symbols or ["DEFAULT"]):
                return False
            if not (0 <= a < self._n_actions):
                return False
        return True

    def to_dict(self, action: Dict[str, int]) -> Dict[str, Any]:
        return {
            s: self._actions[a]
            for s, a in action.items()
        }

    def action_to_weight(
        self, action: Dict[str, int]
    ) -> Dict[str, float]:
        """Convert discrete action to portfolio weight delta."""
        weights = {}
        for s, a in action.items():
            action_name = self._actions[a]
            if action_name == "BUY":
                weights[s] = self.config.max_position_pct
            elif action_name == "SELL":
                weights[s] = -self.config.max_position_pct
            elif action_name == "INCREASE":
                weights[s] = self.config.max_position_pct * 0.5
            elif action_name == "REDUCE":
                weights[s] = -self.config.max_position_pct * 0.5
            elif action_name == "CLOSE":
                weights[s] = -1.0  # close position
            else:  # HOLD
                weights[s] = 0.0
        return weights

    @property
    def n_actions(self) -> int:
        return self._n_actions


class ContinuousActionSpace(ActionSpace):
    """Continuous action space: output portfolio weights directly."""

    def __init__(self, config: Optional[ActionConfig] = None):
        super().__init__(config)
        self._low, self._high = self.config.continuous_bounds
        self._n_symbols = len(self.config.symbols) if self.config.symbols else 1

    @property
    def dim(self) -> int:
        return self._n_symbols

    def sample(self) -> np.ndarray:
        """Sample random continuous actions."""
        return np.random.uniform(self._low, self._high, self._n_symbols)

    def contains(self, action: np.ndarray) -> bool:
        if len(action) != self._n_symbols:
            return False
        return bool(np.all(action >= self._low) and np.all(action <= self._high))

    def to_dict(self, action: np.ndarray) -> Dict[str, Any]:
        symbols = self.config.symbols or [f"ASSET_{i}" for i in range(len(action))]
        return {s: float(w) for s, w in zip(symbols, action)}

    def action_to_weights(
        self, action: np.ndarray, current_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """Convert continuous action to portfolio weights.

        Maps [-1, 1] to position weight deltas, then clips to constraints.
        """
        symbols = self.config.symbols or [f"ASSET_{i}" for i in range(len(action))]
        weights = {}
        for s, a in zip(symbols, action):
            weight = a * self.config.max_position_pct
            if self.config.enforce_no_short:
                weight = max(0.0, weight)
            weights[s] = max(
                -self.config.max_position_pct,
                min(self.config.max_position_pct, weight),
            )
        return weights

    def normalize_weights(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Normalize weights to sum to 1 (if enforce_sum_to_one)."""
        if not self.config.enforce_sum_to_one:
            return weights

        total = sum(max(0, w) for w in weights.values())
        if total > 0:
            return {s: max(0, w) / total for s, w in weights.items()}
        return {s: 1.0 / len(weights) for s in weights}
