"""
IncidentPipeline — the Detection -> Correlation -> Incident application layer.

The engines only *decide*: the Detection Engine says "this event is
anomalous", the Correlation Engine says "this detection is new / an update /
a child / nothing".  This pipeline is the only place that actually creates,
aggregates or links incidents, which is exactly the boundary the spec
demands (spec sections 5, 16, 37):

    raw event -> DetectionEngine -> DetectionResult
              -> CorrelationEngine -> CorrelationResult
              -> NEW_INCIDENT       open a new incident
              -> EXISTING_INCIDENT  aggregate into the active incident
              -> CHILD_INCIDENT     open a child under an active parent
              -> suppressed         count as storm noise, never as a new
                                    incident (spec section 42)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..repositories.incident_repository import IncidentRepository
from .correlation.correlation_engine import CorrelationEngine
from .correlation.correlation_result import CorrelationDecision
from .detection.detection_engine import IncidentDetectionEngine
from .detection.detection_result import DetectionResult
from .incident import Incident
from .incident_context import IncidentContext
from .incident_fingerprint import IncidentFingerprint
from .incident_id import IncidentId
from .incident_scope import IncidentScope
from .incident_severity import IncidentSeverity
from .incident_source import IncidentSource
from .incident_type import IncidentType


class IncidentPipeline:
    """Feed raw events through detection + correlation and mutate incidents."""

    def __init__(
        self,
        repository: Optional[IncidentRepository] = None,
        detection_engine: Optional[IncidentDetectionEngine] = None,
        correlation_engine: Optional[CorrelationEngine] = None,
    ) -> None:
        self.repository = repository or IncidentRepository()
        self.detection_engine = detection_engine or IncidentDetectionEngine()
        self.correlation_engine = correlation_engine or CorrelationEngine(
            repository=self.repository
        )
        self._seq = self._highest_sequence()

    # -- public API -------------------------------------------------------

    def ingest(self, event: Dict[str, Any]) -> Optional[Incident]:
        """Run one raw event through the pipeline.

        Returns the incident that was created/updated, or None when the event
        was normal (no detection) or a pure delivery duplicate.
        """
        detection = self.detection_engine.evaluate(event)

        # Storm shield: a suppressed detection (rule cooldown) belongs to an
        # existing incident — count it as noise instead of re-processing it.
        if detection.suppressed and detection.rule_id:
            incident = self._count_suppressed(detection)
            if incident is not None:
                return incident

        correlation = self.correlation_engine.correlate(detection)
        decision = correlation.decision

        if decision is CorrelationDecision.NO_INCIDENT:
            return None
        if decision is CorrelationDecision.EXISTING_INCIDENT:
            incident = self._aggregate(correlation, detection)
        elif decision is CorrelationDecision.CHILD_INCIDENT:
            incident = self._create(
                correlation, detection, child_of=correlation.parent_incident_id
            )
        else:  # NEW_INCIDENT
            incident = self._create(correlation, detection)

        self.repository.save(incident)
        return incident

    def clear(self) -> None:
        """Reset in-memory state (used by tests / restarts)."""
        self.detection_engine.clear()
        self.correlation_engine.clear()
        self.repository.clear()
        self._seq = 0

    # -- incident creation / aggregation -----------------------------------

    def _create(
        self,
        correlation: Any,
        detection: DetectionResult,
        child_of: Optional[str] = None,
    ) -> Incident:
        occurred_at = detection.occurred_at
        incident = Incident(
            incident_id=self._allocate_id(occurred_at),
            type=detection.incident_type or IncidentType.SYSTEM_FAILURE,
            severity=detection.severity or IncidentSeverity.MEDIUM,
            scope=detection.scope or IncidentScope.GLOBAL,
            source=detection.source or IncidentSource.MANUAL,
            fingerprint=self._build_fingerprint(detection),
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        incident.context = IncidentContext(
            service=detection.service,
            account=detection.account,
            strategy=detection.strategy,
            instrument=detection.instrument,
            venue=detection.venue,
            correlation_id=detection.event_id,
            extra={"detail": detection.detail} if detection.detail else {},
        )

        if child_of is not None:
            incident.set_parent(child_of)
            parent = self.repository.get(child_of)
            if parent is not None:
                parent.add_child(incident.incident_id.value)
                # A more severe child drags the whole fault family up
                # (spec section 41: HIGH -> CRITICAL when a CRITICAL child
                # surfaces).
                if incident.severity > parent.severity:
                    parent.raise_severity(
                        incident.severity,
                        actor="correlation-engine",
                        now=occurred_at,
                    )
                self.repository.save(parent)

        incident.aggregate_event(
            source=detection.service,
            scope_id=detection.strategy,
            now=occurred_at,
        )
        incident.aggregate_detection(detection, now=occurred_at)
        return incident

    def _aggregate(
        self, correlation: Any, detection: DetectionResult
    ) -> Incident:
        """Fold a repeated detection into the active incident."""
        incident = self.repository.get(correlation.incident_id)
        if incident is None:
            # Active incident vanished between correlate and apply — reopen
            # the fault as a fresh incident instead of dropping the event.
            return self._create(correlation, detection)

        scope_id = (
            detection.strategy
            or detection.service
            or detection.account
            or detection.instrument
            or detection.venue
        )
        incident.aggregate_event(
            source=detection.service,
            scope_id=scope_id,
            now=detection.occurred_at,
        )
        incident.aggregate_detection(detection, now=detection.occurred_at)
        incident.context.merge(
            IncidentContext(
                service=detection.service,
                account=detection.account,
                strategy=detection.strategy,
                instrument=detection.instrument,
                venue=detection.venue,
            )
        )
        return incident

    def _count_suppressed(self, detection: DetectionResult) -> Optional[Incident]:
        """Increment suppressed_event_count on the matching active incident."""
        fingerprint = self._build_fingerprint(detection)
        if fingerprint is None:
            return None
        active = self.repository.find_active_by_fingerprint(fingerprint)
        if active is None:
            return None
        active.aggregate_event(
            source=detection.service,
            scope_id=detection.strategy,
            suppressed=True,
            now=detection.occurred_at,
        )
        self.repository.save(active)
        return active

    # -- helpers ----------------------------------------------------------

    def _build_fingerprint(self, detection: DetectionResult) -> Optional[IncidentFingerprint]:
        if detection.incident_type is None:
            return None
        return self.correlation_engine.fingerprint_builder.build(
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

    def _highest_sequence(self) -> int:
        highest = 0
        for incident in self.repository.list_all():
            try:
                seq = int(incident.incident_id.value.rsplit("-", 1)[1])
            except (IndexError, ValueError):
                continue
            highest = max(highest, seq)
        return highest

    def _allocate_id(self, occurred_at: Any) -> IncidentId:
        self._seq += 1
        return IncidentId.generate(self._seq, occurred_at)
