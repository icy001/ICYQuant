"""Control metrics tests (Commit 29 Part 1.5 §19-24)."""

from __future__ import annotations

from services.control_plane.metrics import ControlMetrics, ControlMetricsSnapshot


def test_counters_are_split_by_stage():
    metrics = ControlMetrics()
    metrics.record_submitted()
    metrics.record_authorized()
    metrics.record_executed()
    metrics.record_succeeded(0.12)

    snapshot = metrics.snapshot()
    assert snapshot.submitted == 1
    assert snapshot.authorized == 1
    assert snapshot.rejected == 0
    assert snapshot.executed == 1
    assert snapshot.succeeded == 1
    assert snapshot.failed == 0


def test_authorization_rejection_is_not_execution_failure():
    metrics = ControlMetrics()
    metrics.record_submitted()
    metrics.record_rejected()
    snapshot = metrics.snapshot()
    assert snapshot.rejected == 1
    assert snapshot.failed == 0
    assert snapshot.success_rate == 0.0


def test_success_rate():
    metrics = ControlMetrics()
    for _ in range(8):
        metrics.record_submitted()
        metrics.record_succeeded()
    for _ in range(2):
        metrics.record_submitted()
        metrics.record_failed()
    assert metrics.success_rate() == 0.8


def test_timeout_rate():
    metrics = ControlMetrics()
    for _ in range(5):
        metrics.record_executed()
    metrics.record_executed()
    metrics.record_timeout()
    assert metrics.timeout_rate() == 1 / 6


def test_recovery_and_duplicate_rates():
    metrics = ControlMetrics()
    for _ in range(10):
        metrics.record_submitted()
    metrics.record_recovery()
    metrics.record_duplicate()
    metrics.record_duplicate()
    assert metrics.recovery_rate() == 0.1
    assert metrics.duplicate_rate() == 0.2


def test_latency_percentiles():
    metrics = ControlMetrics()
    metrics.record_submitted()
    metrics.record_succeeded(0.1)
    metrics.record_succeeded(0.2)
    metrics.record_succeeded(0.5)
    metrics.record_succeeded(1.0)
    snapshot = metrics.snapshot()
    assert snapshot.command_latency_p50 == 0.2
    assert snapshot.command_latency_p95 == 1.0
    assert snapshot.command_latency_p99 == 1.0


def test_empty_snapshot_is_safe():
    snapshot = ControlMetricsSnapshot()
    assert snapshot.success_rate == 0.0
    assert snapshot.timeout_rate == 0.0
    assert snapshot.recovery_rate == 0.0
    assert snapshot.duplicate_rate == 0.0
    assert snapshot.command_latency_p95 == 0.0


def test_all_safety_counters():
    metrics = ControlMetrics()
    metrics.record_idempotency_conflict()
    metrics.record_replay_rejection()
    metrics.record_claim_conflict()
    metrics.record_version_conflict()
    snapshot = metrics.snapshot()
    assert snapshot.idempotency_conflicts == 1
    assert snapshot.replay_rejections == 1
    assert snapshot.claim_conflicts == 1
    assert snapshot.version_conflicts == 1
