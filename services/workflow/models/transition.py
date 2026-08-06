"""Transition definition model — state transitions between execution phases."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


class TransitionType(str, enum.Enum):
    """Types of execution transitions."""

    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"
    RETRY = "retry"
    SKIP = "skip"
    CANCEL = "cancel"
    TIMEOUT = "timeout"
    RESUME = "resume"
    PAUSE = "pause"


class TransitionCondition(str, enum.Enum):
    """Conditions that trigger transitions."""

    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    ON_TIMEOUT = "on_timeout"
    ON_RETRY_EXHAUSTED = "on_retry_exhausted"
    ON_CONDITION_MET = "on_condition_met"
    ALWAYS = "always"


@dataclass(frozen=True)
class TransitionDefinition:
    """Immutable transition definition."""

    transition_id: str
    from_state: str
    to_state: str
    transition_type: TransitionType = TransitionType.COMPLETE
    condition: Optional[TransitionCondition] = None
    condition_expression: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "transition_type": self.transition_type.value,
            "condition": self.condition.value if self.condition else None,
            "condition_expression": self.condition_expression,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"TransitionDefinition(id={self.transition_id!r}, "
            f"{self.from_state} -> {self.to_state}, type={self.transition_type.value})"
        )
