"""
Event Router — maps event types to consumer groups and manages
fan-out delivery.

The router is purely a routing concern; it knows which consumers
should receive which events but does NOT perform delivery itself.

Responsibilities
----------------
1. Given an event_type, return the set of consumer groups.
2. Support event-type → consumer-group routing tables.
3. Support dynamic consumer registration.

Architecture:

    event_type
        |
        v
    EventRouter
        |
        v
    [consumer_group_1, consumer_group_2, ...]
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, FrozenSet

from services.integration.event_registry import EventRegistry

logger = logging.getLogger(__name__)


class EventRouter:
    """
    Routes events to consumer groups.

    The router maintains an in-memory mapping of event types to
    their registered consumer groups.  It is backed by the
    EventRegistry for contract validation but adds dynamic
    registration capabilities.

    Usage::

        router = EventRouter(registry)
        router.register_consumer("ORDER_FILLED", "position-service")
        groups = router.route("ORDER_FILLED")
        # frozenset({"position-service", "ledger-service", ...})
    """

    def __init__(self, registry: EventRegistry) -> None:
        self._registry = registry
        # event_type -> consumer groups
        self._routing: Dict[str, set[str]] = defaultdict(set)

    # ── consumer registration ─────────────────────────────────────────

    def register_consumer(self, event_type: str, consumer_group: str) -> None:
        """Register a consumer group for an event type."""
        if not self._registry.has_event(event_type):
            raise KeyError(f"Cannot register consumer for unknown event: {event_type}")
        self._routing[event_type].add(consumer_group)
        logger.debug(
            "Registered consumer '%s' for event '%s'", consumer_group, event_type
        )

    def unregister_consumer(self, event_type: str, consumer_group: str) -> None:
        """Remove a consumer group from an event type."""
        if event_type in self._routing:
            self._routing[event_type].discard(consumer_group)

    def sync_from_registry(self) -> None:
        """Populate routing table from the EventRegistry contracts."""
        for event_type, version, producer, consumers in self._registry.list_all():
            for consumer in consumers:
                self._routing[event_type].add(consumer)

    # ── routing ───────────────────────────────────────────────────────

    def route(self, event_type: str, version: int = 1) -> FrozenSet[str]:
        """
        Return all consumer groups that should receive this event.

        Combines dynamic registrations with registry defaults.
        """
        groups: set[str] = set()

        # From dynamic registration
        if event_type in self._routing:
            groups.update(self._routing[event_type])

        # From registry contracts (as fallback / supplement)
        try:
            registry_groups = self._registry.consumers_for(event_type, version)
            groups.update(registry_groups)
        except KeyError:
            pass

        return frozenset(groups)

    def has_consumers(self, event_type: str) -> bool:
        """Check if any consumers are registered for this event type."""
        return len(self.route(event_type)) > 0

    # ── inspection ────────────────────────────────────────────────────

    def list_consumers(self) -> Dict[str, FrozenSet[str]]:
        """Return {event_type: consumer_groups} for all routed events."""
        return {et: frozenset(gs) for et, gs in self._routing.items()}
