"""
CorrelationEngine — decides what a DetectionResult means for incidents.

Pipeline (spec section 5):

    DetectionResult -> build fingerprint -> look up active incident ->
    decision: NEW / EXISTING / CHILD / NO_INCIDENT

- A matched detection whose fingerprint already has an ACTIVE incident is an
  update (EXISTING), not a new incident — the incident-storm shield.
- A matched detection whose incident type is declared a child of an active
  parent by a CorrelationRule becomes a CHILD incident.
- Everything else opens a NEW incident.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from ...repositories.incident_repository import IncidentRepository
from ..detection.detection_result import DetectionResult
from ..incident import Incident
from ..incident_type import IncidentType
from .correlation_context import CorrelationContext
from .correlation_result import CorrelationDecision, CorrelationResult
from .correlation_rule import CorrelationRule
from .fingerprint_builder import FingerprintBuilder


class CorrelationEngine:
    """Map detections onto the incident graph."""

    def __init__(
        self,
        repository: Optional[IncidentRepository] = None,
        rules: Optional[Sequence[CorrelationRule]] = None,
        window_seconds: float = 300.0,
        fingerprint_builder: Optional[FingerprintBuilder] = None,
    ) -> None:
        self.repository = repository or IncidentRepository()
        self.rules: List[CorrelationRule] = list(rules) if rules is not None else []
        self.window_seconds = window_seconds
        self.fingerprint_builder = fingerprint_builder or FingerprintBuilder()

    # -- correlation ------------------------------------------------------

    def correlate(
        self,
        detection_or_context: Union[DetectionResult, CorrelationContext],
    ) -> CorrelationResult:
        if isinstance(detection_or_context, CorrelationContext):
            context = detection_or_context
        else:
            context = CorrelationContext(detection=detection_or_context)

        detection = context.detection

        if not detection.matched:
            return CorrelationResult(
                decision=CorrelationDecision.NO_INCIDENT,
                detection=detection,
                reason="detection did not match any rule",
            )

        fingerprint = self.fingerprint_builder.build(
            event_type=detection.event_type,
            incident_type=detection.incident_type,
            source=detection.source,
            scope=detection.scope,
            service=detection.service,
            account=detection.account,
            strategy=detection.strategy,
            instrument=detection.instrument,
            venue=detection.venue,
        )

        active = self.repository.find_active_by_fingerprint(fingerprint)
        if active is not None:
            return CorrelationResult(
                decision=CorrelationDecision.EXISTING_INCIDENT,
                detection=detection,
                fingerprint=fingerprint.value,
                incident_type=(
                    detection.incident_type.value if detection.incident_type else None
                ),
                incident_id=active.incident_id.value,
                reason="active incident already exists for this fingerprint",
            )

        candidates: List[tuple[CorrelationRule, Incident]] = []
        for rule in self.rules:
            if not rule.matches_child(detection.incident_type):
                continue
            parent = self._find_active_parent(
                rule.parent_incident_type,
                detection.occurred_at or context.now,
                rule.max_window_seconds,
            )
            if parent is None:
                continue
            candidates.append((rule, parent))

        if candidates:
            # Best rule wins: highest confidence first, then lowest priority
            # number (spec section 28).
            rule, parent = max(
                candidates, key=lambda rp: (rp[0].confidence, -rp[0].priority)
            )
            return CorrelationResult(
                decision=CorrelationDecision.CHILD_INCIDENT,
                detection=detection,
                fingerprint=fingerprint.value,
                incident_type=(
                    detection.incident_type.value if detection.incident_type else None
                ),
                parent_incident_id=parent.incident_id.value,
                reason=(
                    f"rule {rule.rule_id} "
                    f"(confidence={rule.confidence:.2f}, priority={rule.priority}): "
                    f"{rule.parent_incident_type.value} -> {rule.child_incident_type.value}"
                ),
            )

        return CorrelationResult(
            decision=CorrelationDecision.NEW_INCIDENT,
            detection=detection,
            fingerprint=fingerprint.value,
            incident_type=(
                detection.incident_type.value if detection.incident_type else None
            ),
            reason="no active incident and no correlation rule matched",
        )

    def _find_active_parent(
        self,
        parent_type: IncidentType,
        detection_time: datetime,
        max_window_seconds: float,
    ) -> Optional[Incident]:
        for incident in self.repository.list_all():
            if incident.type is not IncidentType(parent_type):
                continue
            if not incident.status.is_open:
                continue
            elapsed = (detection_time - incident.updated_at).total_seconds()
            if 0 <= elapsed <= max_window_seconds:
                return incident
        return None

    # -- rule management --------------------------------------------------

    def add_rule(self, rule: CorrelationRule) -> None:
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        for i, rule in enumerate(self.rules):
            if rule.rule_id == rule_id:
                del self.rules[i]
                return True
        return False

    def rule_count(self) -> int:
        return len(self.rules)

    def clear(self) -> None:
        self.rules.clear()

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_seconds": self.window_seconds,
            "rules": [rule.to_dict() for rule in self.rules],
        }
