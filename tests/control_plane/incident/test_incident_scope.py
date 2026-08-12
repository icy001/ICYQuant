"""Unit tests: IncidentScope enumeration and source/type dimensions."""

from __future__ import annotations

from services.control_plane.incident.incident_scope import IncidentScope
from services.control_plane.incident.incident_source import IncidentSource
from services.control_plane.incident.incident_type import IncidentType


class TestIncidentScope:
    def test_has_six_scopes(self):
        scopes = [s.value for s in IncidentScope]
        assert scopes == [
            "GLOBAL",
            "SERVICE",
            "ACCOUNT",
            "STRATEGY",
            "INSTRUMENT",
            "VENUE",
        ]

    def test_str_enum(self):
        assert IncidentScope.STRATEGY.value == "STRATEGY"
        assert IncidentScope.STRATEGY == "STRATEGY"
        assert IncidentScope("STRATEGY") is IncidentScope.STRATEGY


class TestIncidentSource:
    def test_has_ten_sources(self):
        sources = [s.value for s in IncidentSource]
        assert len(sources) == 10
        assert "RECONCILIATION" in sources
        assert "MANUAL" in sources

    def test_parse(self):
        assert IncidentSource("POLICY_ENGINE") is IncidentSource.POLICY_ENGINE


class TestIncidentType:
    def test_has_twelve_types(self):
        types = [t.value for t in IncidentType]
        assert len(types) == 12
        assert "POSITION_INTEGRITY_FAILURE" in types
        assert "LEDGER_INTEGRITY_FAILURE" in types
        assert "RECONCILIATION_FAILURE" in types
        assert "SECURITY_FAILURE" in types

    def test_type_describes_what_not_how_bad(self):
        # Type and severity are independent dimensions.
        assert IncidentType.RECONCILIATION_FAILURE.value != "CRITICAL"
