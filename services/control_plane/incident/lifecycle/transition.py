from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Union
from uuid import UUID, uuid4

from .state_machine import IncidentState


@dataclass(frozen=True)
class IncidentTransition:
    incident_id: Union[UUID, str]
    from_state: IncidentState
    to_state: IncidentState
    actor: str
    reason: str
    transition_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": (
                str(self.incident_id)
                if isinstance(self.incident_id, UUID)
                else self.incident_id
            ),
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "actor": self.actor,
            "reason": self.reason,
            "transition_id": str(self.transition_id),
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentTransition":
        return cls(
            incident_id=data["incident_id"],
            from_state=IncidentState(data["from_state"]),
            to_state=IncidentState(data["to_state"]),
            actor=data["actor"],
            reason=data["reason"],
            transition_id=UUID(data["transition_id"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=dict(data.get("metadata", {})),
        )
