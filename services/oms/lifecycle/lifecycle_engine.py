"""Order Lifecycle Engine — Unified entry point for order lifecycle operations.

Central driver engine for OMS order lifecycle. Manages the complete
journey from order creation through execution, with event-driven
state transitions, duplicate detection, and recovery.

Pipeline:
    Order Intent → Validate → Route → Dispatch → Execute → Monitor

Core API:
    process(): Execute full lifecycle for an order
    transition(): Execute a single state transition
    replay(): Replay historical events to reconstruct state
    recover(): Recover from snapshots after failures

Usage::

    engine = LifecycleEngine()
    await engine.initialize()

    order = Order(...)
    result = await engine.process(order)

    # Or step by step:
    await engine.transition(order, LifecycleEventType.VALIDATE)
    await engine.transition(order, LifecycleEventType.ROUTE)
    await engine.transition(order, LifecycleEventType.DISPATCH)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import (
    LifecycleStatus,
    StateTransitionValidator,
)
from services.oms.lifecycle.transition_engine import (
    TransitionEngine,
    TransitionEvent,
    TransitionEventType,
    TransitionResult,
)
from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore
from services.oms.lifecycle.lifecycle_dispatcher import (
    LifecycleDispatcher,
    LifecycleEvent,
    LifecycleEventType,
)
from services.oms.lifecycle.order_validator import OrderValidator
from services.oms.lifecycle.order_router import OrderRouter
from services.oms.lifecycle.order_dispatcher import OrderDispatcher
from services.oms.lifecycle.duplicate_event_detector import DuplicateEventDetector
from services.oms.lifecycle.event_sequence_checker import EventSequenceChecker
from services.oms.lifecycle.lifecycle_snapshot import SnapshotManager
from services.oms.lifecycle.lifecycle_audit import LifecycleAudit
from services.oms.lifecycle.metrics import LifecycleMetrics

logger = logging.getLogger(__name__)


class EngineStatus(str, Enum):
    """Lifecycle engine operational status."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ProcessResult:
    """Result of processing an order through the lifecycle engine."""
    order_id: str
    success: bool
    final_status: LifecycleStatus
    events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "success": self.success,
            "final_status": self.final_status.value,
            "events": self.events,
            "errors": self.errors,
            "warnings": self.warnings,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class LifecycleEngine:
    """Unified Order Lifecycle Engine.

    Central entry point for all order lifecycle operations. Manages
    the complete lifecycle from creation to terminal states, with
    event-driven transitions and full audit trail.

    Usage::

        engine = LifecycleEngine()
        await engine.initialize()

        order = Order(symbol="NVDA", side=OrderSide.BUY, quantity=100)
        result = await engine.process(order)
    """

    def __init__(self) -> None:
        self._status: EngineStatus = EngineStatus.STOPPED
        self._lock = asyncio.Lock()

        # Subsystems
        self._validator: Optional[StateTransitionValidator] = None
        self._event_store: Optional[LifecycleEventStore] = None
        self._transition_engine: Optional[TransitionEngine] = None
        self._lifecycle_dispatcher: Optional[LifecycleDispatcher] = None
        self._order_validator: Optional[OrderValidator] = None
        self._order_router: Optional[OrderRouter] = None
        self._order_dispatcher: Optional[OrderDispatcher] = None
        self._duplicate_detector: Optional[DuplicateEventDetector] = None
        self._sequence_checker: Optional[EventSequenceChecker] = None
        self._snapshot_manager: Optional[SnapshotManager] = None
        self._audit: Optional[LifecycleAudit] = None

        # Metrics
        self._metrics: Optional[LifecycleMetrics] = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self) -> None:
        """Initialize the lifecycle engine and all subsystems."""
        async with self._lock:
            if self._status == EngineStatus.RUNNING:
                return

            self._status = EngineStatus.INITIALIZING
            logger.info("Initializing Order Lifecycle Engine...")

            # Initialize subsystems
            self._validator = StateTransitionValidator()
            self._event_store = LifecycleEventStore()
            self._transition_engine = TransitionEngine(self._validator, self._event_store)
            self._lifecycle_dispatcher = LifecycleDispatcher(self._transition_engine)
            self._order_validator = OrderValidator()
            self._order_router = OrderRouter()
            self._order_dispatcher = OrderDispatcher()
            self._duplicate_detector = DuplicateEventDetector()
            self._sequence_checker = EventSequenceChecker()
            self._snapshot_manager = SnapshotManager(self._event_store)
            self._audit = LifecycleAudit(self._event_store)
            self._metrics = LifecycleMetrics()

            self._status = EngineStatus.RUNNING
            logger.info("Order Lifecycle Engine initialized successfully.")

    async def stop(self) -> None:
        """Stop the lifecycle engine gracefully."""
        async with self._lock:
            self._status = EngineStatus.STOPPING
            logger.info("Stopping Order Lifecycle Engine...")
            self._status = EngineStatus.STOPPED
            logger.info("Order Lifecycle Engine stopped.")

    # =========================================================================
    # Core Operations
    # =========================================================================

    async def process(self, order: Order) -> ProcessResult:
        """Execute the full lifecycle for an order.

        This is the main entry point. It validates the order, routes it
        to the appropriate broker, dispatches it, and monitors execution.

        Args:
            order: The order to process through the lifecycle

        Returns:
            ProcessResult with final status and event log
        """
        start_time = datetime.now(timezone.utc)
        result = ProcessResult(
            order_id=order.order_id,
            success=False,
            final_status=LifecycleStatus.CREATED,
        )

        try:
            # Step 1: Validate
            validation = await self._order_validator.validate(order)
            if not validation.is_valid:
                result.errors.extend(validation.errors)
                result.warnings.extend(validation.warnings)
                result.message = f"Order validation failed: {', '.join(validation.errors)}"
                await self._audit.record(
                    order_id=order.order_id,
                    action="validation_failed",
                    details={"errors": validation.errors},
                )
                return result

            await self._transition(
                order, TransitionEventType.VALIDATE,
                LifecycleStatus.CREATED, LifecycleStatus.VALIDATED,
            )
            result.events.append({"type": "validated", "status": "VALIDATED"})

            # Step 2: Route
            route_result = await self._order_router.route(order)
            if not route_result.success:
                result.errors.append(f"Routing failed: {route_result.reason}")
                result.message = f"Order routing failed: {route_result.reason}"
                return result

            await self._transition(
                order, TransitionEventType.ROUTE,
                LifecycleStatus.VALIDATED, LifecycleStatus.ROUTED,
            )
            result.events.append({
                "type": "routed",
                "status": "ROUTED",
                "broker": route_result.broker,
                "market": route_result.market,
            })

            # Step 3: Dispatch
            dispatch_result = await self._order_dispatcher.dispatch(order)
            if not dispatch_result.success:
                result.errors.append(f"Dispatch failed: {dispatch_result.reason}")
                result.message = f"Order dispatch failed: {dispatch_result.reason}"
                return result

            await self._transition(
                order, TransitionEventType.DISPATCH,
                LifecycleStatus.ROUTED, LifecycleStatus.SUBMITTED,
            )
            result.events.append({
                "type": "dispatched",
                "status": "SUBMITTED",
                "gateway": dispatch_result.gateway,
            })

            result.success = True
            result.final_status = LifecycleStatus(order.status.value)
            result.message = "Order successfully submitted to lifecycle"

            await self._audit.record(
                order_id=order.order_id,
                action="lifecycle_processed",
                details={"final_status": result.final_status.value},
            )

        except Exception as e:
            logger.exception(f"Error processing order {order.order_id}: {e}")
            result.errors.append(str(e))
            result.message = f"Lifecycle processing failed: {e}"
            await self._audit.record(
                order_id=order.order_id,
                action="lifecycle_error",
                details={"error": str(e)},
            )

        finally:
            result.duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            if self._metrics:
                self._metrics.record_lifecycle_event()
                self._metrics.record_transition_latency(result.duration_ms)

        return result

    async def transition(
        self,
        order: Order,
        event_type: LifecycleEventType,
        payload: Optional[dict[str, Any]] = None,
    ) -> TransitionResult:
        """Execute a single state transition on an order.

        Args:
            order: Order to transition
            event_type: Type of lifecycle event
            payload: Event-specific data

        Returns:
            TransitionResult with new status and details

        Raises:
            ValueError: If the transition is invalid
        """
        event = self._lifecycle_dispatcher.create_event(
            order_id=order.order_id,
            event_type=event_type,
            from_status=LifecycleStatus(order.status.value),
            payload=payload or {},
        )

        # Duplicate detection
        dup_result = self._duplicate_detector.check(event.event_id, order.order_id)
        if dup_result.is_duplicate:
            logger.warning(
                f"Duplicate event detected: {event.event_id}, discarding"
            )
            if self._metrics:
                self._metrics.record_duplicate()
            return TransitionResult(
                order_id=order.order_id,
                event=TransitionEvent(
                    event_id=event.event_id,
                    order_id=order.order_id,
                    event_type=TransitionEventType(event.event_type.value),
                    from_status=event.from_status,
                    to_status=event.to_status,
                    payload=event.payload,
                ),
                success=False,
                new_status=event.from_status,
                old_status=event.from_status,
                message="Duplicate event — discarded",
            )

        # Sequence check
        seq_result = self._sequence_checker.check(
            order.order_id, event.sequence_id
        )
        if seq_result.status.value == "gap_detected":
            logger.warning(
                f"Sequence gap for order {order.order_id}: "
                f"missing {seq_result.missing_sequences}"
            )
            # Gaps are logged but processing continues for now
            # In production, this would trigger recovery

        # Execute transition
        t_event = TransitionEvent(
            event_id=event.event_id,
            order_id=order.order_id,
            event_type=TransitionEventType(event.event_type.value),
            from_status=event.from_status,
            to_status=event.to_status,
            payload=event.payload,
        )

        result = await self._transition_engine.transition(order, t_event)

        if self._metrics:
            self._metrics.record_transition()

        await self._audit.record(
            order_id=order.order_id,
            action=f"transition_{event.event_type.value}",
            details={
                "from": result.old_status.value,
                "to": result.new_status.value,
                "event_id": event.event_id,
            },
        )

        return result

    async def replay(self, order_id: str) -> list[dict[str, Any]]:
        """Replay all historical events for an order.

        Reconstructs the order's state by replaying all stored events
        in sequence from the event store.

        Args:
            order_id: Order identifier

        Returns:
            List of replayed events as dictionaries
        """
        logger.info(f"Replaying events for order {order_id}")
        events = await self._event_store.replay(order_id)

        if self._metrics:
            self._metrics.record_replay()

        await self._audit.record(
            order_id=order_id,
            action="replay",
            details={"event_count": len(events)},
        )

        return [e.to_dict() for e in events]

    async def recover(self, order_id: str) -> Optional[dict[str, Any]]:
        """Recover an order's state from the most recent snapshot.

        Restores order state from the latest snapshot and then replays
        any events that occurred after the snapshot was taken.

        Args:
            order_id: Order identifier

        Returns:
            Recovered order state as dictionary, or None if no snapshot found
        """
        logger.info(f"Recovering order {order_id} from snapshot")

        snapshot = await self._snapshot_manager.get_latest(order_id)
        if snapshot is None:
            logger.warning(f"No snapshot found for order {order_id}")
            # Fall back to full replay
            events = await self._event_store.replay(order_id)
            if not events:
                return None
            return {
                "order_id": order_id,
                "events": [e.to_dict() for e in events],
                "recovered_from": "event_replay",
            }

        # Replay events after snapshot
        events_after = await self._event_store.get_events(
            order_id, since=snapshot.timestamp
        )

        recovered = {
            "order_id": order_id,
            "snapshot": snapshot.to_dict(),
            "events_after_snapshot": [e.to_dict() for e in events_after],
            "recovered_from": "snapshot",
        }

        await self._audit.record(
            order_id=order_id,
            action="recovery",
            details={
                "snapshot_timestamp": snapshot.timestamp.isoformat(),
                "events_replayed": len(events_after),
            },
        )

        return recovered

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _transition(
        self,
        order: Order,
        event_type: TransitionEventType,
        from_status: LifecycleStatus,
        to_status: LifecycleStatus,
        payload: Optional[dict[str, Any]] = None,
    ) -> TransitionResult:
        """Internal transition helper."""
        event = TransitionEvent(
            event_id=str(uuid.uuid4()),
            order_id=order.order_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            payload=payload or {},
        )
        return await self._transition_engine.transition(order, event)

    # =========================================================================
    # Accessors
    # =========================================================================

    @property
    def status(self) -> EngineStatus:
        """Current engine status."""
        return self._status

    @property
    def event_store(self) -> Optional[LifecycleEventStore]:
        """Access the event store."""
        return self._event_store

    @property
    def audit(self) -> Optional[LifecycleAudit]:
        """Access the audit trail."""
        return self._audit

    @property
    def metrics(self) -> Optional[LifecycleMetrics]:
        """Access lifecycle metrics."""
        return self._metrics

    @property
    def snapshot_manager(self) -> Optional[SnapshotManager]:
        """Access the snapshot manager."""
        return self._snapshot_manager

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": self._status.value,
            "event_store_events": sum(
                1 for _ in ([]
                    if self._event_store is None
                    else self._event_store._events
                )
            ) if self._event_store else 0,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize engine state."""
        return {
            "status": self._status.value,
            "subsystems": {
                "validator": self._validator is not None,
                "event_store": self._event_store is not None,
                "transition_engine": self._transition_engine is not None,
                "order_validator": self._order_validator is not None,
                "order_router": self._order_router is not None,
                "order_dispatcher": self._order_dispatcher is not None,
                "duplicate_detector": self._duplicate_detector is not None,
                "sequence_checker": self._sequence_checker is not None,
                "snapshot_manager": self._snapshot_manager is not None,
                "audit": self._audit is not None,
            },
        }
