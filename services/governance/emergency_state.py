"""
Emergency State — emergency governance state definitions.

Part 1.5: defines emergency states, transitions, and allowed actions
during emergency conditions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class EmergencyStateType(Enum):
    """Emergency state enumeration."""

    NONE = auto()           # No emergency
    DETECTED = auto()       # Emergency condition detected
    ACTIVATED = auto()      # Emergency actions active
    ESCALATED = auto()      # Escalated beyond automatic handling
    RESOLVING = auto()      # Emergency being resolved
    RESOLVED = auto()       # Emergency fully resolved

    @property
    def is_active(self) -> bool:
        return self in (
            EmergencyStateType.DETECTED,
            EmergencyStateType.ACTIVATED,
            EmergencyStateType.ESCALATED,
        )


@dataclass
class EmergencyState:
    """Current emergency governance state."""

    state: EmergencyStateType = EmergencyStateType.NONE
    trigger: str = ""
    description: str = ""
    activated_at: float = 0.0
    resolved_at: float = 0.0
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.state.is_active

    @property
    def duration_seconds(self) -> float:
        if self.activated_at <= 0:
            return 0.0
        end = self.resolved_at if self.resolved_at > 0 else time.time()
        return end - self.activated_at

    def activate(self, trigger: str, description: str, correlation_id: str = "") -> None:
        self.state = EmergencyStateType.ACTIVATED
        self.trigger = trigger
        self.description = description
        self.activated_at = time.time()
        self.correlation_id = correlation_id
        self.metadata["activated_at"] = self.activated_at

    def escalate(self, reason: str = "") -> None:
        self.state = EmergencyStateType.ESCALATED
        self.metadata["escalated_at"] = time.time()
        if reason:
            self.metadata["escalation_reason"] = reason

    def resolve(self) -> None:
        self.state = EmergencyStateType.RESOLVED
        self.resolved_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.name,
            "trigger": self.trigger,
            "description": self.description,
            "activated_at": self.activated_at,
            "resolved_at": self.resolved_at,
            "duration_seconds": self.duration_seconds,
            "correlation_id": self.correlation_id,
            "is_active": self.is_active,
        }
