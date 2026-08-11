"""
Event Consumer — base class for all cross-domain event consumers.

Each domain that receives events from the Event Bus implements
a consumer that processes envelopes and applies domain logic.

Key responsibilities:
- Receive EventEnvelope from the bus
- Validate contract
- Check idempotency (event_id)
- Check ordering (aggregate_version)
- Apply domain command
- Track consumption state

Architecture:

    Event Bus
        |
        v
    EventConsumer.on_envelope(envelope)
        |
        +-- validate (contract check)
        +-- idempotency check (event_id)
        +-- ordering check (aggregate_version)
        +-- handle (domain logic)
        +-- track success/failure
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set

from services.integration.event_contract import EventContract
from services.integration.event_envelope import (
    ConsistencyState,
    DeliveryState,
    EventEnvelope,
)
from services.integration.event_registry import EventRegistry

logger = logging.getLogger(__name__)


class EventSequenceGap(Exception):
    """Raised when a consumer detects a gap in the aggregate event sequence."""

    def __init__(self, aggregate_id: str, expected: int, received: int) -> None:
        self.aggregate_id = aggregate_id
        self.expected = expected
        self.received = received
        super().__init__(
            f"Sequence gap for aggregate {aggregate_id}: "
            f"expected v{expected}, received v{received}"
        )


class DuplicateEvent(Exception):
    """Raised when a consumer detects a duplicate event."""

    def __init__(self, event_id: str, consumer_group: str) -> None:
        self.event_id = event_id
        self.consumer_group = consumer_group
        super().__init__(
            f"Duplicate event {event_id} for consumer {consumer_group}"
        )


class EventConsumer(ABC):
    """
    Base class for domain event consumers.

    Subclasses must implement ``handle`` with domain-specific logic.

    Usage::

        class PositionExecutionConsumer(EventConsumer):
            def __init__(self, registry, group, position_service):
                super().__init__(registry, group)
                self._service = position_service

            def handle(self, envelope: EventEnvelope) -> None:
                # Apply fill to position
                ...
    """

    # Events this consumer is interested in.
    SUBSCRIBED_EVENTS: frozenset[str] = frozenset()

    def __init__(
        self,
        registry: EventRegistry,
        consumer_group: str,
    ) -> None:
        self._registry = registry
        self._consumer_group = consumer_group

        # Idempotency: track processed event_ids
        self._processed_events: Set[str] = set()

        # Ordering: track expected next version per aggregate
        self._aggregate_versions: Dict[str, int] = {}

        # Delivery tracking
        self._delivery_state: DefaultDict[str, DeliveryState] = defaultdict(
            lambda: DeliveryState.PENDING
        )

        # Consistency tracking per aggregate
        self._consistency_state: Dict[str, ConsistencyState] = {}

        # Failed events with retry count
        self._failed_events: Dict[str, int] = {}
        self._dead_letters: Set[str] = set()

        # Max retries before dead-letter
        self._max_retries = 3

        # Lag tracking
        self._last_sequence: int = 0
        self._published_sequence: int = 0

    # ── public entry point ────────────────────────────────────────────

    def on_envelope(self, envelope: EventEnvelope) -> None:
        """
        Process an incoming envelope from the Event Bus.

        Flow:
        1. Validate contract
        2. Check idempotency
        3. Check ordering
        4. Handle domain logic
        5. Track completion
        """
        event_id = envelope.event_id
        event_type = envelope.event_type

        # Skip if not subscribed
        if self.SUBSCRIBED_EVENTS and event_type not in self.SUBSCRIBED_EVENTS:
            logger.debug(
                "Consumer '%s' skipping event '%s' (not subscribed)",
                self._consumer_group,
                event_type,
            )
            return

        # Validate contract
        self._validate_envelope(envelope)

        # Idempotency guard
        if not self._check_idempotency(event_id):
            logger.info(
                "Consumer '%s' skipping duplicate event %s",
                self._consumer_group,
                event_id,
            )
            return

        # Ordering guard
        self._check_ordering(envelope)

        # Process
        try:
            self.handle(envelope)
            self._mark_delivered(event_id)
            self._aggregate_versions[envelope.aggregate_id] = (
                envelope.aggregate_version + 1
            )
            self._consistency_state[envelope.aggregate_id] = ConsistencyState.SYNCED
            self._last_sequence += 1
            logger.info(
                "Consumer '%s' processed event %s type=%s",
                self._consumer_group,
                event_id,
                event_type,
            )
        except Exception as exc:
            self._handle_failure(envelope, exc)

    # ── abstract handler ──────────────────────────────────────────────

    @abstractmethod
    def handle(self, envelope: EventEnvelope) -> None:
        """
        Apply domain logic for this event.

        Subclasses implement domain-specific behavior here.
        """

    # ── validation ────────────────────────────────────────────────────

    def _validate_envelope(self, envelope: EventEnvelope) -> None:
        """Validate the envelope against its registered contract."""
        try:
            contract = self._registry.get_contract(
                envelope.event_type, envelope.event_version
            )
            contract.validate_payload(envelope.payload)
        except KeyError:
            logger.warning(
                "No contract for event '%s' v%d — skipping validation",
                envelope.event_type,
                envelope.event_version,
            )
        except ValueError as exc:
            logger.error("Contract validation failed for %s: %s", envelope.event_id, exc)
            raise

    # ── idempotency ───────────────────────────────────────────────────

    def _check_idempotency(self, event_id: str) -> bool:
        """Return True if event_id has NOT been processed yet."""
        if event_id in self._processed_events:
            return False
        if event_id in self._dead_letters:
            return False
        return True

    def _mark_processed(self, event_id: str) -> None:
        """Mark an event as processed (for idempotency)."""
        self._processed_events.add(event_id)

    def _mark_delivered(self, event_id: str) -> None:
        """Mark event as successfully delivered and processed."""
        self._mark_processed(event_id)
        self._delivery_state[event_id] = DeliveryState.DELIVERED

    # ── ordering ──────────────────────────────────────────────────────

    def _check_ordering(self, envelope: EventEnvelope) -> None:
        """Verify aggregate version ordering; raise EventSequenceGap if gap detected."""
        aggregate_id = envelope.aggregate_id
        expected = self._aggregate_versions.get(aggregate_id, 1)

        if envelope.aggregate_version < expected:
            # Already seen — idempotency should have caught this
            logger.debug(
                "Event %s version %d < expected %d for aggregate %s",
                envelope.event_id,
                envelope.aggregate_version,
                expected,
                aggregate_id,
            )
        elif envelope.aggregate_version > expected:
            self._consistency_state[aggregate_id] = ConsistencyState.LAGGING
            raise EventSequenceGap(
                aggregate_id=aggregate_id,
                expected=expected,
                received=envelope.aggregate_version,
            )

    # ── failure handling ──────────────────────────────────────────────

    def _handle_failure(self, envelope: EventEnvelope, exc: Exception) -> None:
        """Track failure and decide whether to retry or dead-letter."""
        event_id = envelope.event_id
        attempts = self._failed_events.get(event_id, 0) + 1
        self._failed_events[event_id] = attempts

        if attempts > self._max_retries:
            self._delivery_state[event_id] = DeliveryState.DEAD_LETTER
            self._dead_letters.add(event_id)
            logger.critical(
                "Event %s moved to DEAD_LETTER after %d attempts: %s",
                event_id,
                attempts,
                exc,
            )
        else:
            self._delivery_state[event_id] = DeliveryState.RETRYING
            logger.warning(
                "Event %s failed (attempt %d/%d): %s",
                event_id,
                attempts,
                self._max_retries,
                exc,
            )
            raise

    # ── state inspection ──────────────────────────────────────────────

    @property
    def consumer_group(self) -> str:
        return self._consumer_group

    @property
    def processed_count(self) -> int:
        return len(self._processed_events)

    @property
    def failed_count(self) -> int:
        return len(self._failed_events)

    @property
    def dead_letter_count(self) -> int:
        return len(self._dead_letters)

    @property
    def lag(self) -> int:
        """Current consumer lag (published_sequence - last_sequence)."""
        return max(0, self._published_sequence - self._last_sequence)

    def update_published_sequence(self, sequence: int) -> None:
        """Update the latest published sequence (from bus metadata)."""
        self._published_sequence = sequence

    def get_consistency_state(self, aggregate_id: str) -> ConsistencyState:
        """Return the consistency state for an aggregate."""
        return self._consistency_state.get(aggregate_id, ConsistencyState.SYNCED)

    def get_delivery_state(self, event_id: str) -> DeliveryState:
        """Return the delivery state for a specific event."""
        return self._delivery_state.get(event_id, DeliveryState.PENDING)

    def get_aggregate_version(self, aggregate_id: str) -> int:
        """Return the next expected version for an aggregate."""
        return self._aggregate_versions.get(aggregate_id, 1)
