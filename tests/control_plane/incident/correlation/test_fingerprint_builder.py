"""FingerprintBuilder — stable deduplication keys."""
from __future__ import annotations

from services.control_plane.incident.correlation.fingerprint_builder import (
    FingerprintBuilder,
)
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


def _build(builder, **kwargs):
    return builder.build(
        event_type=kwargs.pop("event_type", "HEALTH_MONITOR_DOWN"),
        incident_type=kwargs.pop("incident_type", IncidentType.HEALTH_FAILURE),
        source=kwargs.pop("source", IncidentSource.HEALTH_MONITOR),
        scope=kwargs.pop("scope", IncidentScope.SERVICE),
        service=kwargs.pop("service", "gateway"),
        account=kwargs.pop("account", ""),
        strategy=kwargs.pop("strategy", ""),
        instrument=kwargs.pop("instrument", ""),
        venue=kwargs.pop("venue", ""),
    )


class TestFingerprintBuilder:
    def test_event_type_is_excluded(self):
        builder = FingerprintBuilder()
        f1 = _build(builder, event_type="HEALTH_MONITOR_DOWN")
        f2 = _build(builder, event_type="SERVICE_RESTARTING")
        assert f1.value == f2.value

    def test_scope_id_changes_fingerprint(self):
        builder = FingerprintBuilder()
        assert (
            _build(builder, service="gateway").value
            != _build(builder, service="execution").value
        )

    def test_incident_type_changes_fingerprint(self):
        builder = FingerprintBuilder()
        assert (
            _build(builder, incident_type=IncidentType.HEALTH_FAILURE).value
            != _build(builder, incident_type=IncidentType.RISK_BREACH).value
        )

    def test_source_changes_fingerprint(self):
        builder = FingerprintBuilder()
        assert (
            _build(builder, source=IncidentSource.HEALTH_MONITOR).value
            != _build(builder, source=IncidentSource.RISK_ENGINE).value
        )

    def test_service_takes_precedence_for_scope_id(self):
        builder = FingerprintBuilder()
        f1 = _build(builder, service="gateway", account="acc-1")
        f2 = _build(builder, service="gateway")
        assert f1.value == f2.value

    def test_returns_incident_fingerprint(self):
        builder = FingerprintBuilder()
        fingerprint = _build(builder)
        assert fingerprint.value
        assert fingerprint.incident_type is IncidentType.HEALTH_FAILURE
