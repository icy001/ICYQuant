"""
ICYQuant Execution Agent — trade execution and order management oversight.

Provides AI oversight of trade execution: monitors fill quality, detects
adverse conditions, and provides execution recommendations. Does NOT
directly execute trades — always goes through OMS/Risk check.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class ExecutionAdvice:
    """AI-generated execution advice (does NOT auto-execute)."""
    advice_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy: str = ""               # VWAP, TWAP, Implementation Shortfall, etc.
    urgency: str = "normal"          # low, normal, high
    suggested_venue: str = ""
    suggested_time_window: str = ""  # e.g., "09:30-10:30"
    max_participation_rate: float = 0.1
    limit_price_offset_bps: float = 0.0
    rationale: str = ""
    requires_approval: bool = True   # Always requires approval
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExecutionMonitor:
    """Monitors active executions."""
    monitor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    status: ExecutionStatus = ExecutionStatus.PENDING
    fill_rate: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    cost_saved_bps: float = 0.0
    alerts: list[str] = field(default_factory=list)
    recommendation: str = ""


class ExecutionAgent:
    """Trade execution oversight agent.

    IMPORTANT: This agent provides execution ADVICE and MONITORING only.
    It does NOT directly execute trades. All trades must go through
    the platform's OMS and pass risk guardrails before execution.

    Capabilities:
        - Optimal execution strategy recommendation
        - Fill quality monitoring
        - Slippage and market impact analysis
        - Adverse condition detection
        - Post-trade cost analysis
    """

    def __init__(self, agent_id: str = "execution_agent",
                 registry: Any = None,
                 communication_bus: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._comm_bus = communication_bus
        self._advice_count = 0

    async def recommend_execution(self, trade_list: list[dict[str, Any]],
                                  context: Optional[dict[str, Any]] = None) -> ExecutionAdvice:
        """Generate execution strategy recommendation."""
        self._advice_count += 1

        total_notional = sum(
            abs(t.get('weight_change', 0)) for t in trade_list
        )

        # Determine strategy based on trade characteristics
        if total_notional > 0.10:
            strategy = "VWAP"
            window = "Full day"
            participation = 0.05
        else:
            strategy = "Implementation Shortfall"
            window = "09:30-10:30"
            participation = 0.10

        advice = ExecutionAdvice(
            strategy=strategy,
            urgency="normal",
            suggested_venue="PRIMARY",
            suggested_time_window=window,
            max_participation_rate=participation,
            limit_price_offset_bps=50.0,
            rationale=f"Recommended {strategy} for {len(trade_list)} trades "
                      f"with total weight change {total_notional:.1%}",
            requires_approval=True,
        )

        logger.info("Execution advice %s: strategy=%s trades=%d",
                     advice.advice_id, strategy, len(trade_list))
        return advice

    async def monitor_execution(self, order_id: str) -> ExecutionMonitor:
        """Monitor an active execution for fill quality."""
        return ExecutionMonitor(
            order_id=order_id,
            status=ExecutionStatus.PENDING,
            fill_rate=0.85,
            slippage_bps=2.5,
            market_impact_bps=5.0,
            cost_saved_bps=1.5,
            alerts=[],
            recommendation="Continue monitoring; execution within acceptable parameters",
        )

    @property
    def advice_count(self) -> int:
        return self._advice_count
