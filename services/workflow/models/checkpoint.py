"""Checkpoint model.

A checkpoint captures a restorable snapshot of workflow execution state at a
specific point in time. Checkpoints are used to recover from failures, replay
execution from a known good state, or audit intermediate results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class CheckpointType(str, Enum):
    """Granularity of state captured by a checkpoint."""

    NODE = "NODE"
    WORKFLOW = "WORKFLOW"
    VARIABLE = "VARIABLE"
    FULL = "FULL"


class CheckpointState(str, Enum):
    """Lifecycle state of a checkpoint."""

    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CORRUPTED = "CORRUPTED"


@dataclass
class Checkpoint:
    """A restorable snapshot of workflow execution state.

    The ``variables`` field holds a copy of execution variables, ``state``
    holds engine-specific state (e.g. node statuses), and ``node_id`` scopes a
    checkpoint to a specific node when ``checkpoint_type`` is
    :attr:`CheckpointType.NODE`.
    """

    checkpoint_id: str
    workflow_id: str
    execution_id: str
    checkpoint_type: CheckpointType
    node_id: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the checkpoint to a plain dictionary suitable for JSON encoding."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "checkpoint_type": self.checkpoint_type.value,
            "node_id": self.node_id,
            "variables": dict(self.variables),
            "state": dict(self.state),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Checkpoint:
        """Reconstruct a :class:`Checkpoint` from a serialized dictionary."""
        created_at = data.get("created_at")
        return cls(
            checkpoint_id=data["checkpoint_id"],
            workflow_id=data["workflow_id"],
            execution_id=data["execution_id"],
            checkpoint_type=CheckpointType(data.get("checkpoint_type", CheckpointType.FULL.value)),
            node_id=data.get("node_id"),
            variables=dict(data.get("variables", {})),
            state=dict(data.get("state", {})),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.utcnow(),
        )
