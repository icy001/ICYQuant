"""Policy Network — neural network models for RL trading policies.

Implements Actor-Critic architectures with:
- Shared feature extractor
- Actor head (action distribution)
- Critic head (value estimation)
- Support for PPO, SAC, DQN variants
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math

import numpy as np


class NetworkType(Enum):
    """Type of policy network architecture."""
    MLP = "mlp"
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    CNN = "cnn"


class ActivationType(Enum):
    RELU = "relu"
    TANH = "tanh"
    ELU = "elu"
    GELU = "gelu"
    LEAKY_RELU = "leaky_relu"


@dataclass
class PolicyConfig:
    """Configuration for policy network."""

    # Architecture
    network_type: NetworkType = NetworkType.MLP
    hidden_layers: List[int] = field(default_factory=lambda: [256, 256, 128])
    activation: ActivationType = ActivationType.RELU

    # Input/Output
    state_dim: int = 64
    action_dim: int = 3
    use_discrete_actions: bool = False

    # Actor-Critic specific
    shared_layers: int = 2  # Number of shared layers before branching
    actor_hidden: List[int] = field(default_factory=lambda: [128, 64])
    critic_hidden: List[int] = field(default_factory=lambda: [128, 64])

    # Regularization
    dropout_rate: float = 0.1
    layer_norm: bool = True
    weight_decay: float = 0.0

    # Distribution
    use_tanh_squash: bool = True  # For SAC-style bounded actions
    log_std_min: float = -5.0
    log_std_max: float = 2.0

    # LSTM specific
    lstm_hidden_size: int = 128
    lstm_num_layers: int = 2

    # Initialization
    orthogonal_init: bool = True
    gain: float = 1.0


class PolicyNetwork:
    """Neural network policy for RL trading.

    Supports both discrete and continuous action spaces with
    Actor-Critic architecture.

    This is a pure numpy implementation that mimics PyTorch-style
    network behavior for environment compatibility.

    Usage:
        net = PolicyNetwork(config)
        action, log_prob, value = net.forward(state)
        loss = net.compute_loss(batch)
    """

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()
        self._params: Dict[str, np.ndarray] = {}
        self._init_parameters()
        self._training: bool = True

    def _init_parameters(self):
        """Initialize network parameters."""
        layer_dims = (
            [self.config.state_dim]
            + self.config.hidden_layers
            + [self.config.action_dim]
        )

        rng = np.random.RandomState(42)

        for i in range(len(layer_dims) - 1):
            fan_in = layer_dims[i]
            fan_out = layer_dims[i + 1]

            if self.config.orthogonal_init:
                # Orthogonal initialization
                # When fan_out < fan_in, QR reduces to (fan_out, fan_out).
                # Fix: transpose to (fan_in, fan_out), QR, transpose back to (fan_out, fan_in).
                if fan_out >= fan_in:
                    w = rng.randn(fan_out, fan_in)
                    w, _ = np.linalg.qr(w)
                else:
                    w = rng.randn(fan_in, fan_out)
                    q, _ = np.linalg.qr(w)
                    w = q.T  # (fan_out, fan_in)
                w *= math.sqrt(2.0 / fan_in) * self.config.gain
            else:
                # Xavier uniform
                bound = math.sqrt(6.0 / (fan_in + fan_out))
                w = rng.uniform(-bound, bound, (fan_out, fan_in))

            b = np.zeros(fan_out)

            self._params[f"w_{i}"] = w
            self._params[f"b_{i}"] = b

        # Actor-specific layers (policy head)
        actor_in = self.config.hidden_layers[-1] if self.config.hidden_layers else self.config.state_dim
        for i, hidden in enumerate(self.config.actor_hidden):
            w_a = rng.randn(hidden, actor_in) * math.sqrt(2.0 / actor_in)
            b_a = np.zeros(hidden)
            self._params[f"actor_w_{i}"] = w_a
            self._params[f"actor_b_{i}"] = b_a
            actor_in = hidden

        # Actor output: mean + log_std for continuous, logits for discrete
        if self.config.use_discrete_actions:
            w_a_out = rng.randn(self.config.action_dim, actor_in) * 0.01
            b_a_out = np.zeros(self.config.action_dim)
        else:
            w_a_out = rng.randn(self.config.action_dim, actor_in) * 0.01
            b_a_out = np.zeros(self.config.action_dim)
        self._params["actor_w_out"] = w_a_out
        self._params["actor_b_out"] = b_a_out

        # Critic layers (value head)
        critic_in = self.config.hidden_layers[-1] if self.config.hidden_layers else self.config.state_dim
        for i, hidden in enumerate(self.config.critic_hidden):
            w_c = rng.randn(hidden, critic_in) * math.sqrt(2.0 / critic_in)
            b_c = np.zeros(hidden)
            self._params[f"critic_w_{i}"] = w_c
            self._params[f"critic_b_{i}"] = b_c
            critic_in = hidden

        w_c_out = rng.randn(1, critic_in) * 0.01
        b_c_out = np.zeros(1)
        self._params["critic_w_out"] = w_c_out
        self._params["critic_b_out"] = b_c_out

        # Log std for continuous actions
        if not self.config.use_discrete_actions:
            log_std = np.zeros(self.config.action_dim) - 0.5
            self._params["log_std"] = log_std

    def forward(
        self, state: np.ndarray, deterministic: bool = False
    ) -> Tuple[np.ndarray, float, float]:
        """Forward pass: state → action, log_prob, value.

        Args:
            state: State vector [state_dim]
            deterministic: If True, use mean action (no sampling)

        Returns:
            action: Action vector
            log_prob: Log probability of action
            value: State value estimate
        """
        # Shared feature extraction
        x = state.reshape(-1)
        for i in range(len(self.config.hidden_layers)):
            x = self._linear(x, f"w_{i}", f"b_{i}")
            x = self._activation(x)
            if self.config.layer_norm and i < len(self.config.hidden_layers) - 1:
                x = self._layer_norm(x)

        shared_features = x.copy()

        # Actor head
        a = shared_features
        for i in range(len(self.config.actor_hidden)):
            a = self._linear(a, f"actor_w_{i}", f"actor_b_{i}")
            a = self._activation(a)

        action_mean = self._linear(a, "actor_w_out", "actor_b_out")

        if self.config.use_discrete_actions:
            # Softmax over actions
            action_mean = self._softmax(action_mean)
            if deterministic:
                action = np.eye(self.config.action_dim)[np.argmax(action_mean)]
            else:
                action = self._sample_categorical(action_mean)
            log_prob = float(np.log(np.dot(action, action_mean) + 1e-8))
        else:
            # Continuous: Gaussian policy
            log_std = np.clip(
                self._params["log_std"],
                self.config.log_std_min,
                self.config.log_std_max,
            )
            std = np.exp(log_std)

            if deterministic:
                action = action_mean
            else:
                action = action_mean + std * np.random.randn(*action_mean.shape)

            if self.config.use_tanh_squash:
                action = np.tanh(action)

            # Log probability
            if self.config.use_tanh_squash:
                log_prob = self._gaussian_log_prob(
                    np.arctanh(np.clip(action, -0.999, 0.999)),
                    action_mean, log_std,
                )
            else:
                log_prob = self._gaussian_log_prob(action, action_mean, log_std)

        # Critic head
        v = shared_features
        for i in range(len(self.config.critic_hidden)):
            v = self._linear(v, f"critic_w_{i}", f"critic_b_{i}")
            v = self._activation(v)
        value = float(self._linear(v, "critic_w_out", "critic_b_out")[0])

        return action, log_prob, value

    def get_value(self, state: np.ndarray) -> float:
        """Get value estimate for state."""
        _, _, value = self.forward(state, deterministic=True)
        return value

    def act(
        self, state: np.ndarray, deterministic: bool = False
    ) -> Tuple[np.ndarray, float]:
        """Get action from policy."""
        action, log_prob, _ = self.forward(state, deterministic=deterministic)
        return action, log_prob

    def get_parameters(self) -> Dict[str, np.ndarray]:
        """Get all network parameters."""
        return {k: v.copy() for k, v in self._params.items()}

    def set_parameters(self, params: Dict[str, np.ndarray]):
        """Set network parameters."""
        self._params = {k: v.copy() for k, v in params.items()}

    def _linear(
        self, x: np.ndarray, w_key: str, b_key: str
    ) -> np.ndarray:
        """Linear layer: y = Wx + b."""
        return self._params[w_key] @ x + self._params[b_key]

    def _activation(self, x: np.ndarray) -> np.ndarray:
        """Apply activation function."""
        act = self.config.activation
        if act == ActivationType.RELU:
            return np.maximum(0, x)
        elif act == ActivationType.TANH:
            return np.tanh(x)
        elif act == ActivationType.ELU:
            return np.where(x > 0, x, np.exp(x) - 1)
        elif act == ActivationType.GELU:
            return 0.5 * x * (1 + np.tanh(
                math.sqrt(2 / math.pi) * (x + 0.044715 * x ** 3)
            ))
        elif act == ActivationType.LEAKY_RELU:
            return np.where(x > 0, x, 0.01 * x)
        return x

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax with numerical stability."""
        x = x - np.max(x)
        exp_x = np.exp(x)
        return exp_x / np.sum(exp_x)

    def _sample_categorical(self, probs: np.ndarray) -> np.ndarray:
        """Sample from categorical distribution."""
        cumsum = np.cumsum(probs)
        r = np.random.random()
        idx = np.searchsorted(cumsum, r)
        action = np.zeros_like(probs)
        action[idx] = 1.0
        return action

    def _gaussian_log_prob(
        self, action: np.ndarray, mean: np.ndarray, log_std: np.ndarray
    ) -> float:
        """Compute log probability under Gaussian."""
        std = np.exp(log_std)
        var = std ** 2
        log_prob = -0.5 * (
            np.sum(((action - mean) ** 2) / (var + 1e-8))
            + np.sum(log_std) * 2
            + self.config.action_dim * math.log(2 * math.pi)
        )
        return float(log_prob)

    def _layer_norm(self, x: np.ndarray) -> np.ndarray:
        """Simple layer normalization."""
        mean = np.mean(x)
        std = np.std(x)
        if std > 0:
            return (x - mean) / (std + 1e-8)
        return x

    def train(self):
        """Set network to training mode."""
        self._training = True

    def eval(self):
        """Set network to evaluation mode."""
        self._training = False

    def save(self, path: str):
        """Save parameters to file."""
        import pickle
        with open(path, "wb") as f:
            pickle.dump(self._params, f)

    def load(self, path: str):
        """Load parameters from file."""
        import pickle
        with open(path, "rb") as f:
            self._params = pickle.load(f)


class ActorCriticNetwork(PolicyNetwork):
    """Alias for PolicyNetwork with Actor-Critic architecture.

    Provides the same interface but with explicit naming
    for Actor-Critic algorithms (A2C, PPO).
    """

    def actor_forward(self, state: np.ndarray) -> np.ndarray:
        """Actor-only forward pass."""
        action, _, _ = self.forward(state)
        return action

    def critic_forward(self, state: np.ndarray) -> float:
        """Critic-only forward pass."""
        _, _, value = self.forward(state)
        return value
