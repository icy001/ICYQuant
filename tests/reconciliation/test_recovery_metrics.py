"""Tests for recovery metrics."""

from services.reconciliation.recovery_metrics import RecoveryMetrics


def test_initial_metrics_are_zero():
    metrics = RecoveryMetrics()

    assert metrics.reconciliation_total == 0
    assert metrics.reconciliation_matched == 0
    assert metrics.reconciliation_mismatched == 0
    assert metrics.repair_total == 0
    assert metrics.recovery_total == 0
    assert metrics.manual_review_total == 0
    assert metrics.repair_success_rate == 0.0
    assert metrics.recovery_success_rate == 0.0


def test_record_matched_reconciliation():
    metrics = RecoveryMetrics()

    metrics.record_reconciliation(matched=True)

    assert metrics.reconciliation_total == 1
    assert metrics.reconciliation_matched == 1
    assert metrics.reconciliation_mismatched == 0


def test_record_mismatched_reconciliation():
    metrics = RecoveryMetrics()

    metrics.record_reconciliation(matched=False)

    assert metrics.reconciliation_total == 1
    assert metrics.reconciliation_matched == 0
    assert metrics.reconciliation_mismatched == 1


def test_record_repair_success():
    metrics = RecoveryMetrics()

    metrics.record_repair(success=True)

    assert metrics.repair_total == 1
    assert metrics.repair_success_total == 1
    assert metrics.repair_failed_total == 0


def test_record_repair_failed():
    metrics = RecoveryMetrics()

    metrics.record_repair(success=False)

    assert metrics.repair_total == 1
    assert metrics.repair_success_total == 0
    assert metrics.repair_failed_total == 1


def test_record_recovery_success():
    metrics = RecoveryMetrics()

    metrics.record_recovery(success=True)

    assert metrics.recovery_total == 1
    assert metrics.recovery_success_total == 1
    assert metrics.recovery_failed_total == 0


def test_record_recovery_failed():
    metrics = RecoveryMetrics()

    metrics.record_recovery(success=False)

    assert metrics.recovery_total == 1
    assert metrics.recovery_success_total == 0
    assert metrics.recovery_failed_total == 1


def test_record_manual_review():
    metrics = RecoveryMetrics()

    metrics.record_manual_review()
    metrics.record_manual_review()

    assert metrics.manual_review_total == 2


def test_repair_success_rate():
    metrics = RecoveryMetrics()

    metrics.record_repair(success=True)
    metrics.record_repair(success=True)
    metrics.record_repair(success=False)

    assert metrics.repair_total == 3
    assert metrics.repair_success_rate == 2 / 3


def test_recovery_success_rate():
    metrics = RecoveryMetrics()

    metrics.record_recovery(success=True)
    metrics.record_recovery(success=False)

    assert metrics.recovery_total == 2
    assert metrics.recovery_success_rate == 0.5
