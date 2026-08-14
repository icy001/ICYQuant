"""Observability facade and telemetry tests (Commit 29 Part 1.5 §13-18, §25, §54-55)."""

from __future__ import annotations

from services.control_plane.alerts import AlertRule, AlertSeverity, ControlAlertEvaluator
from services.control_plane.audit_event import AuditEventType, AuditTrail, verify_audit_chain
from services.control_plane.control_health import ControlPlaneHealth
from services.control_plane.diagnostics import ControlPlaneDiagnostics
from services.control_plane.event import InMemoryEventStore
from services.control_plane.metrics import ControlMetrics
from services.control_plane.observability import ControlPlaneObservability
from services.control_plane.telemetry import ControlPlaneTelemetry, RetryStormDetector
from services.control_plane.tracing import ControlTrace


def _observability() -> ControlPlaneObservability:
    return ControlPlaneObservability(
        audit=AuditTrail(),
        events=InMemoryEventStore(),
        metrics=ControlMetrics(),
        tracer=ControlTrace(),
    )


def test_command_created_produces_audit_event():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    events = obs.audit.events("CMD-001")
    assert any(e.event_type == AuditEventType.COMMAND_CREATED for e in events)
    assert any(e.event_type == "COMMAND_CREATED" for e in events)
    created = next(e for e in events if e.event_type == AuditEventType.COMMAND_CREATED)
    assert created.principal_id == "operator-001"
    assert obs.metrics.snapshot().submitted == 1


def test_command_created_emits_fact_event_and_trace():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    fact_events = obs.events.events("CMD-001")
    assert [event.event_type for event in fact_events] == ["COMMAND_CREATED"]
    assert len(obs.tracer.spans()) == 1
    assert obs.tracer.spans()[0].name == "control.command"


def test_authorization_grant_audited():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    obs.record_authorization(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
        decision="ALLOW",
        reason="policy_allowed",
        policy="production-control-policy",
        grant_id="GRANT-001",
    )
    granted = obs.audit.events("CMD-001")[-1]
    assert granted.decision == "ALLOW"
    assert granted.reason == "policy_allowed"
    assert granted.detail["grant_id"] == "GRANT-001"
    assert granted.detail["policy"] == "production-control-policy"
    assert obs.metrics.snapshot().authorized == 1
    assert obs.events.events("CMD-001")[-1].event_type == "AUTHORIZATION_GRANTED"


def test_authorization_rejection_is_audited_too():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    obs.record_authorization(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
        decision="DENY",
        reason="insufficient_scope",
    )
    rejected = obs.audit.events("CMD-001")[-1]
    assert rejected.event_type == AuditEventType.AUTHORIZATION_REJECTED
    assert rejected.reason == "insufficient_scope"
    snapshot = obs.metrics.snapshot()
    assert snapshot.rejected == 1
    assert snapshot.failed == 0  # never conflated with execution failure


def test_execution_audit_records_worker_and_claim():
    obs = _observability()
    obs.record_execution_started(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        worker_id="worker-42",
        claim_id="CLAIM-001",
        fencing_token=7,
        attempt_number=1,
    )
    started = obs.audit.events("CMD-001")[0]
    assert started.detail["worker_id"] == "worker-42"
    assert started.detail["claim_id"] == "CLAIM-001"
    assert started.detail["fencing_token"] == 7
    assert started.detail["attempt_number"] == 1
    assert obs.metrics.snapshot().executed == 1


def test_recovery_has_causation_chain():
    obs = _observability()
    timeout_event = obs.events.append(
        event_type="EXECUTION_TIMEOUT",
        command_id="CMD-001",
        correlation_id="CORR-001",
    )
    obs.record_recovery_started(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        causation_id=timeout_event.event_id,
    )
    recovery_events = [
        event for event in obs.events.events("CMD-001") if event.event_type == "RECOVERY_STARTED"
    ]
    assert len(recovery_events) == 1
    assert recovery_events[0].causation_id == timeout_event.event_id


def test_full_audit_chain_verifies():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    obs.record_authorization(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
        decision="ALLOW",
        reason="policy_allowed",
    )
    obs.record_execution_started(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        worker_id="worker-1",
        claim_id="CLAIM-1",
        fencing_token=1,
        attempt_number=1,
    )
    obs.record_execution_timeout(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        timeout_seconds=10,
    )
    obs.record_recovery_started(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
    )
    obs.record_target_reconciled(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        target_state="PAUSED",
    )
    obs.record_recovery_completed(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
        succeeded=True,
    )
    obs.record_command_succeeded(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
    )
    assert obs.audit.verify() is True
    assert verify_audit_chain(obs.audit.events("CMD-001")) is True
    assert len(obs.events.events("CMD-001")) == 8
    snapshot = obs.metrics.snapshot()
    assert snapshot.recovery_success == 1
    assert snapshot.timeouts == 1


def test_sensitive_parameters_are_redacted_in_audit_detail():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
        parameters={"severity": "high", "broker_password": "secret"},
    )
    created = next(
        e for e in obs.audit.events("CMD-001") if e.event_type == AuditEventType.COMMAND_CREATED
    )
    params = created.detail["parameters"]
    assert params["severity"] == "high"
    assert params["broker_password"] == "[REDACTED]"


def test_retry_storm_detection():
    detector = RetryStormDetector(window_size=10, threshold=0.5)
    for _ in range(4):
        assert detector.record(False) is False
    for _ in range(6):
        detector.record(True)
    assert detector.is_storm() is True
    assert detector.duplicate_rate() == 0.6


def test_telemetry_snapshot_and_alerts():
    obs = _observability()
    obs.record_command_created(
        command_id="CMD-001",
        action="trading:pause",
        resource="trading",
        target="oms-primary",
        principal_id="operator-001",
        correlation_id="CORR-001",
    )
    obs.record_command_succeeded(
        command_id="CMD-001",
        action="trading:pause",
        target="oms-primary",
        correlation_id="CORR-001",
    )
    telemetry = ControlPlaneTelemetry(
        diagnostics=ControlPlaneDiagnostics(command_states=["SUCCEEDED"]),
        metrics=obs.metrics,
        health=ControlPlaneHealth(),
        alerts=ControlAlertEvaluator(),
        retry_storm=RetryStormDetector(window_size=10, threshold=0.5),
    )
    snapshot = telemetry.snapshot()
    assert snapshot.success_rate == 1.0
    assert snapshot.retry_storm is False

    for _ in range(6):
        telemetry.record_request(True)
    assert telemetry.retry_storm.is_storm() is True
    alerts = telemetry.evaluate_alerts()
    storm_alerts = [a for a in alerts if a.rule == AlertRule.DUPLICATE_RATE_HIGH]
    assert storm_alerts
    assert storm_alerts[-1].severity is AlertSeverity.CRITICAL
