"""
Audit Actor — unified actor attribution for all governance audit events.

Every audit event must answer: WHO did this?
Actor types are clearly categorized and cannot be generalized to "SYSTEM".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class ActorType(Enum):
    """Precise categorization of actors in the governance system."""

    HUMAN = auto()
    SERVICE = auto()
    STRATEGY = auto()
    AI_AGENT = auto()
    SYSTEM = auto()
    EMERGENCY_CONTROLLER = auto()
    GOVERNANCE_ADMIN = auto()

    @classmethod
    def from_string(cls, s: str) -> "ActorType":
        try:
            return cls[s.upper()]
        except KeyError:
            return cls.SERVICE


@dataclass
class AuditActor:
    """Fully attributed actor for audit events.

    Never just: actor = "SYSTEM"
    Always: actor, actor_type, service, version, session, authority
    """

    actor_id: str
    actor_type: ActorType = ActorType.SERVICE
    display_name: str = ""

    # Attribution detail
    service: str = ""            # e.g. "allocation-service"
    service_version: str = ""    # e.g. "0.4.0-alpha2"
    session_id: str = ""         # bounded session for traceability

    # Authority context
    authority_id: str = ""       # e.g. "AUTH-001"
    delegation_id: str = ""      # if acting via delegation
    policy_version: str = ""     # policy version active at time

    # Timing
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_type": self.actor_type.name,
            "display_name": self.display_name or self.actor_id,
            "service": self.service,
            "service_version": self.service_version,
            "session_id": self.session_id,
            "authority_id": self.authority_id,
            "delegation_id": self.delegation_id,
            "policy_version": self.policy_version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditActor":
        actor_type = data.get("actor_type", "SERVICE")
        if isinstance(actor_type, str):
            actor_type = ActorType.from_string(actor_type)
        return cls(
            actor_id=data.get("actor_id", ""),
            actor_type=actor_type,
            display_name=data.get("display_name", ""),
            service=data.get("service", ""),
            service_version=data.get("service_version", ""),
            session_id=data.get("session_id", ""),
            authority_id=data.get("authority_id", ""),
            delegation_id=data.get("delegation_id", ""),
            policy_version=data.get("policy_version", ""),
            created_at=data.get("created_at", time.time()),
        )

    # ── Factory Methods ──

    @classmethod
    def human(cls, user_id: str, display_name: str = "",
              authority_id: str = "") -> "AuditActor":
        return cls(
            actor_id=user_id,
            actor_type=ActorType.HUMAN,
            display_name=display_name or user_id,
            authority_id=authority_id,
        )

    @classmethod
    def strategy(cls, strategy_id: str, version: str = "") -> "AuditActor":
        return cls(
            actor_id=strategy_id,
            actor_type=ActorType.STRATEGY,
            display_name=strategy_id,
            service="strategy-service",
            service_version=version,
        )

    @classmethod
    def ai_agent(cls, agent_id: str, service: str = "",
                 version: str = "") -> "AuditActor":
        return cls(
            actor_id=agent_id,
            actor_type=ActorType.AI_AGENT,
            display_name=agent_id,
            service=service,
            service_version=version,
        )

    @classmethod
    def emergency_controller(cls, controller_id: str) -> "AuditActor":
        return cls(
            actor_id=controller_id,
            actor_type=ActorType.EMERGENCY_CONTROLLER,
            display_name=f"Emergency:{controller_id}",
        )

    @classmethod
    def system(cls, service_name: str, version: str = "") -> "AuditActor":
        return cls(
            actor_id=service_name,
            actor_type=ActorType.SYSTEM,
            display_name=service_name,
            service=service_name,
            service_version=version,
        )
