"""RepairAction — actions that can be taken to repair order state."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict


class RepairActionType(Enum):
    """Types of repair actions."""

    NONE = auto()
    REPLAY_EXECUTION = auto()
    REBUILD_ORDER = auto()
    RELOAD_EXECUTION = auto()
    RETRY_QUERY = auto()
    FREEZE_ORDER = auto()
    ESCALATE = auto()

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def is_auto_repairable(self) -> bool:
        return self in (
            RepairActionType.REPLAY_EXECUTION,
            RepairActionType.REBUILD_ORDER,
            RepairActionType.RELOAD_EXECUTION,
            RepairActionType.RETRY_QUERY,
        )

    @property
    def requires_manual(self) -> bool:
        return self in (
            RepairActionType.FREEZE_ORDER,
            RepairActionType.ESCALATE,
        )


@dataclass
class RepairAction:
    """A repair action to be taken on an order."""

    action_id: str = field(
        default_factory=lambda: f"RP-{__import__('uuid').uuid4().hex[:8].upper()}"
    )
    order_id: str = ""
    action_type: RepairActionType = RepairActionType.NONE
    reason: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def none(cls, order_id: str) -> "RepairAction":
        return cls(order_id=order_id, action_type=RepairActionType.NONE)

    @classmethod
    def replay_execution(cls, order_id: str,
                         execution_id: str = "") -> "RepairAction":
        return cls(
            order_id=order_id,
            action_type=RepairActionType.REPLAY_EXECUTION,
            reason=f"Replay missing execution {execution_id}",
            metadata={"execution_id": execution_id},
        )

    @classmethod
    def rebuild_order(cls, order_id: str) -> "RepairAction":
        return cls(
            order_id=order_id,
            action_type=RepairActionType.REBUILD_ORDER,
            reason="Rebuild order from event store",
        )

    @classmethod
    def freeze_order(cls, order_id: str,
                     reason: str = "") -> "RepairAction":
        return cls(
            order_id=order_id,
            action_type=RepairActionType.FREEZE_ORDER,
            reason=reason or "Critical mismatch — order frozen",
        )

    @classmethod
    def escalate(cls, order_id: str,
                 reason: str = "") -> "RepairAction":
        return cls(
            order_id=order_id,
            action_type=RepairActionType.ESCALATE,
            reason=reason or "Critical mismatch — escalated for manual review",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "order_id": self.order_id,
            "action_type": self.action_type.name,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }
