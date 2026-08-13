"""Runbook model tests (Commit 27 Part 1.5, spec sections 3-4)."""

import pytest

from services.operations import Runbook, RunbookSeverity


def test_runbook_severity_values():

    assert RunbookSeverity.STANDARD.value == "STANDARD"
    assert RunbookSeverity.ELEVATED.value == "ELEVATED"
    assert RunbookSeverity.CRITICAL.value == "CRITICAL"
    assert RunbookSeverity.EMERGENCY.value == "EMERGENCY"


def test_runbook_default_enabled():

    runbook = Runbook(
        runbook_id="RB-RECON-001",
        name="Reconciliation Difference",
        description="Position / Ledger mismatch",
        severity=RunbookSeverity.CRITICAL,
        version="1.2.0",
    )

    assert runbook.enabled is True


def test_runbook_version_is_auditable(runbook_meta):

    assert runbook_meta.runbook_id == "RB-TEST-001"
    assert runbook_meta.version == "1.0.0"


def test_runbook_is_frozen():

    runbook = Runbook(
        runbook_id="RB-001",
        name="Test",
        description="Test",
        severity=RunbookSeverity.STANDARD,
        version="1.0.0",
    )

    with pytest.raises(Exception):
        runbook.version = "2.0.0"
