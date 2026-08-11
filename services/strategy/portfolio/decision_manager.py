"""
Decision Manager
================
Central coordinator for the portfolio decision subsystem.
Manages event bus, subsystem registry, and configuration lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ManagerEventType(str, Enum):
    """Types of manager events."""

    SUBSYSTEM_REGISTERED = "subsystem_registered"
    SUBSYSTEM_UNREGISTERED = "subsystem_unregistered"
    CONFIG_UPDATED = "config_updated"
    DECISION_CREATED = "decision_created"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    INTENT_BUILT = "intent_built"
    INTENT_ROUTED = "intent_routed"
    ERROR = "error"


@dataclass
class ManagerEvent:
    """An event emitted by the Decision Manager."""

    event_id: str = field(default_factory=lambda: f"me_{uuid4().hex[:8]}")
    event_type: ManagerEventType = ManagerEventType.DECISION_CREATED
    source: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


EventHandler = Callable[[ManagerEvent], Any]


@dataclass
class SubsystemInfo:
    """Information about a registered subsystem."""

    name: str
    version: str = "0.1.0"
    status: str = "initialized"
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionManager:
    """
    Central coordinator for the portfolio decision subsystem.

    Responsibilities:
    - Subsystem registry (position sizing, capital allocation, etc.)
    - Event bus for inter-subsystem communication
    - Configuration management and hot-reload
    - Lifecycle orchestration
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Subsystem registry
        self._subsystems: Dict[str, SubsystemInfo] = {}

        # Event bus
        self._handlers: Dict[ManagerEventType, List[EventHandler]] = {}
        self._event_history: List[ManagerEvent] = []
        self._max_event_history = config.get("max_event_history", 1000) if config else 1000

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("DecisionManager initialized")

    async def shutdown(self) -> None:
        self._subsystems.clear()
        for handlers in self._handlers.values():
            handlers.clear()
        self._handlers.clear()
        self._initialized = False
        logger.info("DecisionManager shut down")

    # ------------------------------------------------------------------
    # Subsystem Registry
    # ------------------------------------------------------------------

    def register_subsystem(self, name: str, version: str = "0.1.0", **metadata: Any) -> None:
        """Register a subsystem with the manager."""
        info = SubsystemInfo(name=name, version=version, metadata=metadata)
        self._subsystems[name] = info
        self._emit(ManagerEventType.SUBSYSTEM_REGISTERED, source="manager", payload=info.__dict__)
        logger.info("Subsystem registered: %s v%s", name, version)

    def unregister_subsystem(self, name: str) -> None:
        """Unregister a subsystem."""
        if name in self._subsystems:
            del self._subsystems[name]
            self._emit(ManagerEventType.SUBSYSTEM_UNREGISTERED, source="manager", payload={"name": name})
            logger.info("Subsystem unregistered: %s", name)

    def get_subsystem(self, name: str) -> Optional[SubsystemInfo]:
        return self._subsystems.get(name)

    def list_subsystems(self) -> List[SubsystemInfo]:
        return list(self._subsystems.values())

    # ------------------------------------------------------------------
    # Event Bus
    # ------------------------------------------------------------------

    def subscribe(self, event_type: ManagerEventType, handler: EventHandler) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed to %s", event_type.value)

    def unsubscribe(self, event_type: ManagerEventType, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h is not handler]

    def _emit(self, event_type: ManagerEventType, source: str = "", **payload: Any) -> ManagerEvent:
        """Emit an event to all registered handlers."""
        event = ManagerEvent(event_type=event_type, source=source, payload=payload)

        # Store in history (with cap)
        self._event_history.append(event)
        if len(self._event_history) > self._max_event_history:
            self._event_history = self._event_history[-self._max_event_history:]

        # Dispatch to handlers
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Handler error for event %s", event_type.value)

        # Increment metric
        key = f"event_{event_type.value}"
        self._metrics[key] = self._metrics.get(key, 0) + 1

        return event

    async def emit(self, event_type: ManagerEventType, source: str = "", **payload: Any) -> ManagerEvent:
        """Async emit for handlers that need async dispatch."""
        return self._emit(event_type, source=source, **payload)

    def get_event_history(self, event_type: Optional[ManagerEventType] = None, limit: int = 100) -> List[ManagerEvent]:
        """Get recent events, optionally filtered by type."""
        history = self._event_history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Hot-reload configuration."""
        self._config.update(new_config)
        self._emit(ManagerEventType.CONFIG_UPDATED, source="manager", payload={"keys": list(new_config.keys())})
        logger.info("Configuration updated: %d keys", len(new_config))

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
