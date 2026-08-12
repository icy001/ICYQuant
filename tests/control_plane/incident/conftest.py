"""Shared fixtures for the incident management test suite."""
from __future__ import annotations

import pytest

from services.control_plane.incident.escalation.level import EscalationLevel
from services.control_plane.incident.escalation.policy import (
    DEFAULT_ESCALATION_POLICIES,
)
from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_id import IncidentId
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.incident_type import IncidentType


@pytest.fixture
def incident_factory():
    """Build an Incident with minimal plumbing for lifecycle tests."""
    counter = {"n": 0}

    def _factory(**kwargs):
        counter["n"] += 1
        incident_id = (
            kwargs.pop("incident_id", None) or IncidentId.generate(counter["n"])
        )
        status = kwargs.pop("status", None)
        if status is None and "state" in kwargs:
            status = kwargs.pop("state")
        incident = Incident(
            incident_id=incident_id,
            type=kwargs.pop("type", IncidentType.HEALTH_FAILURE),
            severity=kwargs.pop("severity", IncidentSeverity.LOW),
            scope=kwargs.pop("scope", IncidentScope.GLOBAL),
            source=kwargs.pop("source", IncidentSource.HEALTH_MONITOR),
            status=status or IncidentStatus.OPEN,
            fingerprint=kwargs.pop("fingerprint", None),
            created_at=kwargs.pop("created_at", None),
            updated_at=kwargs.pop("updated_at", None),
        )
        if "escalation_level" in kwargs:
            incident.escalation_level = kwargs.pop("escalation_level")
        else:
            incident.escalation_level = DEFAULT_ESCALATION_POLICIES[
                incident.severity
            ].initial_level
        if "closed_at" in kwargs:
            incident.closed_at = kwargs.pop("closed_at")
        if "reopened_at" in kwargs:
            incident.reopened_at = kwargs.pop("reopened_at")
        if kwargs:
            raise TypeError(f"unexpected incident_factory kwargs: {sorted(kwargs)}")
        return incident

    return _factory
