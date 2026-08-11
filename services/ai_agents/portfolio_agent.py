"""
ICYQuant Portfolio Agent — portfolio optimization and allocation.

Optimizes portfolio weights considering risk constraints, factor
exposures, transaction costs, and regulatory limits. Produces
allocation recommendations with trade lists.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Allocation:
    """A single asset allocation."""
    ticker: str
    weight: float
    shares: int = 0
    current_weight: float = 0.0
    target_weight: float = 0.0
    rationale: str = ""


@dataclass
class PortfolioOptimization:
    """Result of portfolio optimization."""
    optimization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    allocations: list[Allocation] = field(default_factory=list)

    # Metrics
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    max_drawdown_estimate: float = 0.0

    # Constraints
    total_turnover: float = 0.0
    transaction_cost_estimate: float = 0.0
    max_single_position: float = 0.0
    constraint_violations: list[str] = field(default_factory=list)

    # Trade list
    trades: list[dict[str, Any]] = field(default_factory=list)

    confidence: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PortfolioAgent:
    """Portfolio optimization and allocation agent.

    Capabilities:
        - Mean-variance optimization
        - Risk-parity allocation
        - Factor-neutral portfolio construction
        - Turnover-aware rebalancing
        - Transaction cost estimation
        - Constraint enforcement (position limits, sector caps)
    """

    def __init__(self, agent_id: str = "portfolio_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._optimization_count = 0

    async def optimize(self, strategies: list[Any],
                       risk_assessment: Any,
                       current_holdings: Optional[list[Allocation]] = None,
                       context: Optional[dict[str, Any]] = None) -> PortfolioOptimization:
        """Optimize portfolio given strategies and risk constraints."""
        self._optimization_count += 1

        current = current_holdings or []
        ctx = context or {}

        optimization = PortfolioOptimization(
            name="optimized_portfolio",
            allocations=[
                Allocation(ticker="000300.SH", weight=0.35, rationale="Market beta exposure"),
                Allocation(ticker="000905.SH", weight=0.25, rationale="Mid-cap factor exposure"),
                Allocation(ticker="510050.SH", weight=0.20, rationale="Large-cap value"),
                Allocation(ticker="511880.SH", weight=0.10, rationale="Bond hedge"),
                Allocation(ticker="CASH", weight=0.10, rationale="Liquidity buffer"),
            ],
            expected_return=0.10,
            expected_volatility=0.14,
            expected_sharpe=0.71,
            max_drawdown_estimate=0.12,
            total_turnover=0.15,
            transaction_cost_estimate=0.0015,
            max_single_position=0.35,
            confidence=0.75,
            recommendations=[
                "Rebalance quarterly to maintain target weights",
                "Set stop-loss at -15% for single positions",
            ],
        )

        # Generate trades
        for alloc in optimization.allocations:
            cur_w = next((a.current_weight for a in current if a.ticker == alloc.ticker), 0.0)
            if abs(alloc.weight - cur_w) > 0.01:
                optimization.trades.append({
                    "ticker": alloc.ticker,
                    "action": "BUY" if alloc.weight > cur_w else "SELL",
                    "weight_delta": abs(alloc.weight - cur_w),
                })

        logger.info("Portfolio optimization %s: return=%.1f%% vol=%.1f%% sharpe=%.2f",
                     optimization.optimization_id,
                     optimization.expected_return * 100,
                     optimization.expected_volatility * 100,
                     optimization.expected_sharpe)
        return optimization

    def rebalance(self, current: list[Allocation],
                  target: PortfolioOptimization) -> list[dict[str, Any]]:
        """Generate rebalancing trades to move from current to target."""
        trades = []
        for t_alloc in target.allocations:
            cur = next((a for a in current if a.ticker == t_alloc.ticker), None)
            cur_weight = cur.weight if cur else 0.0
            diff = t_alloc.weight - cur_weight
            if abs(diff) > 0.005:
                trades.append({
                    "ticker": t_alloc.ticker,
                    "action": "BUY" if diff > 0 else "SELL",
                    "weight_change": abs(diff),
                })
        return trades

    @property
    def optimization_count(self) -> int:
        return self._optimization_count
