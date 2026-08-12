"""Unit tests: IncidentSeverity rank, escalation and comparison rules."""

from __future__ import annotations

import pytest

from services.control_plane.incident.incident_severity import IncidentSeverity


class TestSeverityRank:
    def test_rank_order(self):
        assert IncidentSeverity.INFO.rank == 0
        assert IncidentSeverity.LOW.rank == 1
        assert IncidentSeverity.MEDIUM.rank == 2
        assert IncidentSeverity.HIGH.rank == 3
        assert IncidentSeverity.CRITICAL.rank == 4
        assert IncidentSeverity.FATAL.rank == 5

    def test_priority_chain(self):
        order = [
            IncidentSeverity.INFO,
            IncidentSeverity.LOW,
            IncidentSeverity.MEDIUM,
            IncidentSeverity.HIGH,
            IncidentSeverity.CRITICAL,
            IncidentSeverity.FATAL,
        ]
        for low, high in zip(order, order[1:]):
            assert low < high


class TestEscalationRules:
    def test_escalation_allowed(self):
        assert IncidentSeverity.MEDIUM.can_escalate_to(IncidentSeverity.HIGH)
        assert IncidentSeverity.HIGH.can_escalate_to(IncidentSeverity.CRITICAL)
        assert IncidentSeverity.CRITICAL.can_escalate_to(IncidentSeverity.FATAL)

    def test_same_severity_not_escalation(self):
        assert not IncidentSeverity.HIGH.can_escalate_to(IncidentSeverity.HIGH)

    def test_downgrade_not_an_escalation(self):
        assert not IncidentSeverity.CRITICAL.can_escalate_to(IncidentSeverity.MEDIUM)

    def test_degrade_capability_detected(self):
        assert IncidentSeverity.CRITICAL.can_degrade_to(IncidentSeverity.MEDIUM)
        assert not IncidentSeverity.MEDIUM.can_degrade_to(IncidentSeverity.HIGH)

    def test_non_severity_rejected(self):
        with pytest.raises(TypeError):
            IncidentSeverity.HIGH.can_escalate_to("MEDIUM")  # type: ignore[arg-type]


class TestSeverityComparison:
    def test_gt_and_ge(self):
        assert IncidentSeverity.CRITICAL > IncidentSeverity.HIGH
        assert IncidentSeverity.FATAL >= IncidentSeverity.FATAL

    def test_lt_and_le(self):
        assert IncidentSeverity.LOW < IncidentSeverity.MEDIUM
        assert IncidentSeverity.MEDIUM <= IncidentSeverity.MEDIUM

    def test_string_comparison(self):
        assert IncidentSeverity.CRITICAL >= "CRITICAL"
        assert IncidentSeverity.HIGH > "MEDIUM"
