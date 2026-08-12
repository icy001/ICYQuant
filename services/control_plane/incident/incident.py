"""
Incident — the core aggregate of the Incident Management domain.

An incident unifies Health failures, Policy triggers, Recovery failures, Risk
breaches and Execution failures into one trackable, aggregatable, escalatable
and closable object (spec section 1).

    Signal → Detection → Incident → Policy → Action → Recovery

The Incident is a pure domain aggregate: it records state transitions,
timeline entries and events, but performs no I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .escalation.level import EscalationLevel
from .incident_context import IncidentContext
from .incident_event import IncidentEvent, IncidentEventType
from .incident_fingerprint import IncidentFingerprint
from .incident_id import IncidentId
from .incident_scope import IncidentScope
from .incident_severity import IncidentSeverity
from .incident_source import IncidentSource
from .incident_status import IncidentStateMachine, IncidentStatus
from .incident_timeline import IncidentTimeline, IncidentTimelineEntry
from .incident_type import IncidentType
from .lifecycle.transition import IncidentTransition


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentError(Exception):
    """Base error for invalid incident operations."""


class IncidentResolutionError(IncidentError):
    """Raised when an incident is resolved without the mandatory metadata."""


class IncidentSeverityDowngradeError(IncidentError):
    """Raised when a severity is downgraded without verification."""


class Incident:
    """A single trackable incident."""

    def __init__(
        self,
        incident_id: Union[IncidentId, str],
        type: Union[IncidentType, str],
        severity: Union[IncidentSeverity, str],
        scope: Union[IncidentScope, str] = IncidentScope.GLOBAL,
        source: Union[IncidentSource, str] = IncidentSource.MANUAL,
        status: Union[IncidentStatus, str] = IncidentStatus.OPEN,
        context: Optional[IncidentContext] = None,
        fingerprint: Optional[IncidentFingerprint] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id if isinstance(incident_id, IncidentId) else IncidentId(incident_id)
        self.type = IncidentType(type)
        self.severity = IncidentSeverity(severity)
        self.scope = IncidentScope(scope)
        self.source = IncidentSource(source)
        self.status = IncidentStatus(status)
        self.context = context or IncidentContext()
        self.fingerprint = fingerprint

        self.created_at = created_at or _utcnow()
        self.updated_at = updated_at or self.created_at
        self.resolved_at: Optional[datetime] = None
        self.resolution_reason: str = ""
        self.resolved_by: str = ""
        self.verification_result: str = ""

        self.parent_incident_id: Optional[str] = None
        self.root_cause_incident_id: Optional[str] = None
        self.child_incident_ids: List[str] = []

        self.escalation_count = 0
        self.reopen_count = 0

        self.escalation_level: EscalationLevel = EscalationLevel.L1
        self.transitions: List[IncidentTransition] = []

        self.closed_at: Optional[datetime] = None
        self.reopened_at: Optional[datetime] = None

        # -- aggregation (spec sections 32, 42) ----------------------------
        # One incident can absorb many events/detections from many sources;
        # these counters make the aggregated facts visible instead of the
        # "one error = one incident" illusion.
        self.event_count: int = 0
        self.detection_count: int = 0
        self.suppressed_event_count: int = 0
        self._sources: set = set()
        self._scope_ids: set = set()

        self.timeline: IncidentTimeline = IncidentTimeline()
        self.events: List[IncidentEvent] = []

    # -- lifecycle transitions --------------------------------------------

    def acknowledge(self, actor: str = "", now: Optional[datetime] = None) -> IncidentEvent:
        """ACKNOWLEDGED ≠ RESOLVED (spec section 31)."""
        self._transition(IncidentStatus.ACKNOWLEDGED, actor=actor, now=now)
        return self._record(IncidentEventType.INCIDENT_ACKNOWLEDGED, actor=actor, now=now)

    def start_mitigation(self, actor: str = "", now: Optional[datetime] = None) -> IncidentEvent:
        self._transition(IncidentStatus.MITIGATING, actor=actor, now=now)
        return self._record(IncidentEventType.INCIDENT_MITIGATION_STARTED, actor=actor, now=now)

    def escalate(self, actor: str = "", detail: str = "", now: Optional[datetime] = None) -> IncidentEvent:
        """Recovery failed or severity increased (spec section 20)."""
        self._transition(IncidentStatus.ESCALATED, actor=actor, now=now)
        self.escalation_count += 1
        return self._record(
            IncidentEventType.INCIDENT_ESCALATED, actor=actor, detail=detail, now=now
        )

    def resolve(
        self,
        resolution_reason: str,
        resolved_by: str,
        verification_result: str = "VERIFIED",
        now: Optional[datetime] = None,
    ) -> IncidentEvent:
        """Resolve only with mandatory metadata — never bare status = RESOLVED.

        A bare "done" reason is rejected (spec section 29).
        """
        if not resolution_reason or not resolution_reason.strip():
            raise IncidentResolutionError("resolution_reason is required to resolve an incident")
        if not resolved_by or not resolved_by.strip():
            raise IncidentResolutionError("resolved_by is required to resolve an incident")
        now = now or _utcnow()
        IncidentStateMachine.assert_transition(self.status, IncidentStatus.RESOLVED)
        self.status = IncidentStatus.RESOLVED
        self.resolution_reason = resolution_reason
        self.resolved_by = resolved_by
        self.verification_result = verification_result
        self.resolved_at = now
        self.updated_at = now
        self.timeline.add(
            IncidentEventType.INCIDENT_RESOLVED.value,
            detail=f"{resolution_reason} ({verification_result})",
            actor=resolved_by,
            occurred_at=now,
        )
        event = IncidentEvent(
            event_type=IncidentEventType.INCIDENT_RESOLVED,
            incident_id=self.incident_id.value,
            occurred_at=now,
            actor=resolved_by,
            detail=resolution_reason,
        )
        self.events.append(event)
        return event

    def reopen(self, actor: str = "", now: Optional[datetime] = None) -> IncidentEvent:
        """A resolved incident reappeared (spec section 6, 18)."""
        self._transition(IncidentStatus.REOPENED, actor=actor, now=now)
        self.reopen_count += 1
        self.resolved_at = None
        self.resolution_reason = ""
        return self._record(IncidentEventType.INCIDENT_REOPENED, actor=actor, now=now)

    # -- severity ---------------------------------------------------------

    def raise_severity(
        self, new_severity: Union[IncidentSeverity, str], actor: str = "", now: Optional[datetime] = None
    ) -> IncidentEvent:
        """Escalate severity. Downgrades are rejected without verification.

        MEDIUM → HIGH → CRITICAL → FATAL is allowed; CRITICAL → MEDIUM is not
        (spec section 19).
        """
        new_severity = IncidentSeverity(new_severity)
        if new_severity == self.severity:
            return self._record(
                IncidentEventType.INCIDENT_UPDATED,
                actor=actor,
                detail=f"severity unchanged {new_severity.value}",
                now=now,
            )
        if not self.severity.can_escalate_to(new_severity):
            raise IncidentSeverityDowngradeError(
                f"Cannot downgrade severity {self.severity.value} -> {new_severity.value}"
            )
        old = self.severity.value
        self.severity = new_severity
        self.escalation_count += 1
        self.updated_at = now or _utcnow()
        detail = f"severity {old} -> {new_severity.value}"
        self.timeline.add(
            IncidentEventType.INCIDENT_ESCALATED.value,
            detail=detail,
            actor=actor,
            occurred_at=self.updated_at,
        )
        return self._record(
            IncidentEventType.INCIDENT_ESCALATED,
            actor=actor,
            detail=detail,
            now=now,
        )

    # -- correlation ------------------------------------------------------

    def bind_policy(self, policy_id: str, policy_version: str = "") -> None:
        self.context.bind_policy(policy_id, policy_version)

    def bind_recovery(self, recovery_id: str) -> None:
        self.context.bind_recovery(recovery_id)

    def bind_kill_switch(self, kill_switch_scope: str, scope_id: str = "") -> None:
        self.context.extra["kill_switch_scope"] = kill_switch_scope
        if scope_id:
            self.context.extra["kill_switch_scope_id"] = scope_id

    def set_parent(self, parent_incident_id: str) -> None:
        self.parent_incident_id = parent_incident_id

    def set_root_cause(self, root_cause_incident_id: str) -> None:
        self.root_cause_incident_id = root_cause_incident_id

    def add_child(self, child_incident_id: str) -> None:
        if child_incident_id not in self.child_incident_ids:
            self.child_incident_ids.append(child_incident_id)

    # -- metadata ---------------------------------------------------------

    @property
    def id(self) -> str:
        """Short alias for the incident identifier (audit-friendly)."""
        return self.incident_id.value

    @property
    def state(self) -> IncidentStatus:
        """Read the lifecycle status (alias for ``status``)."""
        return self.status

    @state.setter
    def state(self, value: Any) -> None:
        """Set the lifecycle status (used by the lifecycle service)."""
        self.status = IncidentStatus(value)

    @property
    def duration(self) -> float:
        """Seconds since creation, or time to resolution when resolved."""
        end = self.resolved_at or _utcnow()
        return max(0.0, (end - self.created_at).total_seconds())

    # -- aggregation ------------------------------------------------------

    @property
    def source_count(self) -> int:
        """Distinct services/accounts that contributed events (spec section 32)."""
        return len(self._sources)

    @property
    def affected_scope_count(self) -> int:
        """Distinct scope_ids (strategies, instruments, ...) affected."""
        return len(self._scope_ids)

    def aggregate_event(
        self,
        source: str = "",
        scope_id: str = "",
        suppressed: bool = False,
        now: Optional[datetime] = None,
    ) -> None:
        """Fold one raw event into this incident.

        ``suppressed=True`` counts event-storm noise separately so operators can
        see how violent the storm was without inflating ``event_count``
        (spec section 42).
        """
        if suppressed:
            self.suppressed_event_count += 1
        else:
            self.event_count += 1
            if source:
                self._sources.add(source)
            if scope_id:
                self._scope_ids.add(scope_id)
        self.updated_at = now or _utcnow()

    def aggregate_detection(self, detection: Any, now: Optional[datetime] = None) -> None:
        """Fold a DetectionResult into this incident.

        Counts the detection and applies the two only-up aggregation rules:
        severity may only rise (spec section 33) and scope may only widen
        (spec section 34).  A detector never mutates an incident directly —
        aggregation is the only path (spec section 16).
        """
        self.detection_count += 1
        if getattr(detection, "service", ""):
            self._sources.add(detection.service)
        scope_id = (
            getattr(detection, "strategy", "")
            or getattr(detection, "service", "")
            or getattr(detection, "account", "")
            or getattr(detection, "instrument", "")
            or getattr(detection, "venue", "")
        )
        if scope_id:
            self._scope_ids.add(scope_id)

        severity = getattr(detection, "severity", None)
        if severity is not None and severity > self.severity:
            self.raise_severity(severity, actor="detection-engine", now=now)

        scope = getattr(detection, "scope", None)
        if scope is not None:
            self.expand_scope(scope, now=now)

        self.updated_at = now or _utcnow()

    def expand_scope(
        self, scope: Union[IncidentScope, str], now: Optional[datetime] = None
    ) -> bool:
        """Widen the incident scope; returns True when it changed.

        STRATEGY -> SERVICE -> GLOBAL is the only direction allowed: an
        incident that starts local can spread, but an incident never shrinks
        without a manual audit (spec section 34).
        """
        scope = IncidentScope(scope)
        if not self.scope.can_expand_to(scope):
            return False
        old = self.scope.value
        now = now or _utcnow()
        self.scope = scope
        self.updated_at = now
        self.timeline.add(
            IncidentEventType.INCIDENT_UPDATED.value,
            detail=f"scope {old} -> {scope.value}",
            occurred_at=now,
        )
        return True

    # -- internals --------------------------------------------------------

    def _transition(
        self, target: IncidentStatus, actor: str = "", now: Optional[datetime] = None
    ) -> None:
        IncidentStateMachine.assert_transition(self.status, target)
        now = now or _utcnow()
        self.status = target
        self.updated_at = now
        self.timeline.add(target.value, actor=actor, occurred_at=now)

    def _record(
        self,
        event_type: IncidentEventType,
        actor: str = "",
        detail: str = "",
        now: Optional[datetime] = None,
    ) -> IncidentEvent:
        now = now or _utcnow()
        event = IncidentEvent(
            event_type=event_type,
            incident_id=self.incident_id.value,
            occurred_at=now,
            actor=actor,
            detail=detail,
            correlation_id=self.context.correlation_id,
        )
        self.events.append(event)
        return event

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id.value,
            "type": self.type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "scope": self.scope.value,
            "source": self.source.value,
            "context": self.context.to_dict(),
            "fingerprint": self.fingerprint.to_dict() if self.fingerprint else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_reason": self.resolution_reason,
            "resolved_by": self.resolved_by,
            "verification_result": self.verification_result,
            "parent_incident_id": self.parent_incident_id,
            "root_cause_incident_id": self.root_cause_incident_id,
            "child_incident_ids": list(self.child_incident_ids),
            "escalation_count": self.escalation_count,
            "reopen_count": self.reopen_count,
            "escalation_level": self.escalation_level.value,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "reopened_at": self.reopened_at.isoformat() if self.reopened_at else None,
            "transitions": [t.to_dict() for t in self.transitions],
            "timeline": self.timeline.to_dict(),
            "events": [e.to_dict() for e in self.events],
            "aggregation": {
                "event_count": self.event_count,
                "detection_count": self.detection_count,
                "suppressed_event_count": self.suppressed_event_count,
                "sources": sorted(self._sources),
                "scope_ids": sorted(self._scope_ids),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        incident = cls(
            incident_id=data["incident_id"],
            type=data["type"],
            severity=data["severity"],
            scope=data["scope"],
            source=data["source"],
            status=data["status"],
            context=IncidentContext.from_dict(data.get("context", {})),
            fingerprint=IncidentFingerprint.from_dict(data["fingerprint"])
            if data.get("fingerprint")
            else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )
        incident.resolved_at = datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None
        incident.resolution_reason = data.get("resolution_reason", "")
        incident.resolved_by = data.get("resolved_by", "")
        incident.verification_result = data.get("verification_result", "")
        incident.parent_incident_id = data.get("parent_incident_id")
        incident.root_cause_incident_id = data.get("root_cause_incident_id")
        incident.child_incident_ids = list(data.get("child_incident_ids", []))
        incident.escalation_count = int(data.get("escalation_count", 0))
        incident.reopen_count = int(data.get("reopen_count", 0))
        incident.escalation_level = EscalationLevel(
            int(data.get("escalation_level", EscalationLevel.L1.value))
        )
        incident.closed_at = (
            datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None
        )
        incident.reopened_at = (
            datetime.fromisoformat(data["reopened_at"]) if data.get("reopened_at") else None
        )
        incident.transitions = [
            IncidentTransition.from_dict(t) for t in data.get("transitions", [])
        ]
        incident.timeline = IncidentTimeline.from_dict(data.get("timeline", {}))
        incident.events = [
            IncidentEvent.from_dict(e) for e in data.get("events", [])
        ]
        aggregation = data.get("aggregation", {})
        incident.event_count = int(aggregation.get("event_count", 0))
        incident.detection_count = int(aggregation.get("detection_count", 0))
        incident.suppressed_event_count = int(aggregation.get("suppressed_event_count", 0))
        incident._sources = set(aggregation.get("sources", []))
        incident._scope_ids = set(aggregation.get("scope_ids", []))
        return incident

    def __repr__(self) -> str:
        return (
            f"Incident({self.incident_id.value}, {self.type.value}, "
            f"{self.status.value}, {self.severity.value})"
        )
