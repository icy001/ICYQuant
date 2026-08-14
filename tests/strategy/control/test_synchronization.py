"""Tests for strategy / runtime synchronization."""

from __future__ import annotations

from services.strategy.control.synchronization import (
    ReconciliationResult,
    ReconciliationStatus,
    StrategyRuntimeSynchronizer,
    is_consistent,
    status_for,
)


class TestSynchronizationMatrix:
    def setup_method(self) -> None:
        self.synchronizer = StrategyRuntimeSynchronizer()

    def reconcile(self, control: str, runtime: str) -> ReconciliationResult:
        return self.synchronizer.reconcile(control, runtime, "STRAT-001")

    def test_stopped_stopped_is_healthy(self) -> None:
        result = self.reconcile("STOPPED", "STOPPED")
        assert result.status == ReconciliationStatus.HEALTHY.value
        assert result.consistent is True

    def test_running_running_is_healthy(self) -> None:
        result = self.reconcile("RUNNING", "RUNNING")
        assert result.status == "HEALTHY"

    def test_paused_running_is_degraded(self) -> None:
        result = self.reconcile("PAUSED", "RUNNING")
        assert result.status == "DEGRADED"

    def test_stopping_stopping_is_healthy(self) -> None:
        result = self.reconcile("STOPPING", "STOPPING")
        assert result.status == "HEALTHY"

    def test_running_stopped_is_recovery(self) -> None:
        result = self.reconcile("RUNNING", "STOPPED")
        assert result.status == "RECOVERY_REQUIRED"
        assert result.consistent is False

    def test_runtime_timeout_becomes_unknown(self) -> None:
        result = self.reconcile("RUNNING", "UNKNOWN")
        assert result.status == "RECOVERY_REQUIRED"

    def test_killed_running_runtime_is_critical(self) -> None:
        result = self.reconcile("KILLED", "RUNNING")
        assert result.status == "CRITICAL"
        assert result.consistent is False

    def test_running_degraded_is_degraded(self) -> None:
        result = self.reconcile("RUNNING", "DEGRADED")
        assert result.status == "DEGRADED"

    def test_unknown_combination_defaults_to_recovery(self) -> None:
        result = self.reconcile("RESUMING", "FAILED")
        assert result.status == "RECOVERY_REQUIRED"

    def test_killed_stopped_is_healthy(self) -> None:
        result = self.reconcile("KILLED", "STOPPED")
        assert result.status == "HEALTHY"

    def test_result_carries_context(self) -> None:
        result = self.reconcile("RUNNING", "UNKNOWN")
        assert result.strategy_id == "STRAT-001"
        assert result.control_state == "RUNNING"
        assert result.runtime_state == "UNKNOWN"


class TestHelpers:
    def test_status_for(self) -> None:
        assert status_for("RUNNING", "RUNNING") == "HEALTHY"
        assert status_for("KILLED", "RUNNING") == "CRITICAL"
        assert status_for("RUNNING", "UNKNOWN") == "RECOVERY_REQUIRED"

    def test_is_consistent(self) -> None:
        assert is_consistent("HEALTHY") is True
        assert is_consistent("DEGRADED") is True
        assert is_consistent("RECOVERY_REQUIRED") is False
        assert is_consistent("CRITICAL") is False
