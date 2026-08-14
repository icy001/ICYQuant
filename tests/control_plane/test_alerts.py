"""Alert rules tests (Commit 29 Part 1.5 §26-28, §46)."""

from __future__ import annotations

from services.control_plane.alerts import (
    AlertRule,
    AlertSeverity,
    ControlAlertEvaluator,
    HIGH_RISK_ACTIONS,
    HIGH_RISK_STATES,
)
from services.control_plane.metrics import ControlMetricsSnapshot


def _snapshot(**overrides) -> ControlMetricsSnapshot:
    base = dict(
        submitted=100,
        authorized=90,
        rejected=10,
        executed=100,
        succeeded=100,
        failed=0,
        timeouts=0,
        recoveries=0,
        duplicates=0,
        idempotency_conflicts=0,
        replay_rejections=0,
        claim_conflicts=0,
        version_conflicts=0,
    )
    base.update(overrides)
    return ControlMetricsSnapshot(**base)


def test_failure_rate_high():
    evaluator = ControlAlertEvaluator({"failure_rate": 0.05})
    alerts = evaluator.evaluate_metrics(_snapshot(submitted=100, failed=10))
    rules = [alert.rule for alert in alerts]
    assert AlertRule.COMMAND_FAILURE_RATE_HIGH in rules


def test_timeout_rate_high():
    evaluator = ControlAlertEvaluator({"timeout_rate": 0.05})
    alerts = evaluator.evaluate_metrics(_snapshot(executed=100, timeouts=20))
    assert AlertRule.COMMAND_TIMEOUT_RATE_HIGH in [a.rule for a in alerts]


def test_recovery_rate_high():
    evaluator = ControlAlertEvaluator({"recovery_rate": 0.05})
    alerts = evaluator.evaluate_metrics(_snapshot(recoveries=10))
    assert AlertRule.RECOVERY_RATE_HIGH in [a.rule for a in alerts]


def test_duplicate_rate_high():
    evaluator = ControlAlertEvaluator({"duplicate_rate": 0.20})
    alerts = evaluator.evaluate_metrics(_snapshot(duplicates=30))
    assert AlertRule.DUPLICATE_RATE_HIGH in [a.rule for a in alerts]


def test_conflict_spikes():
    evaluator = ControlAlertEvaluator()
    alerts = evaluator.evaluate_metrics(
        _snapshot(
            idempotency_conflicts=20,
            replay_rejections=15,
            claim_conflicts=12,
            version_conflicts=11,
        )
    )
    rules = {alert.rule for alert in alerts}
    assert AlertRule.IDEMPOTENCY_CONFLICT_SPIKE in rules
    assert AlertRule.REPLAY_REJECTION_SPIKE in rules
    assert AlertRule.CLAIM_CONFLICT_SPIKE in rules
    assert AlertRule.VERSION_CONFLICT_SPIKE in rules


def test_healthy_snapshot_produces_no_alerts():
    evaluator = ControlAlertEvaluator()
    assert evaluator.evaluate_metrics(_snapshot()) == ()


def test_high_risk_command_failure_escalates():
    evaluator = ControlAlertEvaluator()
    alerts = evaluator.evaluate_command(
        command_id="CMD-001",
        action="trading:kill",
        target="oms-primary",
        principal="operator-001",
        attempt=2,
        state="FAILED",
        error="TARGET_UNAVAILABLE",
        correlation_id="INC-2026-0813-001",
    )
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.rule == AlertRule.HIGH_RISK_COMMAND_FAILURE
    assert alert.severity is AlertSeverity.HIGH
    assert alert.context["command_id"] == "CMD-001"
    assert alert.context["action"] == "trading:kill"
    assert alert.context["attempt"] == 2
    assert alert.context["state"] == "FAILED"
    assert alert.context["error"] == "TARGET_UNAVAILABLE"
    assert alert.context["correlation_id"] == "INC-2026-0813-001"


def test_high_risk_unknown_and_recovery_states_escalate():
    evaluator = ControlAlertEvaluator()
    for state in HIGH_RISK_STATES:
        alerts = evaluator.evaluate_command(
            command_id="CMD-X", action="position:rebuild", target="t", state=state
        )
        assert len(alerts) == 1, state
        assert alerts[0].severity is AlertSeverity.HIGH


def test_non_high_risk_command_failure_does_not_escalate():
    evaluator = ControlAlertEvaluator()
    alerts = evaluator.evaluate_command(
        command_id="CMD-001",
        action="system:refresh_cache",
        target="cache-1",
        state="FAILED",
    )
    assert alerts == ()


def test_safe_state_does_not_escalate_even_for_high_risk():
    evaluator = ControlAlertEvaluator()
    alerts = evaluator.evaluate_command(
        command_id="CMD-001",
        action="trading:kill",
        target="oms-primary",
        state="SUCCEEDED",
    )
    assert alerts == ()


def test_audit_integrity_failure_is_critical():
    evaluator = ControlAlertEvaluator()
    alert = evaluator.evaluate_audit_integrity(verified=False)
    assert alert is not None
    assert alert.rule == AlertRule.AUDIT_INTEGRITY_FAILURE
    assert alert.severity is AlertSeverity.CRITICAL


def test_audit_integrity_ok_is_silent():
    evaluator = ControlAlertEvaluator()
    assert evaluator.evaluate_audit_integrity(verified=True) is None


def test_high_risk_actions_registry():
    assert "trading:kill" in HIGH_RISK_ACTIONS
    assert "order:cancel_all" in HIGH_RISK_ACTIONS
    assert "ledger:repair" in HIGH_RISK_ACTIONS
    assert "position:rebuild" in HIGH_RISK_ACTIONS
