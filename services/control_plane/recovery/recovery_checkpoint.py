"""
RecoveryCheckpoint — durable progress marker for resumable recovery.

A checkpoint is written after every successful step.  It records where the
recovery is (``step_id``), how far event replay got (``event_cursor``), which
ledger / position versions were produced, and a checksum over the payload so a
corrupted checkpoint is detected instead of silently resumed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING, Dict, Optional

from .recovery_step import RecoveryStep, StepType

if TYPE_CHECKING:
    from .recovery_plan import RecoveryPlan


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def compute_checksum(payload: Dict[str, Any]) -> str:
    """Stable checksum over a payload (sorted-key JSON + sha256)."""
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class RecoveryCheckpoint:
    """A durable progress marker for a recovery session."""

    recovery_id: str
    step_id: str
    step_type: StepType
    event_cursor: int = 0
    ledger_version: str = ""
    position_version: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    checksum: str = ""

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = _utcnow()
        if not self.checksum:
            self.checksum = compute_checksum(self.payload)

    # -- factories --------------------------------------------------------

    @classmethod
    def from_step(
        cls,
        recovery_id: str,
        step: RecoveryStep,
        output: Optional[Dict[str, Any]] = None,
    ) -> "RecoveryCheckpoint":
        data = dict(output or step.output)
        return cls(
            recovery_id=recovery_id,
            step_id=step.step_id,
            step_type=step.step_type,
            event_cursor=int(data.get("event_cursor", 0) or 0),
            ledger_version=str(data.get("ledger_version", "") or ""),
            position_version=str(data.get("position_version", "") or ""),
            payload=data,
        )

    @classmethod
    def from_plan(cls, plan: RecoveryPlan) -> "RecoveryCheckpoint":
        """Checkpoint at the plan's current step (used before starting it)."""
        step = plan.current_step()
        return cls(
            recovery_id=plan.recovery_id,
            step_id=step.step_id if step else "",
            step_type=step.step_type if step else StepType.FREEZE_STATE,
        )

    # -- integrity --------------------------------------------------------

    def verify(self) -> bool:
        """Whether the stored checksum still matches the payload."""
        return compute_checksum(self.payload) == self.checksum

    def update_payload(self, **values: Any) -> None:
        self.payload.update(values)
        self.checksum = compute_checksum(self.payload)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "step_id": self.step_id,
            "step_type": _enum_value(self.step_type),
            "event_cursor": self.event_cursor,
            "ledger_version": self.ledger_version,
            "position_version": self.position_version,
            "payload": dict(self.payload),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryCheckpoint":
        timestamp = data.get("timestamp")
        return cls(
            recovery_id=data["recovery_id"],
            step_id=data["step_id"],
            step_type=StepType(data["step_type"]),
            event_cursor=data.get("event_cursor", 0),
            ledger_version=data.get("ledger_version", ""),
            position_version=data.get("position_version", ""),
            payload=dict(data.get("payload", {})),
            timestamp=datetime.fromisoformat(timestamp) if timestamp else None,
            checksum=data.get("checksum", ""),
        )


__all__ = ["RecoveryCheckpoint", "compute_checksum"]
