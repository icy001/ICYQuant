"""Reinforcement Learning Agent - RL-based trading policy learning."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import math
import random


class ActionType(Enum):
    """Available trading actions."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    EXIT = "EXIT"


class PolicyType(Enum):
    """Type of RL policy."""
    EPSILON_GREEDY = "EPSILON_GREEDY"
    SOFTMAX = "SOFTMAX"
    UCB = "UCB"
    THOMPSON = "THOMPSON"


class LearningPhase(Enum):
    """Current learning phase."""
    EXPLORATION = "EXPLORATION"
    EXPLOITATION = "EXPLOITATION"
    BALANCED = "BALANCED"


@dataclass
class MarketState:
    """Representation of a market state for RL."""
    price: float
    trend: float
    volatility: float
    volume: float
    momentum: float
    regime: str
    features: Dict[str, float] = field(default_factory=dict)

    def to_vector(self) -> List[float]:
        return [
            self.price, self.trend, self.volatility,
            self.volume, self.momentum,
        ]


@dataclass
class RewardSignal:
    """Reward signal for RL training."""
    total_return: float
    risk_adjusted_return: float
    drawdown_penalty: float
    consistency_bonus: float
    final_reward: float


@dataclass
class QTable:
    """Simple Q-table for value-based RL."""
    states: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def get(self, state_key: str, action: str) -> float:
        return self.states.get(state_key, {}).get(action, 0.0)

    def set(self, state_key: str, action: str, value: float):
        if state_key not in self.states:
            self.states[state_key] = {}
        self.states[state_key][action] = value

    def best_action(self, state_key: str) -> Optional[str]:
        actions = self.states.get(state_key, {})
        if not actions:
            return None
        return max(actions, key=actions.get)


@dataclass
class TrainingEpisode:
    """A single training episode."""
    episode_id: int
    states_visited: List[str]
    actions_taken: List[str]
    rewards_received: List[float]
    total_reward: float
    learning_rate: float
    epsilon: float
    lessons: List[str] = field(default_factory=list)


class ReinforcementLearningAgent:
    """Reinforcement Learning Agent.

    Learns optimal trading policies through:
    - Market state observation
    - Action selection (Buy/Sell/Hold/Adjust)
    - Reward computation (Return/Risk-adjusted return)
    - Policy improvement via Q-learning

    State: Market State (price, trend, volatility, volume, momentum)
    Action: Buy, Sell, Hold, Increase, Decrease, Exit
    Reward: Return, Risk-adjusted Return
    """

    def __init__(self,
                 learning_rate: float = 0.01,
                 discount_factor: float = 0.95,
                 epsilon: float = 0.1,
                 epsilon_decay: float = 0.995,
                 min_epsilon: float = 0.01):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.min_epsilon = min_epsilon
        self.q_table = QTable()
        self.training_history: List[TrainingEpisode] = []
        self._episode_counter = 0
        self.policy_type = PolicyType.EPSILON_GREEDY
        self.learning_phase = LearningPhase.EXPLORATION

    def learn(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Learn from a market state - main entry point.

        Args:
            state_data: Market state data dict.

        Returns:
            Dict with policy decision.
        """
        state = self._build_state(state_data)
        state_key = self._state_to_key(state)
        action = self.select_action(state_key)

        # Compute reward based on outcome
        reward = self._compute_reward(state_data)

        # Update Q-values
        self._update_q(state_key, action.value, reward, None)

        # Decay exploration
        self._decay_epsilon()

        return {
            "state_key": state_key,
            "action": action.value,
            "policy_type": self.policy_type.value,
            "learning_phase": self.learning_phase.value,
            "epsilon": self.epsilon,
            "q_values": self.q_table.states.get(state_key, {}),
            "policy": self._get_policy_summary(state_key),
        }

    def select_action(self, state_key: str) -> ActionType:
        """Select action using epsilon-greedy policy.

        Args:
            state_key: State representation key.

        Returns:
            Selected ActionType.
        """
        if random.random() < self.epsilon:
            # Exploration: random action
            return random.choice(list(ActionType))

        # Exploitation: best known action
        best = self.q_table.best_action(state_key)
        if best is None:
            return random.choice(list(ActionType))
        return ActionType(best)

    def train_episode(self, state_sequence: List[Dict[str, Any]],
                      outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train on a full episode of states and outcomes.

        Args:
            state_sequence: List of market state dicts.
            outcomes: List of outcome dicts corresponding to actions taken.

        Returns:
            Dict with episode training results.
        """
        if len(state_sequence) != len(outcomes):
            return {"error": "State sequence and outcomes must have same length"}

        episode = TrainingEpisode(
            episode_id=self._episode_counter,
            states_visited=[],
            actions_taken=[],
            rewards_received=[],
            total_reward=0.0,
            learning_rate=self.learning_rate,
            epsilon=self.epsilon,
        )

        for state_data, outcome in zip(state_sequence, outcomes):
            state = self._build_state(state_data)
            state_key = self._state_to_key(state)
            action = self.select_action(state_key)

            reward = outcome.get("reward", 0.0)

            episode.states_visited.append(state_key)
            episode.actions_taken.append(action.value)
            episode.rewards_received.append(reward)
            episode.total_reward += reward

            # Update Q-values with temporal difference
            next_state_key = None
            self._update_q(state_key, action.value, reward, next_state_key)

        # Generate lessons from episode
        episode.lessons = self._extract_episode_lessons(episode)

        self.training_history.append(episode)
        self._episode_counter += 1
        self._decay_epsilon()

        # Update learning phase
        self._update_learning_phase()

        return {
            "episode_id": episode.episode_id,
            "total_reward": episode.total_reward,
            "actions_taken": episode.actions_taken,
            "avg_reward": episode.total_reward / max(len(episode.rewards_received), 1),
            "lessons": episode.lessons,
            "epsilon": self.epsilon,
            "learning_phase": self.learning_phase.value,
        }

    def get_policy(self) -> Dict[str, Any]:
        """Get the current learned policy.

        Returns:
            Dict with policy summary.
        """
        if not self.q_table.states:
            return {"states": 0, "best_actions": {}}

        best_actions = {}
        for state_key, actions in self.q_table.states.items():
            if actions:
                best = max(actions, key=actions.get)
                best_actions[state_key] = {
                    "action": best,
                    "value": actions[best],
                }

        return {
            "states_learned": len(self.q_table.states),
            "best_actions": best_actions,
            "policy_type": self.policy_type.value,
            "learning_phase": self.learning_phase.value,
            "total_episodes": len(self.training_history),
        }

    def evaluate(self, test_states: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluate the learned policy on test states.

        Args:
            test_states: List of test market state dicts.

        Returns:
            Dict with evaluation results.
        """
        actions = []
        q_values = []

        for state_data in test_states:
            state = self._build_state(state_data)
            state_key = self._state_to_key(state)
            action = self.select_action(state_key)
            actions.append(action.value)
            state_q = self.q_table.states.get(state_key, {})
            q_values.append(state_q)

        action_counts = {}
        for a in actions:
            action_counts[a] = action_counts.get(a, 0) + 1

        return {
            "total_states": len(test_states),
            "actions": actions,
            "action_distribution": action_counts,
            "avg_q_value": sum(sum(qv.values()) for qv in q_values) / max(len(q_values), 1),
        }

    # ---- Internal helpers ----

    def _build_state(self, data: Dict[str, Any]) -> MarketState:
        return MarketState(
            price=data.get("price", 100.0),
            trend=data.get("trend", 0.0),
            volatility=data.get("volatility", 0.15),
            volume=data.get("volume", 1000000.0),
            momentum=data.get("momentum", 0.0),
            regime=data.get("regime", "normal"),
            features=data.get("features", {}),
        )

    def _state_to_key(self, state: MarketState) -> str:
        """Convert market state to a discrete key."""
        trend_bin = self._discretize(state.trend, [-0.02, -0.005, 0.005, 0.02])
        vol_bin = self._discretize(state.volatility, [0.10, 0.20, 0.35])
        mom_bin = self._discretize(state.momentum, [-0.02, -0.005, 0.005, 0.02])
        return f"T{trend_bin}_V{vol_bin}_M{mom_bin}"

    def _discretize(self, value: float, bins: List[float]) -> int:
        """Discretize a continuous value into bins."""
        for i, threshold in enumerate(bins):
            if value <= threshold:
                return i
        return len(bins)

    def _compute_reward(self, data: Dict[str, Any]) -> float:
        """Compute reward signal from outcome data."""
        raw_return = data.get("return", 0.0)
        volatility = data.get("volatility", 0.15)
        drawdown = data.get("drawdown", 0.0)

        risk_adjusted = raw_return / max(volatility, 0.001)
        drawdown_penalty = -abs(drawdown) * 2.0

        # Consistency bonus for consecutive positive returns
        consistency = data.get("consecutive_positive", 0) * 0.01

        return risk_adjusted + drawdown_penalty + consistency

    def _update_q(self, state_key: str, action: str, reward: float,
                  next_state_key: Optional[str]):
        """Update Q-value using Q-learning update rule."""
        current_q = self.q_table.get(state_key, action)

        if next_state_key:
            next_best = self.q_table.best_action(next_state_key)
            max_next_q = self.q_table.get(next_state_key, next_best) if next_best else 0.0
        else:
            max_next_q = 0.0

        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        self.q_table.set(state_key, action, new_q)

    def _decay_epsilon(self):
        self.epsilon = max(self.epsilon * self.epsilon_decay, self.min_epsilon)

    def _update_learning_phase(self):
        if self.epsilon > 0.2:
            self.learning_phase = LearningPhase.EXPLORATION
        elif self.epsilon > 0.05:
            self.learning_phase = LearningPhase.BALANCED
        else:
            self.learning_phase = LearningPhase.EXPLOITATION

    def _get_policy_summary(self, state_key: str) -> Dict[str, Any]:
        actions = self.q_table.states.get(state_key, {})
        if not actions:
            return {"best_action": None, "confidence": 0.0}

        best = max(actions, key=actions.get)
        best_val = actions[best]
        avg_val = sum(actions.values()) / len(actions)
        confidence = 1.0 / (1.0 + math.exp(-(best_val - avg_val)))

        return {
            "best_action": best,
            "best_q_value": best_val,
            "confidence": confidence,
        }

    def _extract_episode_lessons(self, episode: TrainingEpisode) -> List[str]:
        lessons = []
        if episode.total_reward > 1.0:
            lessons.append("Strong positive episode - reinforce current policy")
        elif episode.total_reward < -1.0:
            lessons.append("Negative episode - review action selection strategy")

        unique_actions = set(episode.actions_taken)
        if len(unique_actions) == 1 and ActionType.HOLD.value in unique_actions:
            lessons.append("Excessive holding - consider more active strategy")
        if ActionType.BUY.value in unique_actions and episode.total_reward < 0:
            lessons.append("Buy actions during negative episode - review entry timing")

        return lessons
