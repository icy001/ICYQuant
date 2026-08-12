"""IncidentCluster — aggregated view of a fault family."""
from __future__ import annotations

from services.control_plane.incident.correlation.incident_cluster import (
    IncidentCluster,
)
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_type import IncidentType


def _cluster():
    return IncidentCluster(
        cluster_id="CL-0001",
        root_incident_id="INC-20260812-000001",
        incident_type=IncidentType.HEALTH_FAILURE,
        severity=IncidentSeverity.LOW,
    )


class TestIncidentCluster:
    def test_creation_adds_root_as_first_member(self):
        cluster = _cluster()
        assert cluster.member_ids == ["INC-20260812-000001"]
        assert cluster.is_root("INC-20260812-000001")

    def test_add_member_deduplicates(self):
        cluster = _cluster()
        cluster.add_member("INC-20260812-000002")
        cluster.add_member("INC-20260812-000002")
        assert cluster.member_count() == 2

    def test_escalate_severity_only_upwards(self):
        cluster = _cluster()
        assert cluster.escalate_severity(IncidentSeverity.HIGH) is True
        assert cluster.severity is IncidentSeverity.HIGH
        assert cluster.escalate_severity(IncidentSeverity.MEDIUM) is False
        assert cluster.severity is IncidentSeverity.HIGH

    def test_close(self):
        cluster = _cluster()
        cluster.close()
        assert cluster.status == "CLOSED"

    def test_serialization_roundtrip(self):
        cluster = _cluster()
        cluster.add_member("INC-20260812-000002")
        cluster.escalate_severity(IncidentSeverity.CRITICAL)
        restored = IncidentCluster.from_dict(cluster.to_dict())
        assert restored == cluster
