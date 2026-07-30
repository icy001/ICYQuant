"""Execution Agent - trade execution optimization.

Responsible for optimal trade execution:
- Algorithm selection (VWAP, TWAP, POV, etc.)
- Market impact minimization
- Liquidity-aware execution
- Dynamic order splitting
- Execution quality monitoring

Connects with Commit 4 Liquidity Engine and Execution Optimizer.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .agent_base import (
    BaseAgent, AgentStatus, Observation, Analysis, Decision, DecisionAction,
)

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(Enum):
    """Available execution algorithms."""
    VWAP = "vwap"          # Volume-Weighted Average Price
    TWAP = "twap"          # Time-Weighted Average Price
    POV = "pov"            # Percentage of Volume
    ICEBERG = "iceberg"    # Hidden order slices
    ADAPTIVE = "adaptive"  # Market-condition adaptive
    SMART = "smart"        # AI-driven smart routing
    MARKET = "market"      # Simple market order
    LIMIT = "limit"        # Limit order


class ExecutionStatus(Enum):
    """Order execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class ExecutionOrder:
    """An execution order with algorithm and parameters."""

    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    action: str = ""  # BUY/SELL
    quantity: int = 0
    algorithm: ExecutionAlgorithm = ExecutionAlgorithm.ADAPTIVE
    status: ExecutionStatus = ExecutionStatus.PENDING
    limit_price: Optional[float] = None
    urgency: str = "normal"  # low, normal, high, critical
    parent_proposal_id: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    filled_quantity: int = 0
    avg_price: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    total_cost_bps: float = 0.0
    slices: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "algorithm": self.algorithm.value,
            "status": self.status.value,
            "limit_price": self.limit_price,
            "urgency": self.urgency,
            "parent_proposal_id": self.parent_proposal_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "filled_quantity": self.filled_quantity,
            "avg_price": self.avg_price,
            "slippage_bps": self.slippage_bps,
            "market_impact_bps": self.market_impact_bps,
            "total_cost_bps": self.total_cost_bps,
            "fill_pct": (self.filled_quantity / self.quantity * 100) if self.quantity > 0 else 0,
        }

    @property
    def fill_pct(self) -> float:
        if self.quantity == 0:
            return 0
        return self.filled_quantity / self.quantity * 100


class ExecutionAgent(BaseAgent):
    """Execution Agent - optimal trade execution.

    Responsibilities:
    - Select best execution algorithm per trade
    - Split large orders to minimize market impact
    - Monitor execution quality
    - Adapt to changing market conditions
    - Report execution results

    Decision factors:
    - Order size relative to ADV (Average Daily Volume)
    - Current liquidity conditions
    - Volatility regime
    - Urgency of execution
    - Market impact models
    """

    agent_type = "execution_agent"

    def __init__(self, name: str = None, config: Dict[str, Any] = None):
        super().__init__(name=name, config=config)
        self._orders: List[ExecutionOrder] = []
        self._completed_orders: List[ExecutionOrder] = []
        self._active_orders: Dict[str, ExecutionOrder] = {}
        self._market_data: Dict[str, Dict[str, Any]] = {}
        self._liquidity_data: Dict[str, Dict[str, Any]] = {}

        # Execution parameters
        self._max_participation_rate = self.config.get("max_participation_rate", 0.10)  # 10% of volume
        self._max_order_slices = self.config.get("max_order_slices", 20)
        self._min_slice_pct = self.config.get("min_slice_pct", 5.0)
        self._slippage_tolerance_bps = self.config.get("slippage_tolerance_bps", 50)

        # Register message handlers
        self.communicator.register_handler("EXECUTE_TRADES", self._on_execute_trades)
        self.communicator.register_handler("MARKET_STATE", self._on_market_state)
        self.communicator.register_handler("CANCEL_ORDER", self._on_cancel_order)

    # ── Lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        super().start()
        self.memory.set_working("executed_count", 0)
        logger.info("ExecutionAgent [%s] started", self.name)

    # ── Message Handlers ────────────────────────────────────────

    def _on_execute_trades(self, data: Dict[str, Any]) -> None:
        """Handle execution request from Portfolio Agent."""
        proposal_id = data.get("proposal_id", "")
        portfolio_id = data.get("portfolio_id", "default")
        trades = data.get("trades", [])

        for trade in trades:
            order = self.create_order(
                symbol=trade["symbol"],
                action=trade["action"],
                weight_change=trade.get("weight_change", 0),
                parent_proposal_id=proposal_id,
                urgency=trade.get("urgency", "normal"),
            )
            if order:
                self._execute_order(order)

        logger.info(
            "[%s] Received %d trade(s) from proposal %s",
            self.name, len(trades), proposal_id,
        )

    def _on_market_state(self, data: Dict[str, Any]) -> None:
        """Handle market state updates for execution context."""
        self.memory.set_working("market_state", data)
        # Adapt active orders if market conditions change significantly
        volatility = data.get("volatility", "medium")
        if volatility in ("high", "extreme"):
            for order in self._active_orders.values():
                if order.algorithm == ExecutionAlgorithm.VWAP:
                    order.algorithm = ExecutionAlgorithm.ADAPTIVE
                    logger.info("[%s] Switched %s to ADAPTIVE due to high vol", self.name, order.order_id)

    def _on_cancel_order(self, data: Dict[str, Any]) -> None:
        """Handle order cancellation request."""
        order_id = data.get("order_id", "")
        order = self._active_orders.get(order_id)
        if order and order.status in (ExecutionStatus.PENDING, ExecutionStatus.QUEUED, ExecutionStatus.PARTIAL):
            order.status = ExecutionStatus.CANCELLED
            order.completed_at = time.time()
            self._active_orders.pop(order_id, None)
            logger.info("[%s] Cancelled order %s", self.name, order_id)

    # ── Main Agent Loop ─────────────────────────────────────────

    def observe(self) -> Optional[Observation]:
        """Monitor active orders and execution quality."""
        return Observation(
            source=self.name,
            data={
                "active_orders": len(self._active_orders),
                "completed_orders": len(self._completed_orders),
                "total_orders": len(self._orders),
                "market_state": self.memory.get_working("market_state", {}),
            },
            tags=["execution", "monitoring"],
        )

    def analyze(self, observation: Optional[Observation]) -> Optional[Analysis]:
        """Analyze execution quality and identify issues."""
        if observation is None:
            return None

        data = observation.data
        signals = []
        confidence = 0.7

        # Check for stalled orders
        now = time.time()
        for order in self._active_orders.values():
            if order.started_at and (now - order.started_at) > 300:  # 5 min
                signals.append({
                    "type": "STALLED_ORDER",
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "elapsed": now - order.started_at,
                    "recommendation": "review_or_cancel",
                })

        # Execution quality summary
        recent_completions = [
            o for o in self._completed_orders[-20:]
            if o.total_cost_bps > 0
        ]
        if recent_completions:
            avg_cost = sum(o.total_cost_bps for o in recent_completions) / len(recent_completions)
            if avg_cost > self._slippage_tolerance_bps:
                signals.append({
                    "type": "HIGH_EXECUTION_COST",
                    "avg_cost_bps": avg_cost,
                    "threshold": self._slippage_tolerance_bps,
                    "recommendation": "review_algorithm_selection",
                })
                confidence = 0.6

        return Analysis(
            agent=self.name,
            summary=f"Execution: {len(self._active_orders)} active, {len(self._completed_orders)} completed",
            metrics={
                "active_orders": len(self._active_orders),
                "completed_orders": len(self._completed_orders),
            },
            signals=signals,
            confidence=confidence,
        )

    def decide(self, analysis: Optional[Analysis]) -> Optional[Decision]:
        """Execution agent doesn't initiate trades - it executes assigned orders."""
        return Decision(
            agent=self.name,
            action=DecisionAction.HOLD,
            symbol="",
            confidence=0.8,
            reason=["Execution agent monitors and executes - no independent decisions"],
        )

    # ── Order Management ────────────────────────────────────────

    def create_order(
        self,
        symbol: str,
        action: str,
        weight_change: float = 0.0,
        quantity: int = 0,
        parent_proposal_id: str = "",
        urgency: str = "normal",
        limit_price: Optional[float] = None,
    ) -> Optional[ExecutionOrder]:
        """Create an execution order with optimal algorithm selection."""
        # Select algorithm based on characteristics
        algorithm = self._select_algorithm(symbol, action, weight_change, urgency)

        # Determine order slices
        num_slices = self._calculate_slices(symbol, weight_change, urgency)

        order = ExecutionOrder(
            symbol=symbol,
            action=action,
            quantity=quantity,
            algorithm=algorithm,
            limit_price=limit_price,
            urgency=urgency,
            parent_proposal_id=parent_proposal_id,
            metadata={
                "weight_change": weight_change,
                "num_slices": num_slices,
            },
        )

        self._orders.append(order)
        return order

    def _select_algorithm(
        self, symbol: str, action: str, weight_change: float, urgency: str
    ) -> ExecutionAlgorithm:
        """Select the optimal execution algorithm."""
        # Get market context
        market_state = self.memory.get_working("market_state", {})
        volatility = market_state.get("volatility", "medium")
        liquidity = market_state.get("liquidity", "normal")

        # Urgency-based selection
        if urgency == "critical":
            return ExecutionAlgorithm.MARKET

        if urgency == "high":
            return ExecutionAlgorithm.POV

        # Volatility-based
        if volatility in ("high", "extreme"):
            return ExecutionAlgorithm.ADAPTIVE

        # Liquidity-based
        if liquidity == "tight":
            return ExecutionAlgorithm.ICEBERG

        # Large orders
        if abs(weight_change) > 5.0:
            return ExecutionAlgorithm.VWAP

        # Default: smart adaptive
        return ExecutionAlgorithm.ADAPTIVE

    def _calculate_slices(
        self, symbol: str, weight_change: float, urgency: str
    ) -> int:
        """Calculate optimal number of order slices."""
        base_slices = max(1, int(abs(weight_change) / self._min_slice_pct))

        # Adjust for urgency
        if urgency == "critical":
            base_slices = 1
        elif urgency == "high":
            base_slices = max(1, base_slices // 2)
        elif urgency == "low":
            base_slices = min(self._max_order_slices, base_slices * 2)

        return min(self._max_order_slices, max(1, base_slices))

    def _execute_order(self, order: ExecutionOrder) -> None:
        """Execute (or simulate) an order."""
        order.status = ExecutionStatus.QUEUED
        order.started_at = time.time()
        self._active_orders[order.order_id] = order

        # In simulation mode: immediately complete with simulated fill
        # In production: this would connect to the execution platform
        order.status = ExecutionStatus.COMPLETED
        order.filled_quantity = order.quantity if order.quantity > 0 else 1000
        order.avg_price = 100.0  # Simulated
        order.completed_at = time.time()

        # Simulate execution quality metrics
        order.slippage_bps = abs(hash(order.symbol + str(time.time())) % 20)  # 0-20 bps
        order.market_impact_bps = abs(hash(order.symbol + "impact") % 10)     # 0-10 bps
        order.total_cost_bps = order.slippage_bps + order.market_impact_bps

        # Track completion
        self._active_orders.pop(order.order_id, None)
        self._completed_orders.append(order)
        self.memory.set_working(
            "executed_count",
            self.memory.get_working("executed_count", 0) + 1,
        )

        # Report completion
        self.send_to(
            recipient="supervisor",
            event="EXECUTION_COMPLETE",
            data=order.to_dict(),
        )

        # Also notify portfolio agent
        self.send_to(
            recipient="portfolio_agent",
            event="ORDER_FILLED",
            data=order.to_dict(),
        )

        logger.info(
            "[%s] Executed %s %s: algo=%s, cost=%.1fbps",
            self.name, order.action, order.symbol,
            order.algorithm.value, order.total_cost_bps,
        )

        # Learn from execution
        self.memory.learn_from_outcome(
            decision=order.to_dict(),
            outcome="completed",
            reward=1.0 if order.total_cost_bps < 30 else 0.5,
            context={
                "algorithm": order.algorithm.value,
                "market_state": self.memory.get_working("market_state", {}),
            },
        )

    # ── Execution Quality ───────────────────────────────────────

    def get_execution_quality(self) -> Dict[str, Any]:
        """Get execution quality metrics."""
        completed = self._completed_orders
        if not completed:
            return {"status": "no_data"}

        costs = [o.total_cost_bps for o in completed]
        slippages = [o.slippage_bps for o in completed]
        fills = [o.fill_pct for o in completed]

        return {
            "total_orders": len(completed),
            "avg_total_cost_bps": sum(costs) / len(costs),
            "max_total_cost_bps": max(costs),
            "avg_slippage_bps": sum(slippages) / len(slippages),
            "avg_fill_pct": sum(fills) / len(fills),
            "algorithm_usage": self._get_algorithm_usage(),
        }

    def _get_algorithm_usage(self) -> Dict[str, int]:
        """Get algorithm usage statistics."""
        usage: Dict[str, int] = {}
        for order in self._completed_orders:
            algo = order.algorithm.value
            usage[algo] = usage.get(algo, 0) + 1
        return usage

    # ── Query Methods ───────────────────────────────────────────

    def get_orders(
        self, status: ExecutionStatus = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get orders with optional status filter."""
        results = self._orders
        if status:
            results = [o for o in results if o.status == status]
        return [o.to_dict() for o in results[-limit:]]

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get currently active orders."""
        return [o.to_dict() for o in self._active_orders.values()]

    def get_status_report(self) -> Dict[str, Any]:
        report = super().get_status_report()
        report.update({
            "active_orders": len(self._active_orders),
            "completed_orders": len(self._completed_orders),
            "total_orders": len(self._orders),
            "execution_quality": self.get_execution_quality(),
        })
        return report
