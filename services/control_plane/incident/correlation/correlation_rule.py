"""
CorrelationRule — a declarative causal relationship between incident types.

Temporal + causal correlation (spec section 32): if a CHILD incident type is
detected while a PARENT incident of the declared type is active within the
window, the detection becomes a child of the parent instead of a new incident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ..incident_type import IncidentType


@dataclass
class CorrelationRule:
    rule_id: str
    parent_incident_type: Union[IncidentType, str]
    child_incident_type: Union[IncidentType, str]
    max_window_seconds: float = 300.0
    confidence: float = 1.0
    """How likely the two incident types share one root cause (0..1).

    >= 0.70 is treated as a high-confidence causal link; below that the
    relationship is only "possible" and should not be promoted to a root
    cause without further evidence (spec section 27).
    """

    priority: int = 100
    """Tie-breaker when several rules score equally (lower wins).

    Confidence is the primary sort key, priority the secondary one
    (spec section 28).
    """

    enabled: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        self.parent_incident_type = IncidentType(self.parent_incident_type)
        self.child_incident_type = IncidentType(self.child_incident_type)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    def matches(
        self,
        parent_type: Union[IncidentType, str],
        child_type: Union[IncidentType, str],
    ) -> bool:
        """True if this rule declares the given parent -> child relationship."""
        if not self.enabled:
            return False
        parent = IncidentType(parent_type) if parent_type is not None else None
        child = IncidentType(child_type) if child_type is not None else None
        return (
            parent is self.parent_incident_type
            and child is self.child_incident_type
        )

    def matches_child(self, child_type: Union[IncidentType, str, None]) -> bool:
        """True if this rule could attach the given child to a parent."""
        if not self.enabled or child_type is None:
            return False
        return IncidentType(child_type) is self.child_incident_type

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "parent_incident_type": self.parent_incident_type.value,
            "child_incident_type": self.child_incident_type.value,
            "max_window_seconds": self.max_window_seconds,
            "confidence": self.confidence,
            "priority": self.priority,
            "enabled": self.enabled,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CorrelationRule":
        return cls(
            rule_id=data["rule_id"],
            parent_incident_type=data["parent_incident_type"],
            child_incident_type=data["child_incident_type"],
            max_window_seconds=data.get("max_window_seconds", 300.0),
            confidence=data.get("confidence", 1.0),
            priority=data.get("priority", 100),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        return (
            f"CorrelationRule({self.rule_id}, "
            f"{self.parent_incident_type.value} -> {self.child_incident_type.value})"
        )
