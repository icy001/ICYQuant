"""
Incident Manager — Autonomous incident detection and management.

Handles the full incident lifecycle: Detect → Classify → Contain →
Recover → Review → Learn.
"""

from __future__ import annotations

import uuid
import time
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class IncidentStatus(Enum):
    DETECTED = "detected"
    CLASSIFIED = "classified"
    CONTAINING = "containing"
    CONTAINED = "contained"
    RECOVERING = "recovering"
    RESOLVED = "resolved"
    REVIEWED = "reviewed"


class IncidentManager:
    """
    Manages autonomous system incidents.

    Implements the incident lifecycle:
        Detect → Classify → Contain → Recover → Review → Learn
    """

    def __init__(self):
        self._incidents: dict[str, dict] = {}
        self._incident_count = 0

    # ------------------------------------------------------------------
    # Incident Lifecycle
    # ------------------------------------------------------------------

    async def create_incident(
        self,
        incident_type: str,
        description: str,
        severity: str = "warning",
        context: Optional[dict] = None,
    ) -> str:
        """Create a new incident."""
        inc_id = str(uuid.uuid4())
        self._incidents[inc_id] = {
            "incident_id": inc_id,
            "type": incident_type,
            "description": description,
            "severity": IncidentSeverity(severity),
            "status": IncidentStatus.DETECTED,
            "created_at": time.time(),
            "context": context or {},
            "timeline": [{"event": "detected", "timestamp": time.time()}],
        }
        self._incident_count += 1

        if severity in ("critical", "major"):
            logger.critical("INCIDENT [%s]: %s", severity, description)
        else:
            logger.warning("Incident [%s]: %s", severity, description)

        return inc_id

    async def classify(self, incident_id: str, category: str, system_component: str = ""):
        """Classify an incident."""
        inc = self._incidents.get(incident_id)
        if inc:
            inc["category"] = category
            inc["system_component"] = system_component
            inc["status"] = IncidentStatus.CLASSIFIED
            inc["timeline"].append({"event": "classified", "timestamp": time.time()})

    async def contain(self, incident_id: str, containment_action: str):
        """Contain an incident."""
        inc = self._incidents.get(incident_id)
        if inc:
            inc["status"] = IncidentStatus.CONTAINING
            inc["containment_action"] = containment_action
            inc["timeline"].append({"event": "containing", "action": containment_action, "timestamp": time.time()})

    async def recover(self, incident_id: str, recovery_action: str):
        """Recover from an incident."""
        inc = self._incidents.get(incident_id)
        if inc:
            inc["status"] = IncidentStatus.RECOVERING
            inc["recovery_action"] = recovery_action
            inc["timeline"].append({"event": "recovering", "action": recovery_action, "timestamp": time.time()})

    async def resolve(self, incident_id: str, resolution: str):
        """Resolve an incident."""
        inc = self._incidents.get(incident_id)
        if inc:
            inc["status"] = IncidentStatus.RESOLVED
            inc["resolution"] = resolution
            inc["resolved_at"] = time.time()
            inc["timeline"].append({"event": "resolved", "timestamp": time.time()})

    async def review(self, incident_id: str, lessons: str, preventions: list[str]):
        """Review an incident for lessons learned."""
        inc = self._incidents.get(incident_id)
        if inc:
            inc["status"] = IncidentStatus.REVIEWED
            inc["lessons_learned"] = lessons
            inc["preventions"] = preventions
            inc["reviewed_at"] = time.time()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def active_incidents(self) -> list[dict]:
        """Get all active (unresolved) incidents."""
        return [
            inc for inc in self._incidents.values()
            if inc["status"] not in (IncidentStatus.RESOLVED, IncidentStatus.REVIEWED)
        ]

    def get(self, incident_id: str) -> Optional[dict]:
        return self._incidents.get(incident_id)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        active = self.active_incidents()
        return {
            "total_incidents": self._incident_count,
            "active": len(active),
            "resolved": len(self._incidents) - len(active),
            "by_severity": {
                s.value: len([i for i in self._incidents.values() if i["severity"].value == s.value])
                for s in IncidentSeverity
            },
        }
