"""Tests for Rollback Manager."""

import time
import pytest
from services.mlops.rollback import (
    RollbackManager, RollbackConfig, RollbackRule,
    RollbackEvent, RollbackStatus,
)


class TestRollbackRule:
    """Unit tests for RollbackRule."""

    def test_error_rate_triggered(self):
        rule = RollbackRule(
            name="error_test",
            metric="error_rate",
            operator=">",
            threshold=2.5,
        )
        # 15% vs 5% baseline → factor = 3.0 > 2.5
        assert rule.evaluate(0.15, 0.05) is True
        # 10% vs 5% baseline → factor = 2.0 < 2.5
        assert rule.evaluate(0.10, 0.05) is False

    def test_sharpe_triggered(self):
        rule = RollbackRule(
            name="sharpe_test",
            metric="sharpe",
            operator="<",
            threshold=0.3,
        )
        assert rule.evaluate(0.2) is True
        assert rule.evaluate(0.5) is False

    def test_disabled_rule(self):
        rule = RollbackRule(
            name="disabled_test",
            metric="error_rate",
            operator=">",
            threshold=1.0,
            enabled=False,
        )
        assert rule.evaluate(0.5, 0.1) is False


class TestRollbackManager:
    """Unit tests for RollbackManager."""

    @pytest.fixture
    def config(self):
        return RollbackConfig(
            max_error_rate=0.05,
            error_spike_factor=3.0,
            cool_down_seconds=0.0,
            require_confirmation=False,
        )

    @pytest.fixture
    def manager(self, config):
        return RollbackManager(config)

    # ------------------------------------------------------------------
    # Model Registration
    # ------------------------------------------------------------------

    def test_register_model(self, manager):
        manager.register_model("Alpha_v38", "1.0.0")
        assert manager.get_current_version("Alpha_v38") == "1.0.0"

    def test_register_multiple_versions(self, manager):
        manager.register_model("Alpha_v38", "1.0.0")
        manager.add_version("Alpha_v38", "1.0.1")
        manager.add_version("Alpha_v38", "1.0.2")

        history = manager.get_version_history("Alpha_v38")
        assert len(history) == 3
        assert "1.0.0" in history
        assert "1.0.2" in history

    # ------------------------------------------------------------------
    # Metric Recording & Rollback
    # ------------------------------------------------------------------

    def test_record_metric_no_trigger(self, manager):
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02}
        )
        # Normal error rate — should not trigger
        event = manager.record_metric("Alpha_v38", "error_rate", 0.03)
        assert event is None

    def test_record_metric_triggers_rollback(self, manager):
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02}
        )
        manager.add_version("Alpha_v38", "0.9.0")

        # Spike: 15% vs 2% baseline → 7.5x > 3x threshold
        event = manager.record_metric("Alpha_v38", "error_rate", 0.15)
        assert event is not None
        assert event.model_name == "Alpha_v38"
        assert event.status == RollbackStatus.COMPLETED

    def test_record_metric_unregistered_model(self, manager):
        event = manager.record_metric("Unknown", "error_rate", 0.5)
        assert event is None

    def test_record_metric_sharpe_collapse(self, manager):
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"sharpe": 2.0}
        )
        manager.add_version("Alpha_v38", "0.9.0")

        event = manager.record_metric("Alpha_v38", "sharpe", 0.1)
        # Should trigger rollback (below 0.3 threshold)
        assert event is not None

    def test_check_all_metrics(self, manager):
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02, "sharpe": 2.0}
        )
        manager.add_version("Alpha_v38", "0.9.0")

        events = manager.check_all_metrics(
            "Alpha_v38",
            {"error_rate": 0.03, "sharpe": 1.8},  # Normal values
        )
        assert len(events) == 0

    # ------------------------------------------------------------------
    # Manual Rollback
    # ------------------------------------------------------------------

    def test_manual_rollback(self, manager):
        manager.register_model("Alpha_v38", "1.0.0")
        manager.add_version("Alpha_v38", "0.9.0")

        event = manager.rollback(
            "Alpha_v38",
            to_version="0.9.0",
            reason="Manual test rollback",
        )
        assert event is not None
        assert event.from_version == "1.0.0"
        assert event.to_version == "0.9.0"
        assert event.triggered_rule == "manual"

    def test_manual_rollback_unregistered(self, manager):
        event = manager.rollback("Unknown", reason="test")
        assert event is None

    def test_manual_rollback_no_previous(self, manager):
        manager.register_model("Alpha_v38", "1.0.0")
        # Only one version
        event = manager.rollback("Alpha_v38", reason="test")
        assert event is None

    # ------------------------------------------------------------------
    # Rules Management
    # ------------------------------------------------------------------

    def test_add_custom_rule(self, manager):
        rule = RollbackRule(
            name="custom_test",
            metric="turnover",
            operator=">",
            threshold=0.8,
        )
        manager.add_rule(rule)
        assert "custom_test" in [r.name for r in manager.get_rules()]

    def test_remove_rule(self, manager):
        assert manager.remove_rule("error_rate_spike") is True
        assert manager.remove_rule("nonexistent") is False

    def test_enable_disable_rule(self, manager):
        assert manager.enable_rule("error_rate_spike", False) is True
        rules = manager.get_rules()
        error_rule = [r for r in rules if r.name == "error_rate_spike"][0]
        assert error_rule.enabled is False

        assert manager.enable_rule("error_rate_spike", True) is True
        rules = manager.get_rules()
        error_rule = [r for r in rules if r.name == "error_rate_spike"][0]
        assert error_rule.enabled is True

    # ------------------------------------------------------------------
    # Cooldown
    # ------------------------------------------------------------------

    def test_cooldown_prevents_rollback(self, manager):
        manager.config.cool_down_seconds = 3600.0  # 1 hour
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02}
        )
        manager.add_version("Alpha_v38", "0.9.0")

        # First rollback
        manager.record_metric("Alpha_v38", "error_rate", 0.15)
        assert manager.is_in_cooldown("Alpha_v38") is True

        # Second should be blocked
        event = manager.record_metric("Alpha_v38", "error_rate", 0.15)
        assert event is None

    # ------------------------------------------------------------------
    # Events & History
    # ------------------------------------------------------------------

    def test_get_events(self, manager):
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02}
        )
        manager.add_version("Alpha_v38", "0.9.0")
        event = manager.record_metric("Alpha_v38", "error_rate", 0.15)

        # Event should have been triggered
        assert event is not None
        events = manager.get_events("Alpha_v38")
        assert len(events) >= 1

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def test_rollback_callback(self, manager):
        events = []

        def on_rollback(event):
            events.append(event)

        manager.on_rollback(on_rollback)
        manager.register_model(
            "Alpha_v38", "1.0.0",
            baseline_metrics={"error_rate": 0.02}
        )
        manager.add_version("Alpha_v38", "0.9.0")
        manager.record_metric("Alpha_v38", "error_rate", 0.15)

        assert len(events) == 1

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def test_reset(self, manager):
        manager.register_model("Alpha_v38", "1.0.0")
        manager.reset()
        assert manager.get_current_version("Alpha_v38") is None
