"""State Transition Validator — Strict transition rule enforcement.

Validates all order state transitions against the defined FSM rules.
Allows dynamic extension of states and transitions for custom workflows.

Transition rules:
    CREATED           → VALIDATED, CANCELLED
    VALIDATED         → ROUTED, REJECTED
    ROUTED            → SUBMITTED, REJECTED
    SUBMITTED         → ACKNOWLEDGED, CANCELLED, REJECTED, EXPIRED
    ACKNOWLEDGED      → WORKING, CANCELLED
    WORKING           → PARTIALLY_FILLED, FILLED, CANCELLED, REPLACED
    PARTIALLY_FILLED  → PARTIALLY_FILLED, FILLED, CANCELLED
    FILLED            → (terminal)
    CANCELLED         → (terminal)
    REJECTED          → (terminal)
    EXPIRED           → (terminal)
    SUSPENDED         → WORKING, CANCELLED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, FrozenSet, Optional, Set

from services.oms.order.models import OrderStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Extended Order Status (adds WORKING, EXPIRED, SUSPENDED, REPLACED)
# =============================================================================


class LifecycleStatus(str, Enum):
    """Extended order lifecycle status for production environments.

    Extends the base OrderStatus with additional states:
    - WORKING: Order accepted and actively being worked at exchange
    - EXPIRED: Order expired before execution (time-in-force)
    - SUSPENDED: Order temporarily paused (kill switch / risk control)
    - REPLACED: Order has been replaced by a new version
    """

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ROUTED = "ROUTED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REPLACED = "REPLACED"

    @classmethod
    def from_order_status(cls, status: OrderStatus) -> "LifecycleStatus":
        """Convert from base OrderStatus."""
        return cls(status.value)

    def to_order_status(self) -> Optional[OrderStatus]:
        """Convert to base OrderStatus if mapping exists."""
        try:
            return OrderStatus(self.value)
        except ValueError:
            return None

    @classmethod
    def terminal_states(cls) -> set["LifecycleStatus"]:
        """Get all terminal (final) states."""
        return {
            cls.FILLED,
            cls.CANCELLED,
            cls.REJECTED,
            cls.EXPIRED,
            cls.REPLACED,
        }

    @classmethod
    def active_states(cls) -> set["LifecycleStatus"]:
        """Get all active (in-market) states."""
        return {
            cls.SUBMITTED,
            cls.ACKNOWLEDGED,
            cls.WORKING,
            cls.PARTIALLY_FILLED,
        }

    @property
    def is_terminal(self) -> bool:
        """Whether this is a terminal state."""
        return self in self.terminal_states()

    @property
    def is_active(self) -> bool:
        """Whether the order is active in the market."""
        return self in self.active_states()


# =============================================================================
# Transition Validator
# =============================================================================


@dataclass
class TransitionValidation:
    """Result of a transition validation."""
    order_id: str
    from_status: LifecycleStatus
    to_status: LifecycleStatus
    is_valid: bool = False
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "order_id": self.order_id,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "is_valid": self.is_valid,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class InvalidTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""

    def __init__(
        self,
        from_status: LifecycleStatus,
        to_status: LifecycleStatus,
        order_id: str = "",
    ) -> None:
        self.from_status = from_status
        self.to_status = to_status
        self.order_id = order_id
        msg = (
            f"Invalid state transition: {from_status.value} -> {to_status.value}"
            + (f" for order {order_id}" if order_id else "")
        )
        super().__init__(msg)


class StateTransitionValidator:
    """Validates order state transitions against defined rules.

    Enforces strict FSM rules for order lifecycle. Supports dynamic
    extension of transitions for custom workflows and recovery modes.

    Usage::

        validator = StateTransitionValidator()
        result = validator.validate(order_id, LifecycleStatus.CREATED, LifecycleStatus.VALIDATED)
        if result.is_valid:
            # proceed with transition
    """

    # Default transition rules: from_state → set of allowed to_states
    DEFAULT_TRANSITIONS: dict[LifecycleStatus, FrozenSet[LifecycleStatus]] = {
        LifecycleStatus.CREATED: frozenset({
            LifecycleStatus.VALIDATED,
            LifecycleStatus.CANCELLED,
        }),
        LifecycleStatus.VALIDATED: frozenset({
            LifecycleStatus.ROUTED,
            LifecycleStatus.REJECTED,
        }),
        LifecycleStatus.ROUTED: frozenset({
            LifecycleStatus.SUBMITTED,
            LifecycleStatus.REJECTED,
        }),
        LifecycleStatus.SUBMITTED: frozenset({
            LifecycleStatus.ACKNOWLEDGED,
            LifecycleStatus.CANCELLED,
            LifecycleStatus.REJECTED,
            LifecycleStatus.EXPIRED,
        }),
        LifecycleStatus.ACKNOWLEDGED: frozenset({
            LifecycleStatus.WORKING,
            LifecycleStatus.CANCELLED,
            LifecycleStatus.EXPIRED,
        }),
        LifecycleStatus.WORKING: frozenset({
            LifecycleStatus.PARTIALLY_FILLED,
            LifecycleStatus.FILLED,
            LifecycleStatus.CANCELLED,
            LifecycleStatus.REPLACED,
            LifecycleStatus.EXPIRED,
            LifecycleStatus.SUSPENDED,
        }),
        LifecycleStatus.PARTIALLY_FILLED: frozenset({
            LifecycleStatus.PARTIALLY_FILLED,  # Incremental fills
            LifecycleStatus.FILLED,
            LifecycleStatus.CANCELLED,
            LifecycleStatus.EXPIRED,
            LifecycleStatus.SUSPENDED,
        }),
        LifecycleStatus.SUSPENDED: frozenset({
            LifecycleStatus.WORKING,
            LifecycleStatus.CANCELLED,
            LifecycleStatus.EXPIRED,
        }),
        # Terminal states
        LifecycleStatus.FILLED: frozenset(),
        LifecycleStatus.CANCELLED: frozenset(),
        LifecycleStatus.REJECTED: frozenset(),
        LifecycleStatus.EXPIRED: frozenset(),
        LifecycleStatus.REPLACED: frozenset(),
    }

    # Human-readable transition descriptions
    TRANSITION_DESCRIPTIONS: dict[str, str] = {
        "CREATED->VALIDATED": "Order validated by OMS",
        "CREATED->CANCELLED": "Order cancelled before validation",
        "VALIDATED->ROUTED": "Order routed to broker gateway",
        "VALIDATED->REJECTED": "Order rejected during validation",
        "ROUTED->SUBMITTED": "Order submitted to exchange",
        "ROUTED->REJECTED": "Order rejected by routing layer",
        "SUBMITTED->ACKNOWLEDGED": "Order acknowledged by broker",
        "SUBMITTED->CANCELLED": "Order cancelled while pending",
        "SUBMITTED->REJECTED": "Order rejected by broker/exchange",
        "SUBMITTED->EXPIRED": "Order expired before acknowledgment",
        "ACKNOWLEDGED->WORKING": "Order now working at exchange",
        "ACKNOWLEDGED->CANCELLED": "Order cancelled after acknowledgment",
        "ACKNOWLEDGED->EXPIRED": "Order expired at exchange",
        "WORKING->PARTIALLY_FILLED": "Order partially filled",
        "WORKING->FILLED": "Order fully filled",
        "WORKING->CANCELLED": "Working order cancelled",
        "WORKING->REPLACED": "Order replaced with new parameters",
        "WORKING->EXPIRED": "Working order expired",
        "WORKING->SUSPENDED": "Order suspended (risk/kill switch)",
        "PARTIALLY_FILLED->PARTIALLY_FILLED": "Additional partial fill",
        "PARTIALLY_FILLED->FILLED": "Order fully filled",
        "PARTIALLY_FILLED->CANCELLED": "Remaining quantity cancelled",
        "PARTIALLY_FILLED->EXPIRED": "Remaining quantity expired",
        "PARTIALLY_FILLED->SUSPENDED": "Partially filled order suspended",
        "SUSPENDED->WORKING": "Order resumed from suspension",
        "SUSPENDED->CANCELLED": "Suspended order cancelled",
        "SUSPENDED->EXPIRED": "Suspended order expired",
    }

    def __init__(self) -> None:
        self._transitions: dict[LifecycleStatus, FrozenSet[LifecycleStatus]] = dict(
            self.DEFAULT_TRANSITIONS
        )

    # ---- Core Validation ----

    def can_transition(
        self, from_status: LifecycleStatus, to_status: LifecycleStatus
    ) -> bool:
        """Check if a transition is allowed.

        Args:
            from_status: Current status
            to_status: Desired target status

        Returns:
            True if the transition is valid
        """
        allowed = self._transitions.get(from_status, frozenset())
        return to_status in allowed

    def validate(
        self,
        order_id: str,
        from_status: LifecycleStatus,
        to_status: LifecycleStatus,
    ) -> TransitionValidation:
        """Validate a transition with detailed result.

        Args:
            order_id: Order identifier
            from_status: Current order status
            to_status: Desired target status

        Returns:
            TransitionValidation with validity and reason
        """
        if from_status == to_status and to_status != LifecycleStatus.PARTIALLY_FILLED:
            return TransitionValidation(
                order_id=order_id,
                from_status=from_status,
                to_status=to_status,
                is_valid=False,
                reason=f"Same-state transition not allowed for {to_status.value}",
            )

        if self.can_transition(from_status, to_status):
            return TransitionValidation(
                order_id=order_id,
                from_status=from_status,
                to_status=to_status,
                is_valid=True,
                reason=self.get_description(from_status, to_status),
            )

        allowed = self.get_allowed_transitions(from_status)
        return TransitionValidation(
            order_id=order_id,
            from_status=from_status,
            to_status=to_status,
            is_valid=False,
            reason=(
                f"Transition {from_status.value} -> {to_status.value} not allowed. "
                f"Valid targets from {from_status.value}: "
                f"{[s.value for s in allowed]}"
            ),
        )

    def validate_or_raise(
        self,
        order_id: str,
        from_status: LifecycleStatus,
        to_status: LifecycleStatus,
    ) -> None:
        """Validate a transition, raising on invalid.

        Args:
            order_id: Order identifier
            from_status: Current order status
            to_status: Desired target status

        Raises:
            InvalidTransitionError: If transition is not allowed
        """
        if not self.can_transition(from_status, to_status):
            raise InvalidTransitionError(from_status, to_status, order_id)

    # ---- Query Methods ----

    def get_allowed_transitions(
        self, status: LifecycleStatus
    ) -> set[LifecycleStatus]:
        """Get all valid next states from a given status.

        Args:
            status: Current lifecycle status

        Returns:
            Set of allowed next status values
        """
        return set(self._transitions.get(status, frozenset()))

    def get_description(
        self, from_status: LifecycleStatus, to_status: LifecycleStatus
    ) -> str:
        """Get a human-readable description of a transition.

        Args:
            from_status: Source status
            to_status: Target status

        Returns:
            Human-readable transition description
        """
        key = f"{from_status.value}->{to_status.value}"
        return self.TRANSITION_DESCRIPTIONS.get(
            key, f"Transition: {from_status.value} -> {to_status.value}"
        )

    def is_terminal(self, status: LifecycleStatus) -> bool:
        """Check if a status is terminal.

        Args:
            status: Lifecycle status to check

        Returns:
            True if no further transitions are allowed
        """
        return len(self._transitions.get(status, frozenset())) == 0

    def is_active(self, status: LifecycleStatus) -> bool:
        """Check if a status represents an active order.

        Args:
            status: Lifecycle status to check

        Returns:
            True if the order is active in the market
        """
        return status.is_active

    # ---- Dynamic Extension ----

    def add_transition(
        self, from_status: LifecycleStatus, to_status: LifecycleStatus
    ) -> None:
        """Dynamically add a valid transition.

        Args:
            from_status: Source status
            to_status: Target status
        """
        current = set(self._transitions.get(from_status, frozenset()))
        current.add(to_status)
        self._transitions[from_status] = frozenset(current)
        logger.info(
            f"Added transition: {from_status.value} -> {to_status.value}"
        )

    def remove_transition(
        self, from_status: LifecycleStatus, to_status: LifecycleStatus
    ) -> None:
        """Dynamically remove a valid transition.

        Args:
            from_status: Source status
            to_status: Target status
        """
        current = set(self._transitions.get(from_status, frozenset()))
        current.discard(to_status)
        self._transitions[from_status] = frozenset(current)
        logger.info(
            f"Removed transition: {from_status.value} -> {to_status.value}"
        )

    def add_state(
        self,
        status: LifecycleStatus,
        allowed_targets: Optional[set[LifecycleStatus]] = None,
    ) -> None:
        """Dynamically add a new state with its allowed transitions.

        Args:
            status: New lifecycle status
            allowed_targets: Set of valid target states from this state
        """
        self._transitions[status] = frozenset(allowed_targets or set())
        logger.info(f"Added state: {status.value}")

    def enable_recovery_mode(self) -> None:
        """Enable recovery mode — allows all transitions for recovery.

        Warning: Only enable during recovery operations.
        """
        self._recovery_transitions_backup = dict(self._transitions)
        for status in LifecycleStatus:
            all_others = {s for s in LifecycleStatus if s != status}
            self._transitions[status] = frozenset(all_others)
        logger.info("Recovery mode enabled — all transitions allowed")

    def disable_recovery_mode(self) -> None:
        """Disable recovery mode — restore original transition rules."""
        if hasattr(self, "_recovery_transitions_backup"):
            self._transitions = self._recovery_transitions_backup
            del self._recovery_transitions_backup
            logger.info("Recovery mode disabled — original rules restored")

    def to_dict(self) -> dict[str, Any]:
        """Serialize transition rules."""
        return {
            status.value: [s.value for s in targets]
            for status, targets in self._transitions.items()
        }
