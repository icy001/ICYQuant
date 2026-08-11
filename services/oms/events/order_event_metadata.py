"""OrderEventMetadata — actor, source, correlation, causation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class OrderEventMetadata:
    """Metadata attached to every order event.

    Fields:
        actor_type: Type of actor (SYSTEM, SERVICE, USER, STRATEGY,
                    RISK_ENGINE, OMS, EXECUTION_ENGINE, etc.)
        actor_id:   ID of the actor.
        source:     Source service/module that produced the event.
        correlation_id: Business flow ID (links events in the same flow).
        causation_id:   ID of the event that caused this event.
        request_id:     Request ID for tracing.
    """

    actor_type: str = ""
    actor_id: str = ""
    source: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    request_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_system(cls, source: str = "oms") -> "OrderEventMetadata":
        return cls(actor_type="SYSTEM", actor_id="system", source=source)

    @classmethod
    def for_service(cls, actor_id: str, source: str = "",
                    correlation_id: str = "",
                    causation_id: str = "") -> "OrderEventMetadata":
        return cls(
            actor_type="SERVICE",
            actor_id=actor_id,
            source=source or actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

    @classmethod
    def for_execution(cls, execution_id: str,
                      correlation_id: str = "") -> "OrderEventMetadata":
        return cls(
            actor_type="EXECUTION_ENGINE",
            actor_id=execution_id,
            source="execution-service",
            correlation_id=correlation_id,
            causation_id=execution_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "request_id": self.request_id,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OrderEventMetadata":
        return cls(
            actor_type=d.get("actor_type", ""),
            actor_id=d.get("actor_id", ""),
            source=d.get("source", ""),
            correlation_id=d.get("correlation_id", ""),
            causation_id=d.get("causation_id", ""),
            request_id=d.get("request_id", ""),
            extra=dict(d.get("extra", {})),
        )
