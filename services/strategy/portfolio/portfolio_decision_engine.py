"""
Portfolio Decision Engine
=========================
Unified entry point for transforming signals into portfolio decisions
and standardized order intents.

Pipeline:
    Signal → Position Sizing → Capital Allocation → Exposure Check
    → Conflict Resolution → Order Netting → Order Intent
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


class DecisionType(str, Enum):
    """Type of portfolio decision."""

    ENTRY = "entry"
    EXIT = "exit"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    LIQUIDATE = "liquidate"
    REDUCE = "reduce"
    INCREASE = "increase"


class DecisionStatus(str, Enum):
    """Status of a portfolio decision."""

    PENDING = "pending"
    SIZING = "sizing"
    ALLOCATING = "allocating"
    CONSTRAINED = "constrained"
    CONFLICTED = "conflicted"
    NETTED = "netted"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    ERROR = "error"


@dataclass
class PortfolioDecision:
    """A single portfolio decision produced by the engine."""

    decision_id: str = field(default_factory=lambda: f"pd_{uuid4().hex[:12]}")
    portfolio_id: str = ""
    strategy_id: str = ""
    signal_id: str = ""

    instrument: str = ""
    decision_type: DecisionType = DecisionType.ENTRY
    direction: str = ""
    quantity: float = 0.0
    target_weight: float = 0.0
    current_weight: float = 0.0

    priority: int = 5
    confidence: float = 0.0

    allocated_capital: float = 0.0
    risk_budget: float = 0.0

    reason: str = ""
    status: DecisionStatus = DecisionStatus.PENDING

    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_status(self, status: DecisionStatus) -> None:
        """Transition the decision to a new status."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
            "instrument": self.instrument,
            "decision_type": self.decision_type.value,
            "direction": self.direction,
            "quantity": self.quantity,
            "target_weight": self.target_weight,
            "current_weight": self.current_weight,
            "priority": self.priority,
            "confidence": self.confidence,
            "allocated_capital": self.allocated_capital,
            "risk_budget": self.risk_budget,
            "reason": self.reason,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class DecisionBatch:
    """A batch of portfolio decisions processed together."""

    batch_id: str = field(default_factory=lambda: f"db_{uuid4().hex[:12]}")
    portfolio_id: str = ""
    decisions: List[PortfolioDecision] = field(default_factory=list)
    total_capital_allocated: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.decisions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "portfolio_id": self.portfolio_id,
            "decision_count": len(self.decisions),
            "total_capital_allocated": self.total_capital_allocated,
            "net_exposure": self.net_exposure,
            "gross_exposure": self.gross_exposure,
            "decisions": [d.to_dict() for d in self.decisions],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class PortfolioDecisionEngine:
    """
    Unified Portfolio Decision Engine.

    Transforms trading signals into institutional-grade portfolio decisions
    through a comprehensive pipeline: sizing → allocation → constraints →
    conflict resolution → netting → order intent generation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Sub-engines (lazy-initialized)
        self._sizing_engine = None
        self._capital_allocator = None
        self._exposure_manager = None
        self._constraints = None
        self._priority_manager = None
        self._conflict_resolver = None
        self._netting_engine = None
        self._intent_builder = None
        self._explainer = None

        self._metrics_registry: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the decision engine and all sub-engines."""
        if self._initialized:
            return

        from services.strategy.portfolio.position_sizing_engine import PositionSizingEngine
        from services.strategy.portfolio.capital_allocator import CapitalAllocator
        from services.strategy.portfolio.exposure_manager import ExposureManager
        from services.strategy.portfolio.portfolio_constraints import PortfolioConstraints
        from services.strategy.portfolio.strategy_priority import StrategyPriorityManager
        from services.strategy.portfolio.strategy_conflict_resolver import StrategyConflictResolver
        from services.strategy.portfolio.order_netting import OrderNettingEngine
        from services.strategy.portfolio.order_intent_builder import OrderIntentBuilder
        from services.strategy.portfolio.decision_explainer import DecisionExplainer

        self._sizing_engine = PositionSizingEngine(self._config.get("sizing", {}))
        self._capital_allocator = CapitalAllocator(self._config.get("capital", {}))
        self._exposure_manager = ExposureManager(self._config.get("exposure", {}))
        self._constraints = PortfolioConstraints(self._config.get("constraints", {}))
        self._priority_manager = StrategyPriorityManager(self._config.get("priority", {}))
        self._conflict_resolver = StrategyConflictResolver(self._config.get("conflict", {}))
        self._netting_engine = OrderNettingEngine(self._config.get("netting", {}))
        self._intent_builder = OrderIntentBuilder(self._config.get("intent", {}))
        self._explainer = DecisionExplainer(self._config.get("explainer", {}))

        await asyncio.gather(
            self._sizing_engine.initialize(),
            self._capital_allocator.initialize(),
            self._exposure_manager.initialize(),
            self._constraints.initialize(),
            self._priority_manager.initialize(),
            self._conflict_resolver.initialize(),
            self._netting_engine.initialize(),
            self._intent_builder.initialize(),
            self._explainer.initialize(),
        )

        self._initialized = True
        logger.info("PortfolioDecisionEngine initialized successfully")

    async def shutdown(self) -> None:
        """Gracefully shut down the decision engine."""
        self._initialized = False
        logger.info("PortfolioDecisionEngine shut down")

    # ------------------------------------------------------------------
    # Main Pipeline
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        signals: List[Any],
        portfolio_id: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> DecisionBatch:
        """
        Full pipeline: signals → sizing → allocation → constraints → conflict → netting → decisions.

        Args:
            signals: List of trading signals from the Signal Engine.
            portfolio_id: Target portfolio identifier.
            portfolio_state: Current portfolio state (holdings, weights, cash, etc.).

        Returns:
            DecisionBatch containing all processed decisions.
        """
        if not self._initialized:
            await self.initialize()

        logger.info(
            "Evaluating %d signals for portfolio %s", len(signals), portfolio_id
        )

        batch = DecisionBatch(portfolio_id=portfolio_id)

        # Stage 1: Position Sizing
        sized = await self._sizing_engine.size_positions(signals, portfolio_state)
        logger.debug("Stage 1: Sized %d positions", len(sized))

        # Stage 2: Capital Allocation
        allocated = await self._capital_allocator.allocate(sized, portfolio_id, portfolio_state)
        logger.debug("Stage 2: Allocated capital for %d candidates", len(allocated))

        # Stage 3: Exposure Check
        exposure_report = await self._exposure_manager.check(allocated, portfolio_state)
        if exposure_report.limit_hits:
            logger.warning("Stage 3: %d exposure limit(s) hit", len(exposure_report.limit_hits))
        logger.debug("Stage 3: Exposure check complete")

        # Stage 4: Constraints Check
        constrained = []
        for alloc in allocated:
            check = await self._constraints.check(alloc, portfolio_state)
            if check.passed:
                constrained.append(alloc)
            else:
                logger.info(
                    "Constraint check failed for %s: %s",
                    alloc.get("instrument", ""),
                    check.reason,
                )
        logger.debug("Stage 4: %d passed constraints", len(constrained))

        # Stage 5: Strategy Priority
        prioritized = await self._priority_manager.prioritize(constrained)
        logger.debug("Stage 5: Prioritized %d candidates", len(prioritized))

        # Stage 6: Conflict Resolution
        resolved = await self._conflict_resolver.resolve(prioritized, portfolio_state)
        logger.debug(
            "Stage 6: Resolved %d candidates (%d conflicts)",
            len(resolved),
            self._conflict_resolver.last_conflict_count if hasattr(self._conflict_resolver, 'last_conflict_count') else 0,
        )

        # Stage 7: Order Netting
        netted = await self._netting_engine.net(resolved)
        logger.debug("Stage 7: Netted to %d orders", len(netted))

        # Stage 8: Build Decisions
        decisions = []
        for net in netted:
            decision = PortfolioDecision(
                portfolio_id=portfolio_id,
                strategy_id=net.get("strategy_id", ""),
                signal_id=net.get("signal_id", ""),
                instrument=net.get("instrument", ""),
                decision_type=DecisionType(net.get("decision_type", "entry")),
                direction=net.get("direction", ""),
                quantity=net.get("quantity", 0.0),
                target_weight=net.get("target_weight", 0.0),
                current_weight=net.get("current_weight", 0.0),
                priority=net.get("priority", 5),
                confidence=net.get("confidence", 0.0),
                allocated_capital=net.get("allocated_capital", 0.0),
                risk_budget=net.get("risk_budget", 0.0),
                reason=net.get("reason", ""),
                status=DecisionStatus.APPROVED,
                metadata=net.get("metadata", {}),
            )
            decisions.append(decision)

        batch.decisions = decisions
        batch.total_capital_allocated = sum(d.allocated_capital for d in decisions)
        batch.gross_exposure = exposure_report.gross_exposure
        batch.net_exposure = exposure_report.net_exposure

        self._metrics_registry["evaluated_total"] = (
            self._metrics_registry.get("evaluated_total", 0) + len(signals)
        )
        self._metrics_registry["decisions_total"] = (
            self._metrics_registry.get("decisions_total", 0) + len(decisions)
        )

        logger.info(
            "Evaluation complete: %d signals → %d decisions (batch=%s)",
            len(signals),
            len(decisions),
            batch.batch_id,
        )

        return batch

    async def allocate(
        self,
        sized_positions: List[Dict[str, Any]],
        portfolio_id: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Allocate capital to sized positions."""
        if not self._initialized:
            await self.initialize()
        return await self._capital_allocator.allocate(sized_positions, portfolio_id, portfolio_state)

    async def build_order_intent(
        self,
        decision: PortfolioDecision,
    ) -> Any:
        """
        Build a standardized Order Intent from a portfolio decision.

        This is the final output of the Strategy Platform.
        """
        if not self._initialized:
            await self.initialize()
        return await self._intent_builder.build(decision)

    async def build_order_intents_batch(
        self,
        batch: DecisionBatch,
    ) -> List[Any]:
        """Build Order Intents for an entire decision batch."""
        if not self._initialized:
            await self.initialize()
        return await self._intent_builder.build_batch(batch)

    async def explain(
        self,
        decision: PortfolioDecision,
    ) -> Any:
        """Generate a human-readable explanation for a portfolio decision."""
        if not self._initialized:
            await self.initialize()
        return await self._explainer.explain(decision)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        """Return engine-level metrics snapshot."""
        return dict(self._metrics_registry)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
