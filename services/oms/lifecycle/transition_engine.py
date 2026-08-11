"""Transition Engine — State transition execution and validation.

Core FSM engine that orchestrates state transitions:
    Current State → Incoming Event → Transition Rules → Next State

Features:
- Strict transition validation via StateTransitionValidator
- Event-driven state change execution
- Pre/post transition hooks for extensibility
- Support for recovery mode (relaxed validation)
- Transition audit logging

Usage::

    engine = TransitionEngine(validator, event_store)
    result = await engine.transition(order, LifecycleEvent(...))
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import (
    LifecycleStatus,
    StateTransitionValidator,
    InvalidTransitionError,
)
from services.oms.lifecycle.lifecycle_event_store import LifecycleEventStore

logger = logging.getLogger(__name__)


class TransitionEventType(str, Enum):
    """Types of transition events."""
    VALIDATE = "validate"
    ROUTE = "route"
    DISPATCH = "dispatch"
    ACKNOWLEDGE = "acknowledge"
    WORKING = "working"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    REPLACE = "replace"
    CANCEL = "cancel"
    REJECT = "reject"
    EXPIRE = "expire"
    SUSPEND = "suspend"
    RESUME = "resume"
    RECOVER = "recover"


@dataclass
class TransitionEvent:
    """Event triggering a state transition."""
    event_id: str
    order_id: str
    event_type: TransitionEventType
    from_status: LifecycleStatus
    to_status: LifecycleStatus
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "event_type": self.event_type.value,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "payload": self.payload,
        }


@dataclass
class TransitionResult:
    """Result of a state transition execution."""
    order_id: str
    event: TransitionEvent
    success: bool
    new_status: LifecycleStatus
    old_status: LifecycleStatus
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status_changed(self) -> bool:
        """Whether the status actually changed."""
        return self.new_status != self.old_status

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "event": self.event.to_dict(),
            "success": self.success,
            "new_status": self.new_status.value,
            "old_status": self.old_status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


TransitionHook = Callable[[Order, TransitionEvent], Any]


class TransitionEngine:
    """Executes validated state transitions for orders.

    The TransitionEngine is the FSM execution layer. It validates
    each transition via StateTransitionValidator, persists events,
    updates order state, and runs pre/post hooks.

    Characteristics:
    - No illegal state jumps allowed
    - Support for dynamic state extension
    - Recovery mode for exception handling
    - Hook system for custom transition logic
    """

    def __init__(
        self,
        validator: StateTransitionValidator,
        event_store: LifecycleEventStore,
    ) -> None:
        """Initialize transition engine.

        Args:
            validator: State transition rule validator
            event_store: Event-sourced persistence layer
        """
        self._validator = validator
        self._event_store = event_store
        self._pre_hooks: list[TransitionHook] = []
        self._post_hooks: list[TransitionHook] = []
        self._recovery_mode: bool = False

    # ---- Core Transition ----

    async def transition(
        self,
        order: Order,
        event: TransitionEvent,
        force: bool = False,
    ) -> TransitionResult:
        """Execute a state transition for an order.

        Args:
            order: Order to transition
            event: Transition event describing the change
            force: Force transition (skip validation, recovery mode)

        Returns:
            TransitionResult with new status and details

        Raises:
            InvalidTransitionError: If transition is not allowed and force=False
        """
        current_status = LifecycleStatus(order.status.value)
        old_status = current_status

        # Validate transition (unless forced / recovery)
        if not force and not self._recovery_mode:
            self._validator.validate_or_raise(
                order.order_id, current_status, event.to_status
            )

        # Run pre-hooks
        await self._run_pre_hooks(order, event)

        # Persist event
        await self._event_store.store_event(
            order_id=order.order_id,
            event_type=event.event_type.value,
            from_status=event.from_status.value,
            to_status=event.to_status.value,
            payload=event.payload,
            metadata=event.metadata,
        )

        # Execute state change
        new_ord_status = event.to_status.to_order_status() or order.status
        order.record_status_change(
            from_status=event.from_status.to_order_status() or order.status,
            to_status=new_ord_status,
        )
        order.status = new_ord_status
        order.updated_at = datetime.now(timezone.utc)

        # Run post-hooks
        await self._run_post_hooks(order, event)

        result = TransitionResult(
            order_id=order.order_id,
            event=event,
            success=True,
            new_status=event.to_status,
            old_status=old_status,
            message=self._validator.get_description(event.from_status, event.to_status),
            metadata=event.metadata,
        )

        logger.info(
            f"Order {order.order_id} transitioned: "
            f"{old_status.value} -> {event.to_status.value} "
            f"via {event.event_type.value}"
        )

        return result

    async def validate(
        self,
        order: Order,
        event: TransitionEvent,
    ) -> bool:
        """Validate a transition without executing it.

        Args:
            order: Order to check
            event: Proposed transition event

        Returns:
            True if the transition is valid
        """
        current_status = LifecycleStatus(order.status.value)
        return self._validator.can_transition(current_status, event.to_status)

    async def get_allowed_next_states(
        self, order: Order
    ) -> set[LifecycleStatus]:
        """Get all valid next states for an order.

        Args:
            order: Order to query

        Returns:
            Set of allowed next lifecycle status values
        """
        current_status = LifecycleStatus(order.status.value)
        return self._validator.get_allowed_transitions(current_status)

    # ---- Hook Management ----

    def add_pre_hook(self, hook: TransitionHook) -> None:
        """Add a hook to run before each transition.

        Args:
            hook: Async callable (order, event) -> any
        """
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: TransitionHook) -> None:
        """Add a hook to run after each transition.

        Args:
            hook: Async callable (order, event) -> any
        """
        self._post_hooks.append(hook)

    async def _run_pre_hooks(self, order: Order, event: TransitionEvent) -> None:
        """Execute all pre-transition hooks."""
        for hook in self._pre_hooks:
            try:
                result = hook(order, event)
                # Support both sync and async hooks
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception(
                    f"Pre-hook failed for order {order.order_id} "
                    f"transition {event.event_type.value}"
                )

    async def _run_post_hooks(self, order: Order, event: TransitionEvent) -> None:
        """Execute all post-transition hooks."""
        for hook in self._post_hooks:
            try:
                result = hook(order, event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception(
                    f"Post-hook failed for order {order.order_id} "
                    f"transition {event.event_type.value}"
                )

    # ---- Recovery Mode ----

    @property
    def recovery_mode(self) -> bool:
        """Whether recovery mode is enabled."""
        return self._recovery_mode

    def enable_recovery_mode(self) -> None:
        """Enable recovery mode — bypasses strict validation."""
        self._recovery_mode = True
        self._validator.enable_recovery_mode()
        logger.info("TransitionEngine: recovery mode enabled")

    def disable_recovery_mode(self) -> None:
        """Disable recovery mode — restore strict validation."""
        self._recovery_mode = False
        self._validator.disable_recovery_mode()
        logger.info("TransitionEngine: recovery mode disabled")

    # ---- Utilities ----

    def is_terminal(self, status: LifecycleStatus) -> bool:
        """Check if a status is terminal."""
        return self._validator.is_terminal(status)

    def is_active(self, status: LifecycleStatus) -> bool:
        """Check if a status is active."""
        return self._validator.is_active(status)

    def to_dict(self) -> dict[str, Any]:
        """Serialize engine state."""
        return {
            "recovery_mode": self._recovery_mode,
            "pre_hooks": len(self._pre_hooks),
            "post_hooks": len(self._post_hooks),
            "transitions": self._validator.to_dict(),
        }
