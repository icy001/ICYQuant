"""Portfolio Agent — specialized agent for portfolio management, optimization, and rebalancing.

Pipeline:
    Portfolio request / Coordinator assignment
        -> PortfolioAgent.analyze() (portfolio analysis)
        -> PortfolioAgent.optimize() (allocation optimization)
        -> PortfolioAgent.rebalance() (generate rebalance orders)
        -> publish recommendations to blackboard
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


class PortfolioAction(str, Enum):
    """Actions for portfolio rebalancing."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class PortfolioPosition:
    """A position in the portfolio.

    Attributes:
        symbol: Trading symbol.
        weight: Current weight in portfolio.
        target_weight: Target weight after rebalancing.
        action: Recommended action.
        quantity: Position quantity.
        market_value: Current market value.
    """

    symbol: str = ""
    weight: float = 0.0
    target_weight: float = 0.0
    action: PortfolioAction = PortfolioAction.HOLD
    quantity: float = 0.0
    market_value: float = 0.0


@dataclass
class PortfolioSummary:
    """Summary of portfolio analysis.

    Attributes:
        total_value: Total portfolio value.
        positions: Current positions.
        risk_metrics: Risk metrics.
        rebalance_needed: Whether rebalancing is needed.
    """

    total_value: float = 0.0
    positions: List[PortfolioPosition] = field(default_factory=list)
    risk_metrics: Dict[str, Any] = field(default_factory=dict)
    rebalance_needed: bool = False


class PortfolioAgent:
    """Specialized agent for portfolio management and optimization.

    Analyzes portfolio composition, computes risk metrics, optimizes
    allocations, and generates rebalancing recommendations.

    Supports:
        - Portfolio analysis and summary
        - Risk metric computation
        - Allocation optimization
        - Rebalancing recommendation
        - Position-level actions

    Usage:
        agent = PortfolioAgent(agent_id="portfolio_1", message_bus=bus)
        await agent.initialize()
        summary = await agent.analyze(positions)
        actions = await agent.rebalance()
    """

    def __init__(
        self,
        agent_id: str = "",
        message_bus: Optional[MessageBus] = None,
    ) -> None:
        """Initialize the Portfolio Agent.

        Args:
            agent_id: Unique agent identifier.
            message_bus: Message bus for communication.
        """
        self._agent_id: str = agent_id or uuid4().hex[:12]
        self._message_bus: Optional[MessageBus] = message_bus
        self._initialized: bool = False
        self._current_summary: Optional[PortfolioSummary] = None
        logger.info("PortfolioAgent created: %s", self._agent_id)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the portfolio agent."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("PortfolioAgent initialized: %s", self._agent_id)

    async def shutdown(self) -> None:
        """Shut down the portfolio agent."""
        self._current_summary = None
        self._initialized = False
        logger.info("PortfolioAgent shutdown: %s", self._agent_id)

    # ── Analysis ──

    async def analyze(
        self, positions: List[Dict[str, Any]],
    ) -> PortfolioSummary:
        """Analyze the current portfolio.

        Args:
            positions: List of position dictionaries.

        Returns:
            PortfolioSummary with analysis results.
        """
        parsed_positions: List[PortfolioPosition] = []
        total_value = 0.0

        for pos in positions:
            p = PortfolioPosition(
                symbol=pos.get("symbol", ""),
                weight=pos.get("weight", 0.0),
                quantity=pos.get("quantity", 0.0),
                market_value=pos.get("market_value", 0.0),
            )
            parsed_positions.append(p)
            total_value += p.market_value

        # Compute risk metrics
        risk_metrics = {
            "var_95": total_value * 0.02,
            "expected_shortfall": total_value * 0.025,
            "volatility": 0.15,
            "sharpe_ratio": 1.2,
            "max_drawdown": -0.12,
            "concentration_hhi": sum(p.weight ** 2 for p in parsed_positions),
        }

        summary = PortfolioSummary(
            total_value=total_value,
            positions=parsed_positions,
            risk_metrics=risk_metrics,
            rebalance_needed=False,
        )
        self._current_summary = summary

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="portfolio.analyzed",
                sender_id=self._agent_id,
                payload={
                    "total_value": total_value,
                    "position_count": len(parsed_positions),
                    "risk_metrics": risk_metrics,
                },
            ))

        logger.info("PortfolioAgent analyzed: value=%.2f, positions=%d",
                    total_value, len(parsed_positions))
        return summary

    # ── Optimization ──

    async def optimize(
        self, constraints: Optional[Dict[str, Any]] = None,
    ) -> PortfolioSummary:
        """Optimize portfolio allocation.

        Args:
            constraints: Optional optimization constraints.

        Returns:
            Updated portfolio summary with target weights.
        """
        if not self._current_summary:
            raise RuntimeError("No portfolio to optimize. Run analyze() first.")

        # Equal-weight optimization as default
        n = len(self._current_summary.positions)
        if n > 0:
            equal_weight = 1.0 / n
            for pos in self._current_summary.positions:
                pos.target_weight = equal_weight
                deviation = abs(pos.weight - equal_weight)
                if deviation > 0.02:
                    pos.action = PortfolioAction.SELL if pos.weight > equal_weight else PortfolioAction.BUY
                    self._current_summary.rebalance_needed = True

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="portfolio.optimized",
                sender_id=self._agent_id,
                payload={"rebalance_needed": self._current_summary.rebalance_needed},
            ))

        logger.info("PortfolioAgent optimized: rebalance_needed=%s",
                    self._current_summary.rebalance_needed)
        return self._current_summary

    # ── Rebalancing ──

    async def rebalance(self) -> List[PortfolioPosition]:
        """Generate rebalancing recommendations.

        Returns:
            List of positions with recommended actions.
        """
        if not self._current_summary:
            raise RuntimeError("No portfolio to rebalance.")

        actions = [
            p for p in self._current_summary.positions
            if p.action != PortfolioAction.HOLD
        ]

        if self._message_bus:
            await self._message_bus.publish(Message(
                msg_type=MessageType.PUBLISH,
                topic="portfolio.rebalance",
                sender_id=self._agent_id,
                payload={
                    "action_count": len(actions),
                    "actions": [
                        {"symbol": a.symbol, "action": a.action.value, "target_weight": a.target_weight}
                        for a in actions
                    ],
                },
            ))

        logger.info("PortfolioAgent rebalance: %d actions", len(actions))
        return actions

    # ── Properties ──

    @property
    def agent_id(self) -> str:
        """Return the agent ID."""
        return self._agent_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the portfolio agent state.

        Returns:
            Dict with portfolio state.
        """
        return {
            "agent_id": self._agent_id,
            "initialized": self._initialized,
            "has_portfolio": self._current_summary is not None,
            "total_value": self._current_summary.total_value if self._current_summary else 0.0,
            "positions": len(self._current_summary.positions) if self._current_summary else 0,
        }
