"""
Standard event envelope.

Defines the unified event format for
all ICYQuant event-driven communications,
supporting versioning and correlation tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4


@dataclass
class EventEnvelope:
    """
    Standard event envelope.

    All events flowing through the ICYQuant
    EventBus are wrapped in this envelope,
    providing consistent metadata for tracing,
    versioning, and correlation.

    Attributes:
        event_id: Unique event identifier (UUID).
        event_type: Domain event type (e.g., OrderCreated).
        version: Event schema version.
        source: Service that produced the event.
        timestamp: ISO-8601 creation timestamp.
        correlation_id: Correlation ID for request tracing.
        payload: Event data dictionary.
    """

    event_id: str = ""

    event_type: str = ""

    version: int = 1

    source: str = ""

    timestamp: str = ""

    correlation_id: str = ""

    payload: Dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: Dict[str, Any],
        source: str,
        correlation_id: str = "",
    ) -> EventEnvelope:
        """
        Create a new event envelope.

        Generates a unique event ID and
        records the current timestamp.

        Args:
            event_type: Domain event type name.
            payload: Event data dictionary.
            source: Producer service name.
            correlation_id: Optional correlation ID.

        Returns:
            New EventEnvelope instance.
        """

        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            version=1,
            source=source,
            timestamp=datetime.utcnow().isoformat(),
            correlation_id=correlation_id
            or str(uuid4()),
            payload=payload,
        )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Serialize envelope to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "version": self.version,
            "source": self.source,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
    ) -> EventEnvelope:
        """
        Create envelope from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            EventEnvelope instance.
        """

        return cls(
            event_id=data.get(
                "event_id", ""
            ),
            event_type=data.get(
                "event_type", ""
            ),
            version=data.get(
                "version", 1
            ),
            source=data.get(
                "source", ""
            ),
            timestamp=data.get(
                "timestamp", ""
            ),
            correlation_id=data.get(
                "correlation_id", ""
            ),
            payload=data.get(
                "payload", {}
            ),
        )
