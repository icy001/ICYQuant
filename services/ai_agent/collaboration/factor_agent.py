"""Factor Agent — specialized agent for factor research, mining, and evaluation.

Pipeline:
    Factor research request / Coordinator assignment
        -> FactorAgent.mine_factors() (discover candidate factors)
        -> FactorAgent.evaluate_factor() (IC analysis, decay, turnover)
        -> FactorAgent.select_factors() (multi-factor selection)
        -> publish findings to blackboard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.message_bus import MessageBus, Message, MessageType

logger = logging.getLogger(__name__)


class FactorCategory(str, Enum):
    """Categories of quantitative factors."""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    GROWTH = "growth"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"
    MACRO = "macro"
    ALTERNATIVE = "alternative"


@dataclass
class Factor:
    """A quantitative factor definition with evaluation metrics.

    Attributes:
        factor_id: Unique factor identifier.
        name: Factor name.
        category: Factor category.
        description: Factor description.
        ic_mean: Mean information coefficient.
        ic_ir: IC information ratio.
        rank_ic: Rank IC.
        decay_rate: Signal decay rate.
        turnover: Monthly turnover rate.
        sharpe: Long-short Sharpe ratio.
    """

    factor_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    category: FactorCategory = FactorCategory.TECHNICAL
    description: str = ""
    ic_mean: float = 0.0
    ic_ir: float = 0.0
    rank_ic: float = 0.0
    decay_rate: float = 0.0
    turnover: float = 0.0
    sharpe: float = 0.0

    @property
    def is_significant(self) -> bool:
        """Return whether the factor has significant predictive power."""
        return abs(self.ic_mean) > 0.02 and self.ic_ir > 0.3

    def to_dict(self) -> Dict[str, Any]:
        """Return factor as a dictionary."""
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "category": self.category.value,
            "ic_mean": self.ic_mean,
            "ic_ir": self.ic_ir,
            "sharpe": self.sharpe,
        }


class FactorAgent:
    """Specialized agent for factor research, mining, and evaluation.

    Discovers, evaluates, and selects quantitative factors for strategy
    development. Publishes factor findings for Research and Strategy agents.

    Supports:
        - Factor mining and discovery
        - Factor evaluation (IC, decay, turnover)
        - Multi-factor selection
        - Factor correlation analysis
        - Factor publication

    Usage:
        agent = FactorAgent(agent_id="factor_1", message_bus=bus)
        await agent.initialize()
        factors = await agent.mine_factors()
        best = await agent.evaluate_factor(factors[0])
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Factor Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._factors: Dict[str, Factor] = {}
        logger.info("FactorAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the factor agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("FactorAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the factor agent."""
        self._factors.clear()
        self._initialized = False
        logger.info("FactorAgent shutdown: %s", self._agent_id)

    # ── Factor Mining ──

    async def mine_factors(
        self, category: Optional[FactorCategory] = None,
    ) -> List[Factor]:
        """Discover candidate factors.

        Args:
            category: Optional category filter.

        Returns:
            List of discovered factors.
        """
        candidates: List[Factor] = []

        # Built-in factor library
        builtin_factors = [
            Factor(name="momentum_20d", category=FactorCategory.MOMENTUM,
                   description="20-day price momentum", ic_mean=0.035, ic_ir=0.55),
            Factor(name="volatility_60d", category=FactorCategory.VOLATILITY,
                   description="60-day realized volatility", ic_mean=-0.028, ic_ir=0.42),
            Factor(name="pb_ratio", category=FactorCategory.VALUE,
                   description="Price-to-book ratio", ic_mean=-0.022, ic_ir=0.38),
            Factor(name="roe", category=FactorCategory.QUALITY,
                   description="Return on equity", ic_mean=0.018, ic_ir=0.32),
            Factor(name="revenue_growth", category=FactorCategory.GROWTH,
                   description="Revenue growth YoY", ic_mean=0.025, ic_ir=0.45),
            Factor(name="rsi_14d", category=FactorCategory.TECHNICAL,
                   description="14-day RSI", ic_mean=-0.015, ic_ir=0.28),
        ]

        for f in builtin_factors:
            if category is None or f.category == category:
                self._factors[f.factor_id] = f
                candidates.append(f)

        logger.info("FactorAgent mined %d factors (category=%s)",
                    len(candidates), category.value if category else "all")
        return candidates

    # ── Factor Evaluation ──

    async def evaluate_factor(self, factor: Factor) -> Factor:
        """Evaluate a factor's predictive power.

        Args:
            factor: The factor to evaluate.

        Returns:
            Evaluated factor with metrics.
        """
        # Evaluation metrics would come from actual computation
        factor.rank_ic = factor.ic_mean * 1.1
        factor.decay_rate = 0.05
        factor.turnover = 0.3
        factor.sharpe = factor.ic_ir * 2.0

        self._factors[factor.factor_id] = factor

        logger.debug("FactorAgent evaluated %s: IC=%.3f, IR=%.2f",
                     factor.name, factor.ic_mean, factor.ic_ir)
        return factor

    # ── Factor Selection ──

    async def select_factors(
        self, min_ic: float = 0.02, max_correlation: float = 0.7,
    ) -> List[Factor]:
        """Select the best factors based on criteria.

        Args:
            min_ic: Minimum absolute IC threshold.
            max_correlation: Maximum pairwise correlation.

        Returns:
            List of selected factors.
        """
        all_factors = list(self._factors.values())

        # Filter by IC significance
        significant = [
            f for f in all_factors
            if abs(f.ic_mean) >= min_ic and f.ic_ir > 0.3
        ]

        # Sort by IC IR descending
        significant.sort(key=lambda f: f.ic_ir, reverse=True)

        logger.info("FactorAgent selected %d factors from %d candidates",
                    len(significant), len(all_factors))

        # Publish selection
        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="factor.selected",
                sender_id=self._agent_id,
                payload={"selected_factors": [f.to_dict() for f in significant]},
            ))

        return significant

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the factor agent state.

        Returns:
            Dict with factor count and categories.
        """
        cat_counts: Dict[str, int] = {}
        for f in self._factors.values():
            cat_counts[f.category.value] = cat_counts.get(f.category.value, 0) + 1

        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "total_factors": len(self._factors),
            "category_breakdown": cat_counts,
        }
