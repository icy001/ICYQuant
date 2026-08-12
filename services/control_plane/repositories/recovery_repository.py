"""
RecoveryRepository — durable storage of recovery sessions.

#40/#41 — recovery sessions survive orchestrator crashes: the repository holds
the full context + plan + state, so a restarted orchestrator can load the
active recovery and resume from its last checkpoint instead of starting over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..recovery.recovery_orchestrator import RecoverySession
from ..recovery.recovery_state import RecoveryState


@dataclass
class RecoveryRepository:
    """In-memory recovery session store (swap for a durable adapter later)."""

    _recoveries: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # -- writes -----------------------------------------------------------

    def save(self, session: RecoverySession) -> None:
        self._recoveries[session.recovery_id] = session.to_dict()

    def delete(self, recovery_id: str) -> bool:
        return self._recoveries.pop(recovery_id, None) is not None

    def clear(self) -> None:
        self._recoveries.clear()

    # -- reads ------------------------------------------------------------

    def get(self, recovery_id: str) -> Optional[RecoverySession]:
        data = self._recoveries.get(recovery_id)
        return RecoverySession.from_dict(data) if data else None

    def list_all(self) -> List[RecoverySession]:
        return [self.get(rid) for rid in self._recoveries]  # type: ignore[list-item]

    def find_by_incident(self, incident_id: str) -> Optional[RecoverySession]:
        for data in self._recoveries.values():
            if data.get("context", {}).get("incident_id") == incident_id:
                return RecoverySession.from_dict(data)
        return None

    def find_active_by_incident(self, incident_id: str) -> Optional[RecoverySession]:
        active = self.list_active()
        for session in active:
            if session.context.incident_id == incident_id:
                return session
        return None

    def list_active(self) -> List[RecoverySession]:
        return [
            s for s in self.list_all() if s.state.is_active or s.state is RecoveryState.FAILED
        ]

    # -- metrics ----------------------------------------------------------

    def recovery_count(self) -> int:
        return len(self._recoveries)


__all__ = ["RecoveryRepository"]
