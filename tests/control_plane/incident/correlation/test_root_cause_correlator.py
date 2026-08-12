"""RootCauseCorrelator — root cause heuristics over an incident group."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.incident.correlators.root_cause_correlator import (
    RootCauseCorrelator,
)
from services.control_plane.incident.incident import Incident
from services.control_plane.incident.incident_id import IncidentId
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.incident_type import IncidentType

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def _incident(seq, created_at, **kwargs):
    return Incident(
        incident_id=IncidentId.generate(seq),
        type=kwargs.pop("type", IncidentType.HEALTH_FAILURE),
        severity=kwargs.pop("severity", IncidentSeverity.HIGH),
        scope=kwargs.pop("scope", IncidentScope.SERVICE),
        source=kwargs.pop("source", IncidentSource.HEALTH_MONITOR),
        status=kwargs.pop("status", IncidentStatus.OPEN),
        created_at=created_at,
    )


class TestRootCauseCorrelator:
    def test_empty_group_returns_none(self):
        assert RootCauseCorrelator.find_root_cause([]) is None

    def test_single_incident_is_root_cause(self):
        incident = _incident(1, NOW)
        assert RootCauseCorrelator.find_root_cause([incident]) is incident

    def test_earliest_opened_is_root_cause(self):
        earlier = _incident(1, NOW - timedelta(minutes=10))
        later = _incident(2, NOW)
        root = RootCauseCorrelator.find_root_cause([later, earlier])
        assert root is earlier

    def test_out_degree_breaks_ties(self):
        a = _incident(1, NOW)
        b = _incident(2, NOW)
        c = _incident(3, NOW + timedelta(minutes=1))
        b.parent_incident_id = a.incident_id.value
        c.parent_incident_id = a.incident_id.value
        root = RootCauseCorrelator.find_root_cause([a, b, c])
        assert root is a


class TestRootCausePromotion:
    def test_promotes_deeper_cause_and_demotes_previous_root(self):
        """§35: a later-discovered deeper cause replaces the previous root."""
        earlier = _incident(1, NOW, type=IncidentType.POSITION_INTEGRITY_FAILURE)
        deeper = _incident(2, NOW + timedelta(minutes=1), type=IncidentType.EVENT_BUS_FAILURE)
        earlier.set_parent(deeper.incident_id.value)

        RootCauseCorrelator.promote_root_cause([earlier, deeper], deeper)

        assert deeper.parent_incident_id is None
        assert deeper.root_cause_incident_id is None
        assert earlier.parent_incident_id == deeper.incident_id.value
        assert earlier.root_cause_incident_id == deeper.incident_id.value
        assert deeper.child_incident_ids == [earlier.incident_id.value]

    def test_promotion_reparents_multiple_children(self):
        a = _incident(1, NOW)
        b = _incident(2, NOW + timedelta(minutes=1))
        c = _incident(3, NOW + timedelta(minutes=2))
        b.set_parent(a.incident_id.value)
        c.set_parent(a.incident_id.value)

        RootCauseCorrelator.promote_root_cause([a, b, c], b)

        assert b.parent_incident_id is None
        assert b.child_incident_ids == [a.incident_id.value, c.incident_id.value]
        assert a.parent_incident_id == b.incident_id.value
        assert c.parent_incident_id == b.incident_id.value
