"""
Policy Action — actions triggered by policy rule evaluation.

For structured effect outcomes with severity and aggregation, see:
policy_effect.py which provides PolicyEffect, EffectType, AggregatedEffects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class PolicyActionType(Enum):
    """Types of actions triggered by policy evaluation."""

    ALLOW = auto()
    WARN = auto()
    NOTIFY = auto()
    REQUIRE_REVIEW = auto()
    REDUCE_SCOPE = auto()
    FREEZE_NEW = auto()
    REDUCE_EXPOSURE = auto()
    REBALANCE = auto()
    BLOCK = auto()
    ESCALATE = auto()
    EMERGENCY_EXIT = auto()
    CUSTOM = auto()


@dataclass
class PolicyAction:
    """A concrete action triggered when a policy rule is breached."""

    action_id: str = ""
    action_type: PolicyActionType = PolicyActionType.WARN
    target: str = ""           # Target component/strategy
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    description: str = ""

    @classmethod
    def allow(cls, **kwargs) -> "PolicyAction":
        return cls(action_type=PolicyActionType.ALLOW, **kwargs)

    @classmethod
    def warn(cls, message: str, **kwargs) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType.WARN,
            description=message,
            **kwargs,
        )

    @classmethod
    def block(cls, reason: str, **kwargs) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType.BLOCK,
            description=reason,
            **kwargs,
        )

    @classmethod
    def require_review(cls, reason: str, **kwargs) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType.REQUIRE_REVIEW,
            description=reason,
            **kwargs,
        )

    @classmethod
    def reduce_scope(cls, max_amount: float, **kwargs) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType.REDUCE_SCOPE,
            parameters={"max_amount": max_amount},
            **kwargs,
        )

    @classmethod
    def freeze_new(cls, **kwargs) -> "PolicyAction":
        return cls(action_type=PolicyActionType.FREEZE_NEW, **kwargs)

    @classmethod
    def emergency_exit(cls, reason: str, **kwargs) -> "PolicyAction":
        return cls(
            action_type=PolicyActionType.EMERGENCY_EXIT,
            description=reason,
            **kwargs,
        )

    def is_blocking(self) -> bool:
        return self.action_type in (
            PolicyActionType.BLOCK,
            PolicyActionType.FREEZE_NEW,
            PolicyActionType.EMERGENCY_EXIT,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.name,
            "target": self.target,
            "parameters": self.parameters,
            "priority": self.priority,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyAction":
        return cls(
            action_id=data.get("action_id", ""),
            action_type=PolicyActionType[data.get("action_type", "WARN")],
            target=data.get("target", ""),
            parameters=data.get("parameters", {}),
            priority=data.get("priority", 0),
            description=data.get("description", ""),
        )
