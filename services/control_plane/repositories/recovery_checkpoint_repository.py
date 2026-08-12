"""
RecoveryCheckpointRepository — durable checkpoint store.

#13/#14 — a replay must never run 10M events and then fail at the end.
Checkpoints are persisted after every successful step so a retry resumes from
``event_cursor + 1`` instead of restarting.  Each checkpoint stores a checksum
so corrupted checkpoints are detected, never silently resumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..recovery.recovery_checkpoint import RecoveryCheckpoint


@dataclass
class RecoveryCheckpointRepository:
    """In-memory checkpoint store keyed by recovery_id."""

    _checkpoints: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # -- writes -----------------------------------------------------------

    def save(self, checkpoint: RecoveryCheckpoint) -> None:
        if not checkpoint.verify():
            raise ValueError(
                f"refusing to persist corrupted checkpoint for {checkpoint.recovery_id!r}"
            )
        self._checkpoints.setdefault(checkpoint.recovery_id, []).append(
            checkpoint.to_dict()
        )

    def delete(self, recovery_id: str) -> bool:
        return self._checkpoints.pop(recovery_id, None) is not None

    def clear(self) -> None:
        self._checkpoints.clear()

    # -- reads ------------------------------------------------------------

    def latest(self, recovery_id: str) -> Optional[RecoveryCheckpoint]:
        history = self._checkpoints.get(recovery_id) or []
        if not history:
            return None
        checkpoint = RecoveryCheckpoint.from_dict(history[-1])
        return checkpoint if checkpoint.verify() else None

    def list_for(self, recovery_id: str) -> List[RecoveryCheckpoint]:
        return [
            RecoveryCheckpoint.from_dict(data)
            for data in self._checkpoints.get(recovery_id, [])
        ]

    def checkpoint_count(self) -> int:
        return sum(len(v) for v in self._checkpoints.values())


__all__ = ["RecoveryCheckpointRepository"]
