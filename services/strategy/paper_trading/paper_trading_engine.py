"""
Paper Trading Engine
====================
Unified entry point for paper trading. Accepts Order Intents from the
Portfolio Decision Engine, simulates execution through virtual exchange,
tracks virtual portfolio performance, and drives strategy evaluation.

Pipeline:
    Order Intent → Paper Trading → Virtual Exchange → Virtual Portfolio
    → Performance Evaluation → Promotion Workflow → Live Deployment
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PaperOrderStatus(str, Enum):
    """Status of a paper trading order."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class PaperSessionStatus(str, Enum):
    """Status of a paper trading session."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class PaperOrder:
    """A paper trading order generated from an Order Intent."""
    order_id: str = field(default_factory=lambda: f"po_{uuid4().hex[:12]}")
    intent_id: str = ""
    session_id: str = ""
    strategy_id: str = ""
    instrument: str = ""
    side: str = ""           # BUY / SELL
    quantity: float = 0.0
    price: Optional[float] = None
    order_type: str = "MARKET"
    status: PaperOrderStatus = PaperOrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_price: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperTrade:
    """A completed paper trade."""
    trade_id: str = field(default_factory=lambda: f"pt_{uuid4().hex[:12]}")
    order_id: str = ""
    session_id: str = ""
    instrument: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperTradingEngine:
    """Unified paper trading engine.

    Accepts Order Intents, simulates full trade lifecycle through virtual
    exchange infrastructure, and drives strategy evaluation.
    """

    def __init__(self):
        self._sessions: Dict[str, "PaperSession"] = {}
        self._runtime: Optional["PaperRuntime"] = None
        self._manager: Optional["PaperManager"] = None

        # Subsystems (wired via wire())
        self._virtual_exchange: Optional["VirtualExchange"] = None
        self._virtual_oms: Optional["VirtualOMS"] = None
        self._virtual_portfolio: Optional["VirtualPortfolio"] = None
        self._virtual_account: Optional["VirtualAccount"] = None
        self._execution_simulator: Optional["ExecutionSimulator"] = None
        self._performance_evaluator: Optional["PerformanceEvaluator"] = None
        self._promotion_workflow: Optional["PromotionWorkflow"] = None
        self._kill_switch: Optional["KillSwitch"] = None
        self._continuous_evaluation: Optional["ContinuousEvaluation"] = None

        self._metrics: Dict[str, Any] = {}
        self.is_initialized = False

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def wire(
        self,
        runtime: Optional[Any] = None,
        manager: Optional[Any] = None,
        virtual_exchange: Optional[Any] = None,
        virtual_oms: Optional[Any] = None,
        virtual_portfolio: Optional[Any] = None,
        virtual_account: Optional[Any] = None,
        execution_simulator: Optional[Any] = None,
        performance_evaluator: Optional[Any] = None,
        promotion_workflow: Optional[Any] = None,
        kill_switch: Optional[Any] = None,
        continuous_evaluation: Optional[Any] = None,
    ) -> None:
        """Wire all paper trading subsystems."""
        self._runtime = runtime
        self._manager = manager
        self._virtual_exchange = virtual_exchange
        self._virtual_oms = virtual_oms
        self._virtual_portfolio = virtual_portfolio
        self._virtual_account = virtual_account
        self._execution_simulator = execution_simulator
        self._performance_evaluator = performance_evaluator
        self._promotion_workflow = promotion_workflow
        self._kill_switch = kill_switch
        self._continuous_evaluation = continuous_evaluation
        logger.info("PaperTradingEngine wired with %d subsystems",
                     sum(1 for x in [
                         runtime, manager, virtual_exchange, virtual_oms,
                         virtual_portfolio, virtual_account, execution_simulator,
                         performance_evaluator, promotion_workflow, kill_switch,
                         continuous_evaluation,
                     ] if x is not None))

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the paper trading engine and all subsystems."""
        if self._runtime:
            await self._runtime.initialize(config)
        if self._virtual_exchange:
            await self._virtual_exchange.initialize()
        if self._virtual_oms:
            await self._virtual_oms.initialize()
        if self._virtual_portfolio:
            await self._virtual_portfolio.initialize()
        if self._virtual_account:
            await self._virtual_account.initialize()
        if self._execution_simulator:
            await self._execution_simulator.initialize()
        if self._performance_evaluator:
            await self._performance_evaluator.initialize()
        self.is_initialized = True
        logger.info("PaperTradingEngine initialized")

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    async def submit(self, order_intent: Any, session_id: str = "") -> PaperOrder:
        """Submit an Order Intent for paper trading.

        Converts an OrderIntent from the Portfolio Decision Engine into
        a PaperOrder and routes it through the virtual execution pipeline.
        """
        if self._kill_switch and self._kill_switch.is_triggered(
            order_intent.strategy_id
        ):
            order = PaperOrder(
                intent_id=getattr(order_intent, 'intent_id', ''),
                session_id=session_id,
                strategy_id=getattr(order_intent, 'strategy_id', ''),
                instrument=getattr(order_intent, 'instrument', ''),
                side=getattr(order_intent, 'side', 'BUY'),
                quantity=getattr(order_intent, 'quantity', 0.0),
                status=PaperOrderStatus.REJECTED,
            )
            logger.warning("Order rejected by kill switch: %s", order.intent_id)
            return order

        order = PaperOrder(
            intent_id=getattr(order_intent, 'intent_id', ''),
            session_id=session_id,
            strategy_id=getattr(order_intent, 'strategy_id', ''),
            instrument=getattr(order_intent, 'instrument', ''),
            side=getattr(order_intent, 'side', 'BUY'),
            quantity=getattr(order_intent, 'quantity', 0.0),
            price=getattr(order_intent, 'limit_price', None),
            order_type=getattr(order_intent, 'intent_type', 'MARKET'),
            status=PaperOrderStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )

        # Route through OMS
        if self._virtual_oms:
            oms_order = await self._virtual_oms.accept_order(order)
            order.order_id = oms_order.order_id

        logger.info("Paper order submitted: %s (%s %s qty=%s)",
                     order.order_id, order.side, order.instrument, order.quantity)
        self._metrics['orders_submitted'] = self._metrics.get('orders_submitted', 0) + 1
        return order

    # ------------------------------------------------------------------
    # Simulate
    # ------------------------------------------------------------------

    async def simulate(self, session_id: str, start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> List[PaperTrade]:
        """Run paper trading simulation for a session over a date range."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("Unknown session: %s", session_id)
            return []

        trades: List[PaperTrade] = []
        # Iterate through session orders and simulate execution
        for order in session.orders:
            if self._execution_simulator:
                result = await self._execution_simulator.simulate_execution(order)
                if result.fills:
                    for fill in result.fills:
                        trade = PaperTrade(
                            order_id=order.order_id,
                            session_id=session_id,
                            instrument=order.instrument,
                            side=order.side,
                            quantity=fill.quantity,
                            price=fill.price,
                            slippage=result.slippage,
                            commission=result.commission,
                        )
                        trades.append(trade)
                        # Update virtual portfolio
                        if self._virtual_portfolio:
                            await self._virtual_portfolio.apply_trade(trade)

        session.trades = trades
        session.status = PaperSessionStatus.COMPLETED
        self._metrics['trades_simulated'] = self._metrics.get('trades_simulated', 0) + len(trades)
        logger.info("Simulation complete for session %s: %d trades", session_id, len(trades))
        return trades

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    async def evaluate(self, session_id: str) -> Dict[str, Any]:
        """Evaluate strategy performance for a paper trading session."""
        if self._performance_evaluator:
            report = await self._performance_evaluator.evaluate_session(session_id)
            return report.to_dict() if hasattr(report, 'to_dict') else {"error": "no_report"}
        return {"error": "performance_evaluator not wired"}

    # ------------------------------------------------------------------
    # Promote
    # ------------------------------------------------------------------

    async def promote(self, strategy_id: str) -> Dict[str, Any]:
        """Initiate strategy promotion from paper to live."""
        if self._promotion_workflow:
            result = await self._promotion_workflow.initiate_promotion(strategy_id)
            self._metrics['promotions_initiated'] = self._metrics.get('promotions_initiated', 0) + 1
            return result
        return {"error": "promotion_workflow not wired"}

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    async def create_session(self, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> str:
        """Create a new paper trading session."""
        session_id = f"pts_{uuid4().hex[:12]}"
        from services.strategy.paper_trading.paper_session import PaperSession
        session = PaperSession(
            session_id=session_id,
            strategy_id=strategy_id,
            config=config or {},
        )
        self._sessions[session_id] = session
        logger.info("Paper session created: %s for strategy %s", session_id, strategy_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Any]:
        return self._sessions.get(session_id)

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)
