"""
DetectionRule — declarative rule that turns a raw event into a DetectionResult.

A rule answers one question: "is this event anomalous enough to be detected?"
It never decides what action to take — that is Policy's job (spec section 2-4).

    rule_id:  POSITION-UNTRUSTED-001
    event_type: POSITION_HEALTH_CHANGED
    condition: state == UNTRUSTED
    severity: CRITICAL
    incident_type: POSITION_INTEGRITY_FAILURE
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Union

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType


def field_equals(field_name: str, expected: Any) -> Callable[[Dict[str, Any]], bool]:
    """Build a condition matching when event[field_name] == expected."""

    def _check(event: Dict[str, Any]) -> bool:
        return event.get(field_name) == expected

    return _check


def field_in(field_name: str, expected: set) -> Callable[[Dict[str, Any]], bool]:
    """Build a condition matching when event[field_name] is in expected."""

    def _check(event: Dict[str, Any]) -> bool:
        return event.get(field_name) in expected

    return _check


@dataclass
class DetectionRule:
    rule_id: str
    event_type: str
    incident_type: Union[IncidentType, str]
    severity: Union[IncidentSeverity, str]
    scope: Union[IncidentScope, str] = IncidentScope.GLOBAL
    source: Union[IncidentSource, str] = IncidentSource.MANUAL
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    enabled: bool = True
    priority: int = 100
    rule_version: str = "v1"
    cooldown_seconds: Optional[float] = None
    """Suppress repeated detections within this window (spec section 43)."""

    def __post_init__(self) -> None:
        self.incident_type = IncidentType(self.incident_type)
        self.severity = IncidentSeverity(self.severity)
        self.scope = IncidentScope(self.scope)
        self.source = IncidentSource(self.source)

    def matches(self, event: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        if event.get("event_type") != self.event_type:
            return False
        if self.condition is None:
            return True
        return bool(self.condition(event))

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "event_type": self.event_type,
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "scope": self.scope.value,
            "source": self.source.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "cooldown_seconds": self.cooldown_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectionRule":
        return cls(
            rule_id=data["rule_id"],
            rule_version=data.get("rule_version", "v1"),
            event_type=data["event_type"],
            incident_type=data["incident_type"],
            severity=data["severity"],
            scope=data.get("scope", IncidentScope.GLOBAL.value),
            source=data.get("source", IncidentSource.MANUAL.value),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 100),
            cooldown_seconds=data.get("cooldown_seconds"),
        )

    def __repr__(self) -> str:
        return (
            f"DetectionRule({self.rule_id}, {self.event_type} -> "
            f"{self.incident_type.value}/{self.severity.value})"
        )
