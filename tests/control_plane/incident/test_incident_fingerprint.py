"""Unit tests: IncidentFingerprint deduplication keys."""

from __future__ import annotations

from services.control_plane.incident.incident_fingerprint import IncidentFingerprint
from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


def fp(source, itype, scope=None, scope_id=None):
    return IncidentFingerprint(source=source, incident_type=itype, scope=scope, scope_id=scope_id)


class TestFingerprintStability:
    def test_same_components_same_fingerprint(self):
        a = fp(IncidentSource.POSITION_SERVICE, IncidentType.POSITION_INTEGRITY_FAILURE)
        b = fp(IncidentSource.POSITION_SERVICE, IncidentType.POSITION_INTEGRITY_FAILURE)
        assert a == b
        assert a.value == b.value

    def test_matches_same_components(self):
        a = fp(IncidentSource.POSITION_SERVICE, IncidentType.POSITION_INTEGRITY_FAILURE)
        b = fp(IncidentSource.POSITION_SERVICE, IncidentType.POSITION_INTEGRITY_FAILURE)
        assert a.matches(b)

    def test_scoped_fingerprint_differs(self):
        a = fp(
            IncidentSource.POSITION_SERVICE,
            IncidentType.POSITION_INTEGRITY_FAILURE,
            IncidentScope.STRATEGY,
            "ALPHA",
        )
        b = fp(
            IncidentSource.POSITION_SERVICE,
            IncidentType.POSITION_INTEGRITY_FAILURE,
            IncidentScope.STRATEGY,
            "BETA",
        )
        assert a != b
        assert not a.matches(b)


class TestFingerprintDiscrimination:
    def test_different_source_differs(self):
        a = fp(IncidentSource.RISK_ENGINE, IncidentType.RISK_BREACH)
        b = fp(IncidentSource.RECONCILIATION, IncidentType.RISK_BREACH)
        assert a != b

    def test_different_type_differs(self):
        a = fp(IncidentSource.POSITION_SERVICE, IncidentType.POSITION_INTEGRITY_FAILURE)
        b = fp(IncidentSource.POSITION_SERVICE, IncidentType.MARKET_DATA_FAILURE)
        assert a != b

    def test_scope_affects_fingerprint(self):
        a = fp(
            IncidentSource.RECONCILIATION,
            IncidentType.RECONCILIATION_FAILURE,
            IncidentScope.GLOBAL,
        )
        b = fp(
            IncidentSource.RECONCILIATION,
            IncidentType.RECONCILIATION_FAILURE,
            IncidentScope.STRATEGY,
            "ALPHA",
        )
        assert a != b

    def test_fingerprint_is_short_hash(self):
        value = fp(IncidentSource.HEALTH_MONITOR, IncidentType.HEALTH_FAILURE).value
        assert len(value) == 16
        assert all(c in "0123456789abcdef" for c in value)


class TestFingerprintSerialization:
    def test_round_trip(self):
        f = fp(
            IncidentSource.RECONCILIATION,
            IncidentType.RECONCILIATION_FAILURE,
            IncidentScope.STRATEGY,
            "ALPHA",
        )
        restored = IncidentFingerprint.from_dict(f.to_dict())
        assert restored == f
        assert restored.matches(f)
