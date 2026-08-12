"""
Action executors — the execution side of the Policy Engine.

The Policy Engine only *requests* actions (see ``policy.policy_action``).
Each executor translates a :class:`PolicyAction` into an
:class:`ActionRequest` that the owning subsystem can consume:

    ALLOW_TRADING          → Trading Gate / OMS
    BLOCK_TRADING          → Trading Gate / OMS
    DEGRADE_TRADING        → Trading Gate / OMS
    HALT_TRADING           → Trading Gate / OMS
    ACTIVATE_KILL_SWITCH   → Kill Switch
    START_RECOVERY         → Recovery Engine

Policy ≠ Execution: executors never mutate state themselves — they produce
requests and hand them over.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..policy.policy_action import PolicyAction, PolicyActionType
from ..policy.policy_context import PolicyContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ActionRequest:
    """A requested action handed to the owning subsystem."""

    def __init__(
        self,
        action_type: PolicyActionType,
        target: str = "",
        status: str = "REQUESTED",
        detail: str = "",
        correlation_id: str = "",
        requested_at: Optional[datetime] = None,
    ) -> None:
        self.action_type = action_type
        self.target = target
        self.status = status
        self.detail = detail
        self.correlation_id = correlation_id
        self.requested_at = requested_at or _utcnow()

    @property
    def accepted(self) -> bool:
        return self.status == "REQUESTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "status": self.status,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
            "requested_at": self.requested_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRequest":
        return cls(
            action_type=PolicyActionType(data["action_type"]),
            target=data.get("target", ""),
            status=data.get("status", "REQUESTED"),
            detail=data.get("detail", ""),
            correlation_id=data.get("correlation_id", ""),
            requested_at=datetime.fromisoformat(data["requested_at"]),
        )


class ActionExecutor(ABC):
    """Base class for a single action executor."""

    action_type: PolicyActionType

    @abstractmethod
    def execute(
        self, action: PolicyAction, context: PolicyContext
    ) -> ActionRequest:
        """Translate a requested action into an ActionRequest."""
        raise NotImplementedError


#: All built-in executor classes, keyed by PolicyActionType.
EXECUTOR_TYPES: Dict[PolicyActionType, type] = {}


def register_executor(executor_cls: type) -> type:
    """Register an executor class under its ``action_type`` (decorator)."""
    action_type = executor_cls.action_type
    if action_type in EXECUTOR_TYPES:
        raise ValueError(f"executor already registered for {action_type.value}")
    EXECUTOR_TYPES[action_type] = executor_cls
    return executor_cls


def get_executor(action_type: PolicyActionType) -> ActionExecutor:
    """Return an executor instance for ``action_type`` (lazy import)."""
    if action_type not in EXECUTOR_TYPES:
        # lazy import to avoid a circular import at package init
        _import_executors()
    executor_cls = EXECUTOR_TYPES.get(action_type)
    if executor_cls is None:
        raise ValueError(f"no executor registered for {action_type.value}")
    return executor_cls()


def _import_executors() -> None:
    from . import (  # noqa: F401  (import side-effect registers executors)
        activate_kill_switch,
        allow_trading,
        block_trading,
        degrade_trading,
        halt_trading,
        start_recovery,
    )


__all__ = [
    "ActionRequest",
    "ActionExecutor",
    "EXECUTOR_TYPES",
    "register_executor",
    "get_executor",
]
