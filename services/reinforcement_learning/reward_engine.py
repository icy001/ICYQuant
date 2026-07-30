"""Reward Engine — multi-objective reward shaping for RL trading.

Designs composite rewards that balance profit, risk, and trading efficiency.
Avoids simple "profit-only" rewards that lead to over-trading or excessive risk.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math

import numpy as np


class RewardType(Enum):
    """Types of reward components."""
    PROFIT = "profit"
    SHARPE = "sharpe"
    DRAWDOWN = "drawdown"
    RISK_ADJUSTED = "risk_adjusted"
    TURNOVER = "turnover"
    REGIME = "regime"
    CONSISTENCY = "consistency"


@dataclass
class RewardConfig:
    """Configuration for the reward engine."""

    # Component weights
    profit_weight: float = 1.0
    sharpe_weight: float = 0.5
    drawdown_weight: float = -2.0  # negative = penalty
    risk_adjusted_weight: float = 0.3
    turnover_penalty: float = -0.1
    regime_weight: float = 0.2
    consistency_weight: float = 0.1

    # Risk-free rate for Sharpe
    risk_free_rate: float = 0.02

    # Drawdown thresholds
    max_tolerated_drawdown: float = 0.15

    # Normalization
    normalize_rewards: bool = True
    reward_clip: Optional[float] = 10.0

    # Hindsight (for HER-like approaches)
    use_hindsight: bool = False

    enabled_components: List[RewardType] = field(default_factory=lambda: [
        RewardType.PROFIT,
        RewardType.SHARPE,
        RewardType.DRAWDOWN,
        RewardType.RISK_ADJUSTED,
        RewardType.TURNOVER,
    ])


@dataclass
class RewardComponents:
    """Breakdown of reward into components."""

    profit: float = 0.0
    sharpe: float = 0.0
    drawdown: float = 0.0
    risk_adjusted: float = 0.0
    turnover: float = 0.0
    regime: float = 0.0
    consistency: float = 0.0

    def total(self) -> float:
        return (
            self.profit + self.sharpe + self.drawdown
            + self.risk_adjusted + self.turnover
            + self.regime + self.consistency
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "profit": self.profit,
            "sharpe": self.sharpe,
            "drawdown": self.drawdown,
            "risk_adjusted": self.risk_adjusted,
            "turnover": self.turnover,
            "regime": self.regime,
            "consistency": self.consistency,
            "total": self.total(),
        }


class RewardEngine:
    """Multi-objective reward computation engine.

    Computes composite rewards from multiple components:
    - Profit: raw PnL
    - Sharpe: risk-adjusted return
    - Drawdown: penalty for losses
    - Risk-adjusted: Sortino/Calmar-like
    - Turnover: penalty for excessive trading
    - Regime: reward for regime-appropriate actions
    - Consistency: reward for stable returns

    Usage:
        engine = RewardEngine(config)
        reward = engine.compute(portfolio_return, drawdown, turnover, ...)
        components = engine.get_components()
    """

    def __init__(self, config: Optional[RewardConfig] = None):
        self.config = config or RewardConfig()
        self._return_history: List[float] = []
        self._component_history: List[RewardComponents] = []
        self._episode_rewards: List[float] = []

    def compute(
        self,
        portfolio_return: float,
        current_drawdown: float,
        turnover: float,
        volatility: float = 0.2,
        market_regime: str = "neutral",
        action_entropy: float = 0.0,
    ) -> float:
        """Compute composite reward.

        Args:
            portfolio_return: Period portfolio return
            current_drawdown: Current drawdown from peak
            turnover: Portfolio turnover ratio
            volatility: Current volatility
            market_regime: bull/bear/neutral/crisis
            action_entropy: Entropy of action distribution
        """
        components = RewardComponents()
        enabled = set(self.config.enabled_components)

        # 1. Profit component
        if RewardType.PROFIT in enabled:
            components.profit = (
                self.config.profit_weight * portfolio_return
            )

        # 2. Sharpe component (rolling)
        if RewardType.SHARPE in enabled:
            self._return_history.append(portfolio_return)
            components.sharpe = (
                self.config.sharpe_weight
                * self._compute_rolling_sharpe()
            )

        # 3. Drawdown penalty
        if RewardType.DRAWDOWN in enabled:
            excess_dd = max(0, current_drawdown - self.config.max_tolerated_drawdown)
            components.drawdown = (
                self.config.drawdown_weight
                * excess_dd
                * (1 + current_drawdown)
            )

        # 4. Risk-adjusted return (Sortino-like)
        if RewardType.RISK_ADJUSTED in enabled:
            downside_vol = self._compute_downside_volatility()
            sortino = (
                (portfolio_return - self.config.risk_free_rate / 252) / downside_vol
                if downside_vol > 0 else 0.0
            )
            components.risk_adjusted = (
                self.config.risk_adjusted_weight * sortino
            )

        # 5. Turnover penalty
        if RewardType.TURNOVER in enabled:
            components.turnover = (
                self.config.turnover_penalty * turnover
            )

        # 6. Regime reward
        if RewardType.REGIME in enabled:
            components.regime = (
                self.config.regime_weight
                * self._compute_regime_reward(portfolio_return, market_regime)
            )

        # 7. Consistency bonus
        if RewardType.CONSISTENCY in enabled:
            components.consistency = (
                self.config.consistency_weight
                * self._compute_consistency()
            )

        reward = components.total()

        # Clip reward
        if self.config.reward_clip is not None:
            reward = max(-self.config.reward_clip, min(self.config.reward_clip, reward))

        self._component_history.append(components)
        self._episode_rewards.append(reward)

        return reward

    def compute_episode_reward(self) -> float:
        """Compute total episode reward (discounted sum)."""
        if not self._episode_rewards:
            return 0.0
        # Simple sum (no discount for now, can add gamma)
        return sum(self._episode_rewards)

    def get_components(self) -> Optional[RewardComponents]:
        """Get latest reward component breakdown."""
        return self._component_history[-1] if self._component_history else None

    def get_component_history(self) -> List[RewardComponents]:
        """Get full component history."""
        return self._component_history.copy()

    def get_episode_stats(self) -> Dict[str, float]:
        """Get episode-level reward statistics."""
        if not self._episode_rewards:
            return {}
        arr = np.array(self._episode_rewards)
        return {
            "mean_reward": float(np.mean(arr)),
            "std_reward": float(np.std(arr)),
            "min_reward": float(np.min(arr)),
            "max_reward": float(np.max(arr)),
            "total_reward": float(np.sum(arr)),
            "positive_ratio": float(np.mean(arr > 0)),
        }

    def _compute_rolling_sharpe(self) -> float:
        """Compute rolling Sharpe ratio."""
        if len(self._return_history) < 2:
            return 0.0
        arr = np.array(self._return_history[-252:])
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            return 0.0
        return (mean - self.config.risk_free_rate / 252) / std * math.sqrt(252)

    def _compute_downside_volatility(self) -> float:
        """Compute downside deviation."""
        if len(self._return_history) < 2:
            return 0.01
        rets = np.array(self._return_history)
        downside = rets[rets < 0]
        if len(downside) == 0:
            return 0.01
        return float(np.std(downside))

    def _compute_regime_reward(
        self, portfolio_return: float, market_regime: str
    ) -> float:
        """Compute reward based on market regime appropriateness."""
        if market_regime == "bull":
            return max(0, portfolio_return)  # reward positive in bull
        elif market_regime == "bear":
            return max(0, -portfolio_return)  # reward avoiding losses in bear
        elif market_regime == "crisis":
            return -abs(portfolio_return)  # penalize any exposure in crisis
        else:
            return portfolio_return  # neutral

    def _compute_consistency(self) -> float:
        """Compute consistency bonus (penalize high variance)."""
        if len(self._return_history) < 5:
            return 0.0
        recent = self._return_history[-20:]
        if len(recent) < 2:
            return 0.0
        # Reward low variance of returns
        std = float(np.std(recent))
        return -std * 5  # penalize volatility

    def reset(self):
        """Reset reward engine state."""
        self._return_history = []
        self._component_history = []
        self._episode_rewards = []
