"""
Event Registry — central mapping from event type to contract,
deserializer, and consumer list.

Responsibilities
----------------
1. Look up the canonical EventContract for a given event_type + version.
2. Resolve which deserializer to use for a raw payload.
3. Return the set of consumer groups registered for an event type.

This registry eliminates scattered ``if event.type == ...`` logic
across the project.  All routing decisions flow through one place.

Architecture:

    Event Type
        |
        v
    Event Registry
        |
        +---> EventContract (schema, producer)
        +---> Deserializer   (payload → domain object)
        +---> Consumers      (who should handle this)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple

from services.integration.event_contract import (
    ALL_CONTRACTS,
    EventContract,
)
from services.integration.event_envelope import EventEnvelope

logger = logging.getLogger(__name__)

# Type alias for a deserializer callable.
Deserializer = Callable[[Mapping[str, Any]], Any]
"""Takes raw payload dict, returns a typed domain event object."""


@dataclass
class RegistryEntry:
    """A single entry in the Event Registry."""

    contract: EventContract
    deserializer: Optional[Deserializer] = None
    consumer_groups: FrozenSet[str] = field(default_factory=frozenset)

    @property
    def event_type(self) -> str:
        return self.contract.event_type

    @property
    def version(self) -> int:
        return self.contract.version


class EventRegistry:
    """
    Thread-safe registry of all event types flowing through the bus.

    Usage::

        registry = EventRegistry()
        registry.register_defaults()

        envelope = registry.deserialize("ORDER_FILLED", 1, raw_payload)
        consumers = registry.consumers_for("ORDER_FILLED")
    """

    def __init__(self) -> None:
        # Key: (event_type, version)
        self._entries: Dict[Tuple[str, int], RegistryEntry] = {}

    # ── registration ──────────────────────────────────────────────────

    def register(
        self,
        contract: EventContract,
        deserializer: Optional[Deserializer] = None,
        consumer_groups: Optional[FrozenSet[str]] = None,
    ) -> None:
        """Register (or replace) an event type."""
        key = (contract.event_type, contract.version)
        consumers = consumer_groups or contract.consumers or frozenset()
        self._entries[key] = RegistryEntry(
            contract=contract,
            deserializer=deserializer,
            consumer_groups=consumers,
        )
        logger.debug("Registered event: %s v%d", contract.event_type, contract.version)

    def register_defaults(self) -> None:
        """Register all canonical contracts from event_contract.py."""
        for contract in ALL_CONTRACTS:
            self.register(contract)

    # ── lookup ────────────────────────────────────────────────────────

    def get_contract(self, event_type: str, version: int = 1) -> EventContract:
        """Return the contract for an event type (or raise KeyError)."""
        key = (event_type, version)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(f"Unknown event: {event_type} v{version}")
        return entry.contract

    def consumers_for(self, event_type: str, version: int = 1) -> FrozenSet[str]:
        """Return consumer groups registered for a given event type."""
        key = (event_type, version)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(f"Unknown event: {event_type} v{version}")
        return entry.consumer_groups

    def deserializer_for(
        self, event_type: str, version: int = 1
    ) -> Optional[Deserializer]:
        """Return the deserializer for an event type, if any."""
        key = (event_type, version)
        entry = self._entries.get(key)
        if entry is None:
            raise KeyError(f"Unknown event: {event_type} v{version}")
        return entry.deserializer

    def has_event(self, event_type: str, version: int = 1) -> bool:
        """Check if an event type is registered."""
        return (event_type, version) in self._entries

    # ── deserialization ───────────────────────────────────────────────

    def deserialize(
        self, event_type: str, version: int, payload: Mapping[str, Any]
    ) -> Any:
        """Deserialize a raw payload into a typed domain event."""
        deserializer = self.deserializer_for(event_type, version)
        if deserializer is not None:
            return deserializer(payload)
        # Fallback: return raw dict
        return dict(payload)

    # ── listing ───────────────────────────────────────────────────────

    def list_event_types(self) -> List[str]:
        """Return all registered event type names (unique)."""
        return sorted({t for (t, _) in self._entries.keys()})

    def list_all(self) -> List[Tuple[str, int, str, FrozenSet[str]]]:
        """Return [(event_type, version, producer, consumers), ...]."""
        return [
            (k[0], k[1], e.contract.producer, e.consumer_groups)
            for k, e in self._entries.items()
        ]

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, item: Tuple[str, int]) -> bool:
        return item in self._entries
