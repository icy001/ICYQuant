"""CommandMetadata — context attached to every command."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class CommandMetadata:
    """Metadata for a command — actor, source, correlation, causation.

    Fields:
        command_id: Unique ID for this command (for idempotency).
        actor_type: Type of actor (STRATEGY, OMS, EXECUTION, etc.)
        actor_id: ID of the actor.
        source: Source service/module.
        correlation_id: Business flow ID.
        causation_id: ID of the event that caused this command.
        timestamp: When the command was created.
        request_id: External request ID for tracing.
    """

    command_id: str = field(
        default_factory=lambda: f"CMD-{__import__('uuid').uuid4().hex[:12].upper()}"
    )
    actor_type: str = "SYSTEM"
    actor_id: str = "system"
    source: str = "oms"
    correlation_id: str = ""
    causation_id: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    request_id: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_system(cls, source: str = "oms",
                   correlation_id: str = "") -> "CommandMetadata":
        return cls(actor_type="SYSTEM", actor_id="system",
                   source=source, correlation_id=correlation_id)

    @classmethod
    def for_strategy(cls, strategy_id: str,
                     correlation_id: str = "") -> "CommandMetadata":
        return cls(actor_type="STRATEGY", actor_id=strategy_id,
                   source="strategy-service",
                   correlation_id=correlation_id)

    @classmethod
    def for_execution(cls, execution_id: str,
                      correlation_id: str = "",
                      causation_id: str = "") -> "CommandMetadata":
        return cls(actor_type="EXECUTION", actor_id=execution_id,
                   source="execution-service",
                   correlation_id=correlation_id,
                   causation_id=causation_id or execution_id)

    @classmethod
    def for_operator(cls, operator_id: str,
                     correlation_id: str = "") -> "CommandMetadata":
        return cls(actor_type="OPERATOR", actor_id=operator_id,
                   source="admin-console",
                   correlation_id=correlation_id)

    @classmethod
    def for_recovery(cls, correlation_id: str = "") -> "CommandMetadata":
        return cls(actor_type="RECOVERY", actor_id="recovery-service",
                   source="recovery-service",
                   correlation_id=correlation_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "extra": dict(self.extra),
        }
