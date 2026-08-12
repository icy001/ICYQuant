"""
CorrelationResult — the outcome of correlating one detection.

Decision semantics:

    NEW_INCIDENT       open a new incident for this detection
    EXISTING_INCIDENT  an active incident with the same fingerprint exists
    CHILD_INCIDENT     this detection belongs to an active parent incident
    NO_INCIDENT        the detection did not match, no incident involved
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from ..detection.detection_result import DetectionResult


class CorrelationDecision(str, Enum):
    NEW_INCIDENT = "NEW_INCIDENT"
    EXISTING_INCIDENT = "EXISTING_INCIDENT"
    CHILD_INCIDENT = "CHILD_INCIDENT"
    NO_INCIDENT = "NO_INCIDENT"


@dataclass
class CorrelationResult:
    decision: CorrelationDecision
    detection: DetectionResult
    fingerprint: str = ""
    incident_type: Optional[str] = None
    incident_id: Optional[str] = None
    parent_incident_id: Optional[str] = None
    reason: str = ""

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "detection": self.detection.to_dict(),
            "fingerprint": self.fingerprint,
            "incident_type": self.incident_type,
            "incident_id": self.incident_id,
            "parent_incident_id": self.parent_incident_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationResult":
        return cls(
            decision=CorrelationDecision(data["decision"]),
            detection=DetectionResult.from_dict(data["detection"]),
            fingerprint=data.get("fingerprint", ""),
            incident_type=data.get("incident_type"),
            incident_id=data.get("incident_id"),
            parent_incident_id=data.get("parent_incident_id"),
            reason=data.get("reason", ""),
        )

    def __repr__(self) -> str:
        return f"CorrelationResult({self.decision.value}, reason={self.reason!r})"
