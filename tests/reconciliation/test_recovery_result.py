"""Tests for the unified recovery result."""

import dataclasses

from services.reconciliation.lifecycle import ReconciliationLifecycle
from services.reconciliation.models.recovery_result import RecoveryResult


def test_recovered_result():
    result = RecoveryResult(
        reconciliation_id="REC-001",
        lifecycle=ReconciliationLifecycle.RECOVERED,
        repaired=True,
        verified=True,
        repair_id="REPAIR-001",
        reason="Recovered after verified repair",
    )

    assert result.reconciliation_id == "REC-001"
    assert result.lifecycle == ReconciliationLifecycle.RECOVERED
    assert result.repaired is True
    assert result.verified is True
    assert result.repair_id == "REPAIR-001"
    assert result.reason == "Recovered after verified repair"


def test_matched_result_has_no_repair():
    result = RecoveryResult(
        reconciliation_id="REC-002",
        lifecycle=ReconciliationLifecycle.MATCHED,
        repaired=False,
        verified=True,
        repair_id=None,
        reason="Reconciliation matched; no repair required",
    )

    assert result.lifecycle == ReconciliationLifecycle.MATCHED
    assert result.repaired is False
    assert result.verified is True
    assert result.repair_id is None


def test_manual_review_result():
    result = RecoveryResult(
        reconciliation_id="REC-003",
        lifecycle=ReconciliationLifecycle.MANUAL_REVIEW,
        repaired=False,
        verified=False,
        repair_id=None,
        reason="Manual review required",
    )

    assert result.lifecycle == ReconciliationLifecycle.MANUAL_REVIEW
    assert result.repaired is False
    assert result.verified is False


def test_failed_result():
    result = RecoveryResult(
        reconciliation_id="REC-004",
        lifecycle=ReconciliationLifecycle.FAILED,
        repaired=False,
        verified=False,
        repair_id="REPAIR-004",
        reason="rebuild failed",
    )

    assert result.lifecycle == ReconciliationLifecycle.FAILED
    assert result.repaired is False
    assert result.verified is False
    assert result.repair_id == "REPAIR-004"


def test_result_is_frozen():
    result = RecoveryResult(
        reconciliation_id="REC-005",
        lifecycle=ReconciliationLifecycle.RECOVERED,
        repaired=True,
        verified=True,
        repair_id=None,
        reason="ok",
    )

    try:
        result.repaired = False
    except (AttributeError, dataclasses.FrozenInstanceError):
        pass
    else:
        assert False, "RecoveryResult should be frozen"
