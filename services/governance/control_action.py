"""
Control Action — unified actions the control plane can take.

Part 1.5: defines ALLOW / WARN / RESTRICT / FREEZE / REDUCE / CANCEL /
REVOKE / PAUSE / ESCALATE / EMERGENCY / RECOVER actions.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict


class ControlActionType(Enum):
    """Unified control actions for the autonomous governance control plane."""

    ALLOW = auto()
    WARN = auto()
    RESTRICT = auto()
    FREEZE = auto()
    REDUCE = auto()
    CANCEL = auto()
    REVOKE = auto()
    PAUSE = auto()
    ESCALATE = auto()
    EMERGENCY = auto()
    RECOVER = auto()

    @property
    def label(self) -> str:
        labels = {
            ControlActionType.ALLOW: "Allow",
            ControlActionType.WARN: "Warn",
            ControlActionType.RESTRICT: "Restrict",
            ControlActionType.FREEZE: "Freeze",
            ControlActionType.REDUCE: "Reduce",
            ControlActionType.CANCEL: "Cancel",
            ControlActionType.REVOKE: "Revoke",
            ControlActionType.PAUSE: "Pause",
            ControlActionType.ESCALATE: "Escalate",
            ControlActionType.EMERGENCY: "Emergency",
            ControlActionType.RECOVER: "Recover",
        }
        return labels.get(self, "Unknown")

    @property
    def is_resource_safe(self) -> bool:
        """Actions that only reduce or maintain risk, never increase it."""
        return self in (
            ControlActionType.ALLOW,
            ControlActionType.WARN,
            ControlActionType.FREEZE,
            ControlActionType.REDUCE,
            ControlActionType.CANCEL,
            ControlActionType.PAUSE,
            ControlActionType.RECOVER,
        )

    @property
    def requires_audit(self) -> bool:
        """Actions that MUST be audited."""
        return self not in (ControlActionType.ALLOW,)

    @property
    def is_destructive(self) -> bool:
        """Actions that materially change system behavior."""
        return self in (
            ControlActionType.FREEZE,
            ControlActionType.CANCEL,
            ControlActionType.REVOKE,
            ControlActionType.EMERGENCY,
        )

    @property
    def severity_level(self) -> int:
        levels = {
            ControlActionType.ALLOW: 0,
            ControlActionType.RECOVER: 0,
            ControlActionType.WARN: 1,
            ControlActionType.RESTRICT: 2,
            ControlActionType.PAUSE: 3,
            ControlActionType.REDUCE: 3,
            ControlActionType.CANCEL: 4,
            ControlActionType.FREEZE: 4,
            ControlActionType.REVOKE: 5,
            ControlActionType.ESCALATE: 5,
            ControlActionType.EMERGENCY: 5,
        }
        return levels.get(self, 0)
