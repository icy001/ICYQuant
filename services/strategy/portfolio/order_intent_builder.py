"""
Order Intent Builder
====================
Converts portfolio decisions into standardized Order Intent objects.

Pipeline:
    PortfolioDecision → OrderIntentBuilder → OrderIntent → Risk Engine / OMS
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.strategy.portfolio.order_intent import (
    IntentBatch,
    IntentSide,
    IntentStatus,
    IntentType,
    OrderIntent,
)

logger = logging.getLogger(__name__)


@dataclass
class IntentBuildContext:
    """Context for building order intents."""

    portfolio_id: str = ""
    default_destination: str = "default_oms"
    default_time_in_force: str = "DAY"
    default_intent_type: IntentType = IntentType.MARKET
    max_intents_per_batch: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderIntentBuilder:
    """
    Builds standardized Order Intent objects from portfolio decisions.

    This is the final stage of the Strategy Platform pipeline.
    All output must go through this builder to ensure standardized format.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Default build context
        self._default_context = IntentBuildContext(
            default_destination=self._config.get("default_destination", "default_oms"),
            default_time_in_force=self._config.get("default_time_in_force", "DAY"),
            default_intent_type=IntentType(
                self._config.get("default_intent_type", "MARKET")
            ),
            max_intents_per_batch=self._config.get("max_intents_per_batch", 100),
        )

        # Per-strategy overrides
        self._strategy_overrides: Dict[str, Dict[str, Any]] = self._config.get(
            "strategy_overrides", {}
        )

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("OrderIntentBuilder initialized")

    async def shutdown(self) -> None:
        self._strategy_overrides.clear()
        self._initialized = False
        logger.info("OrderIntentBuilder shut down")

    # ------------------------------------------------------------------
    # Direction Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_side(direction: str) -> IntentSide:
        """Map signal/decision direction to IntentSide."""
        direction = direction.upper().strip()
        long_aliases = {"LONG", "BUY", "BUY_TO_OPEN", "OPEN_LONG", "COVER"}
        short_aliases = {"SHORT", "SELL", "SELL_TO_OPEN", "OPEN_SHORT", "SELL_SHORT", "SHORT_SELL"}
        exit_aliases = {"EXIT", "CLOSE", "SELL_TO_CLOSE", "BUY_TO_CLOSE", "LIQUIDATE", "REDUCE"}

        if direction in long_aliases:
            return IntentSide.BUY
        elif direction in short_aliases:
            return IntentSide.SELL_SHORT
        elif direction in exit_aliases:
            return IntentSide.SELL
        else:
            # Default: try to infer from context
            return IntentSide.BUY

    @staticmethod
    def _map_intent_type(decision_type: str) -> IntentType:
        """Map decision type to IntentType."""
        mapping = {
            "entry": IntentType.MARKET,
            "exit": IntentType.MARKET,
            "rebalance": IntentType.LIMIT,
            "hedge": IntentType.STOP,
            "reduce": IntentType.TWAP,
            "increase": IntentType.MARKET,
        }
        return mapping.get(decision_type, IntentType.MARKET)

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def _resolve_context(
        self,
        strategy_id: str,
        portfolio_id: str,
    ) -> IntentBuildContext:
        """Resolve build context with per-strategy overrides."""
        ctx = IntentBuildContext(
            portfolio_id=portfolio_id,
            default_destination=self._default_context.default_destination,
            default_time_in_force=self._default_context.default_time_in_force,
            default_intent_type=self._default_context.default_intent_type,
            max_intents_per_batch=self._default_context.max_intents_per_batch,
        )

        overrides = self._strategy_overrides.get(strategy_id, {})
        if "destination" in overrides:
            ctx.default_destination = overrides["destination"]
        if "time_in_force" in overrides:
            ctx.default_time_in_force = overrides["time_in_force"]
        if "intent_type" in overrides:
            try:
                ctx.default_intent_type = IntentType(overrides["intent_type"])
            except ValueError:
                pass

        return ctx

    async def build(
        self,
        decision: Any,
        context: Optional[IntentBuildContext] = None,
    ) -> OrderIntent:
        """
        Build a single Order Intent from a portfolio decision.

        Args:
            decision: PortfolioDecision or dict with decision data.
            context: Optional build context.

        Returns:
            Standardized OrderIntent.
        """
        if not self._initialized:
            await self.initialize()

        # Extract data from decision (supports both object and dict)
        if isinstance(decision, dict):
            d = decision
        else:
            d = decision.to_dict() if hasattr(decision, "to_dict") else {}

        strategy_id = d.get("strategy_id", "")
        portfolio_id = d.get("portfolio_id", "")
        ctx = context or self._resolve_context(strategy_id, portfolio_id)

        # Map direction to side
        direction = d.get("direction", "")
        side = self._map_side(direction)

        # Determine intent type
        decision_type = d.get("decision_type", "entry")
        if hasattr(decision_type, "value"):
            decision_type = decision_type.value
        intent_type = self._map_intent_type(decision_type)

        # Calculate quantity
        quantity = d.get("quantity", d.get("position_size", 0.0))
        allocated = d.get("allocated_capital", 0.0)

        intent = OrderIntent(
            batch_id=d.get("batch_id", ""),
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            signal_id=d.get("signal_id", ""),
            decision_id=d.get("decision_id", ""),
            instrument=d.get("instrument", ""),
            instrument_type=d.get("instrument_type", d.get("metadata", {}).get("instrument_type", "")),
            exchange=d.get("exchange", d.get("metadata", {}).get("exchange", "")),
            side=side,
            intent_type=intent_type,
            quantity=quantity,
            target_weight=d.get("target_weight", 0.0),
            current_weight=d.get("current_weight", 0.0),
            allocated_capital=allocated,
            priority=d.get("priority", 5),
            confidence=d.get("confidence", 0.0),
            reason=d.get("reason", ""),
            destination=ctx.default_destination,
            time_in_force=ctx.default_time_in_force,
            tags=d.get("tags", []),
            metadata=d.get("metadata", {}),
        )

        self._metrics["intents_built"] = self._metrics.get("intents_built", 0) + 1

        logger.debug(
            "Built intent %s: %s %s %.0f @ %s",
            intent.intent_id,
            intent.side.value,
            intent.instrument,
            intent.quantity,
            intent.destination,
        )

        return intent

    async def build_batch(
        self,
        batch: Any,
        context: Optional[IntentBuildContext] = None,
    ) -> List[OrderIntent]:
        """
        Build Order Intents for an entire decision batch.

        Args:
            batch: DecisionBatch or dict with decisions.
            context: Optional build context.

        Returns:
            List of OrderIntent objects.
        """
        if not self._initialized:
            await self.initialize()

        # Extract decisions
        if isinstance(batch, dict):
            decisions = batch.get("decisions", [])
            batch_id = batch.get("batch_id", "")
            portfolio_id = batch.get("portfolio_id", "")
        else:
            decisions = getattr(batch, "decisions", [])
            batch_id = getattr(batch, "batch_id", "")
            portfolio_id = getattr(batch, "portfolio_id", "")

        if not decisions:
            logger.warning("No decisions in batch %s", batch_id)
            return []

        # Limit batch size
        if len(decisions) > self._default_context.max_intents_per_batch:
            logger.warning(
                "Truncating batch from %d to %d decisions",
                len(decisions),
                self._default_context.max_intents_per_batch,
            )
            decisions = decisions[:self._default_context.max_intents_per_batch]

        # Build all intents
        intents = []
        for decision in decisions:
            if isinstance(decision, dict):
                decision["batch_id"] = batch_id
            elif hasattr(decision, "batch_id"):
                pass  # batch_id already set

            intent = await self.build(decision, context)
            intent.batch_id = batch_id
            intents.append(intent)

        # Create intent batch for tracking
        intent_batch = IntentBatch(
            batch_id=batch_id,
            portfolio_id=portfolio_id,
            intents=intents,
            total_notional=sum(i.notional_value for i in intents),
            total_quantity=sum(i.quantity for i in intents),
        )

        self._metrics["batches_built"] = self._metrics.get("batches_built", 0) + 1
        self._metrics["total_intents_built"] = (
            self._metrics.get("total_intents_built", 0) + len(intents)
        )

        logger.info(
            "Built batch %s: %d intents, total notional=%.2f",
            batch_id,
            len(intents),
            intent_batch.total_notional,
        )

        return intents

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_strategy_override(
        self,
        strategy_id: str,
        destination: Optional[str] = None,
        time_in_force: Optional[str] = None,
        intent_type: Optional[str] = None,
    ) -> None:
        """Set build overrides for a specific strategy."""
        override = self._strategy_overrides.get(strategy_id, {})
        if destination:
            override["destination"] = destination
        if time_in_force:
            override["time_in_force"] = time_in_force
        if intent_type:
            override["intent_type"] = intent_type
        self._strategy_overrides[strategy_id] = override

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
