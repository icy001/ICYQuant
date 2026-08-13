"""Incident severity tests (Commit 27 Part 1.4, spec section 3)."""

from __future__ import annotations

from services.operations import IncidentSeverity


def test_severity_ordering():

    assert (
        IncidentSeverity.MINOR
        < IncidentSeverity.MODERATE
        < IncidentSeverity.MAJOR
        < IncidentSeverity.CRITICAL
        < IncidentSeverity.CATASTROPHIC
    )


def test_severity_numeric_values():

    assert IncidentSeverity.MINOR.value == 1
    assert IncidentSeverity.MODERATE.value == 2
    assert IncidentSeverity.MAJOR.value == 3
    assert IncidentSeverity.CRITICAL.value == 4
    assert IncidentSeverity.CATASTROPHIC.value == 5


def test_severity_is_int_enum():

    assert int(IncidentSeverity.CRITICAL) == 4
    assert isinstance(
        IncidentSeverity.CATASTROPHIC,
        int,
    )
