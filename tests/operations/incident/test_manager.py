"""Incident manager tests (Commit 27 Part 1.4, spec sections 11-17, 23-25, 30-31, 34)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.operations import (
    Alert,
    AlertSeverity,
    AlertState,
    IncidentImpact,
    IncidentManager,
    IncidentSeverity,
    IncidentState,
    build_correlation_key,
    map_alert_severity,
    should_open_incident,
)

TRIAGED = IncidentState.TRIAGED
INVESTIGATING = IncidentState.INVESTIGATING
MITIGATING = IncidentState.MITIGATING
RECOVERING = IncidentState.RECOVERING
MONITORING = IncidentState.MONITORING
RESOLVED = IncidentState.RESOLVED
CLOSED = IncidentState.CLOSED

RECOVERY_OK = {
    "service_health": True,
    "risk_state": True,
    "position_state": True,
    "ledger_state": True,
    "reconciliation": True,
    "execution": True,
    "venue": True,
}


def _impact(**overrides):

    fields = {
        "affected_services": ("risk",),
        "affected_venues": (),
        "affected_strategies": (),
        "affected_orders": 10,
        "affected_positions": 2,
        "trading_blocked": True,
    }

    fields.update(overrides)

    return IncidentImpact(**fields)


def _alert(
    alert_id="ALT-000001",
    severity=AlertSeverity.CRITICAL,
    labels=None,
    service_id="reconciliation",
    title="Position reconciliation difference",
    message="ledger vs position mismatch",
):

    return Alert(
        alert_id=alert_id,
        rule_id="reconciliation-difference",
        severity=severity,
        state=AlertState.FIRING,
        title=title,
        message=message,
        service_id=service_id,
        labels=labels or {},
        fired_at=datetime(
            2026, 8, 13, 13, 0, 0,
            tzinfo=timezone.utc,
        ),
    )


def test_create_incident():
    # spec section 34
    manager = IncidentManager()

    impact = IncidentImpact(
        affected_services=("risk",),
        affected_venues=(),
        affected_strategies=(),
        affected_orders=10,
        affected_positions=2,
        trading_blocked=True,
    )

    incident = manager.create(
        title="Risk unavailable",
        description="Risk service unavailable",
        severity=IncidentSeverity.CRITICAL,
        impact=impact,
    )

    assert incident.state is IncidentState.DETECTED
    assert incident.context.incident_id.startswith("INC-")
    assert incident.context.environment == "production"
    assert incident.context.source_alert_ids == ()
    assert manager.get(
        incident.context.incident_id
    ) is incident


def test_get_unknown_returns_none():

    assert IncidentManager().get("INC-unknown") is None


def test_all_incidents():

    manager = IncidentManager()

    manager.create(
        title="A",
        description="a",
        severity=IncidentSeverity.MINOR,
        impact=_impact(),
    )

    manager.create(
        title="B",
        description="b",
        severity=IncidentSeverity.MINOR,
        impact=_impact(),
    )

    assert len(manager.all_incidents()) == 2


def test_create_records_incident_created_audit():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    events = manager.timeline(
        incident.context.incident_id
    )

    assert events[0].event_type == "INCIDENT_CREATED"
    assert events[0].new_state == "DETECTED"
    assert events[0].actor == "incident-engine"


def test_transition_records_audit():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    manager.transition(
        incident,
        IncidentState.TRIAGED,
        actor="operator",
        reason="manual triage",
    )

    assert incident.state is IncidentState.TRIAGED

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "STATE_CHANGED"
    assert last.previous_state == "DETECTED"
    assert last.new_state == "TRIAGED"
    assert last.actor == "operator"
    assert last.reason == "manual triage"


def test_transition_resolved_sets_resolved_at():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
        MONITORING,
        RESOLVED,
    ):
        manager.transition(incident, target)

    assert incident.state is IncidentState.RESOLVED
    assert incident.resolved_at is not None


def test_transition_closed_sets_closed_at():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
        MONITORING,
        RESOLVED,
        CLOSED,
    ):
        manager.transition(incident, target)

    assert incident.state is IncidentState.CLOSED
    assert incident.closed_at is not None
    assert incident.resolved_at is not None


def test_invalid_transition_raises_and_is_not_audited():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    with pytest.raises(ValueError):

        manager.transition(
            incident,
            IncidentState.RESOLVED,
        )

    assert incident.state is IncidentState.DETECTED
    assert len(manager.audit_events(
        incident.context.incident_id
    )) == 1  # 只有 INCIDENT_CREATED


def test_create_from_critical_alert():

    manager = IncidentManager()

    incident = manager.create_from_alert(
        _alert(labels={
            "venue": "NASDAQ",
            "service": "reconciliation",
        })
    )

    assert incident.state is IncidentState.DETECTED
    assert incident.severity is IncidentSeverity.CRITICAL
    assert incident.title == "Position reconciliation difference"
    assert incident.context.source_alert_ids == ("ALT-000001",)
    assert incident.context.correlation_key is not None


def test_emergency_alert_maps_to_catastrophic():

    manager = IncidentManager()

    incident = manager.create_from_alert(
        _alert(severity=AlertSeverity.EMERGENCY)
    )

    assert incident.severity is IncidentSeverity.CATASTROPHIC


def test_warning_alert_does_not_open_incident():

    manager = IncidentManager()

    with pytest.raises(ValueError):

        manager.create_from_alert(
            _alert(severity=AlertSeverity.WARNING)
        )

    assert manager.all_incidents() == ()


def test_should_open_incident_threshold():
    """spec section 13: 并非所有 Alert 都打开 Incident。"""

    assert should_open_incident(AlertSeverity.INFO) is False
    assert should_open_incident(AlertSeverity.WARNING) is False
    assert should_open_incident(AlertSeverity.ERROR) is False
    assert should_open_incident(AlertSeverity.CRITICAL) is True
    assert should_open_incident(AlertSeverity.EMERGENCY) is True


def test_map_alert_severity():

    assert map_alert_severity(AlertSeverity.INFO) is IncidentSeverity.MINOR
    assert map_alert_severity(AlertSeverity.WARNING) is IncidentSeverity.MODERATE
    assert map_alert_severity(AlertSeverity.ERROR) is IncidentSeverity.MAJOR
    assert map_alert_severity(AlertSeverity.CRITICAL) is IncidentSeverity.CRITICAL
    assert (
        map_alert_severity(AlertSeverity.EMERGENCY)
        is IncidentSeverity.CATASTROPHIC
    )


def test_build_correlation_key():
    """spec section 15: venue/service/strategy 组合为关联键。"""

    assert (
        build_correlation_key({
            "venue": "NASDAQ",
            "service": "event-bus",
        })
        == "venue:NASDAQ,service:event-bus"
    )

    assert (
        build_correlation_key({
            "strategy": "momentum-01",
        })
        == "strategy:momentum-01"
    )

    assert build_correlation_key({}) is None


def test_alerts_with_same_correlation_key_merge():
    """spec sections 14-15: 同 venue 的多个 Alert 合并为一个 Incident。"""

    manager = IncidentManager()

    alert1 = _alert(
        alert_id="ALT-000001",
        labels={"venue": "NASDAQ"},
    )

    alert2 = _alert(
        alert_id="ALT-000002",
        labels={"venue": "NASDAQ"},
    )

    inc1 = manager.create_from_alert(alert1)
    inc2 = manager.create_from_alert(alert2)

    assert inc1 is inc2
    assert inc1.context.source_alert_ids == (
        "ALT-000001",
        "ALT-000002",
    )
    assert len(manager.all_incidents()) == 1


def test_different_correlation_keys_create_separate_incidents():

    manager = IncidentManager()

    inc1 = manager.create_from_alert(
        _alert(
            alert_id="ALT-1",
            labels={"venue": "NASDAQ"},
        )
    )

    inc2 = manager.create_from_alert(
        _alert(
            alert_id="ALT-2",
            labels={"venue": "NYSE"},
        )
    )

    assert inc1 is not inc2
    assert len(manager.all_incidents()) == 2


def test_duplicate_alert_attach_is_idempotent():

    manager = IncidentManager()

    alert = _alert(
        alert_id="ALT-000001",
        labels={"venue": "NASDAQ"},
    )

    inc1 = manager.create_from_alert(alert)
    inc2 = manager.create_from_alert(alert)

    assert inc1 is inc2
    assert inc1.context.source_alert_ids == ("ALT-000001",)


def test_correlation_stops_after_incident_resolved():

    manager = IncidentManager()

    inc = manager.create_from_alert(
        _alert(
            alert_id="ALT-1",
            labels={"venue": "NASDAQ"},
        )
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
        MONITORING,
        RESOLVED,
    ):
        manager.transition(inc, target)

    inc2 = manager.create_from_alert(
        _alert(
            alert_id="ALT-2",
            labels={"venue": "NASDAQ"},
        )
    )

    assert inc2 is not inc
    assert inc2.context.source_alert_ids == ("ALT-2",)


def test_escalate_via_manager():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.MAJOR,
        impact=_impact(trading_blocked=False),
    )

    manager.escalate(
        incident,
        IncidentSeverity.CRITICAL,
        actor="incident-commander",
        reason="position inconsistency confirmed",
    )

    assert incident.severity is IncidentSeverity.CRITICAL

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "SEVERITY_ESCALATED"
    assert last.previous_state == "MAJOR"
    assert last.new_state == "CRITICAL"


def test_escalate_does_not_downgrade_via_manager():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    result = manager.escalate(
        incident,
        IncidentSeverity.MAJOR,
    )

    assert result is IncidentSeverity.CRITICAL
    assert incident.severity is IncidentSeverity.CRITICAL
    assert all(
        event.event_type != "SEVERITY_ESCALATED"
        for event in manager.audit_events(
            incident.context.incident_id
        )
    )


def test_identify_root_cause():
    """spec section 17: Root Cause 只由人工/确定性逻辑写入。"""

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    assert incident.root_cause is None

    manager.identify_root_cause(
        incident,
        "event-bus connection failure",
        actor="operator",
    )

    assert incident.root_cause == (
        "event-bus connection failure"
    )

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "ROOT_CAUSE_IDENTIFIED"
    assert last.metadata["root_cause"] == (
        "event-bus connection failure"
    )


def test_assign():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    manager.assign(incident, "oncall-ops")

    assert incident.assigned_to == "oncall-ops"


def test_request_control():
    """spec sections 23-24: Incident -> Control Request（不直接执行）。"""

    manager = IncidentManager()

    incident = manager.create(
        title="Position / Ledger mismatch",
        description="Reconciliation difference detected",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    request = manager.request_control(
        incident,
        action="PAUSE_TRADING",
        reason="Position / Ledger mismatch",
    )

    assert request.incident_id == (
        incident.context.incident_id
    )
    assert request.action == "PAUSE_TRADING"
    assert request.requested_by == "incident-engine"
    assert request.requires_confirmation is True

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "CONTROL_REQUESTED"
    assert last.metadata["action"] == "PAUSE_TRADING"


def test_approve_control():
    """spec section 25: 极高风险操作必须显式授权。"""

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CATASTROPHIC,
        impact=_impact(trading_blocked=True),
    )

    request = manager.request_control(
        incident,
        action="GLOBAL_KILL",
        reason="global trading safety compromised",
    )

    manager.approve_control(
        request,
        actor="risk-manager",
    )

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "CONTROL_APPROVED"
    assert last.actor == "risk-manager"
    assert len(manager.control_requests(
        incident.context.incident_id
    )) == 1


def test_recovery_gate_failure_blocks_resolution():
    """spec section 31: 任一检查 FAIL -> Incident != RESOLVED。"""

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
        MONITORING,
    ):
        manager.transition(incident, target)

    results = dict(RECOVERY_OK)
    results["reconciliation"] = False

    passed = manager.validate_recovery(
        incident,
        results,
    )

    assert passed is False
    assert incident.state is IncidentState.MONITORING
    assert incident.resolved_at is None


def test_recovery_gate_pass_resolves_from_monitoring():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
        MONITORING,
    ):
        manager.transition(incident, target)

    passed = manager.validate_recovery(
        incident,
        RECOVERY_OK,
    )

    assert passed is True
    assert incident.state is IncidentState.RESOLVED
    assert incident.resolved_at is not None

    last = manager.timeline(
        incident.context.incident_id
    )[-1]

    assert last.event_type == "STATE_CHANGED"
    assert last.new_state == "RESOLVED"


def test_recovery_gate_pass_from_recovering_goes_monitoring():

    manager = IncidentManager()

    incident = manager.create(
        title="T",
        description="d",
        severity=IncidentSeverity.CRITICAL,
        impact=_impact(),
    )

    for target in (
        TRIAGED,
        INVESTIGATING,
        MITIGATING,
        RECOVERING,
    ):
        manager.transition(incident, target)

    passed = manager.validate_recovery(
        incident,
        RECOVERY_OK,
    )

    assert passed is True
    assert incident.state is IncidentState.MONITORING


def test_full_incident_lifecycle_with_audit_trail():
    """spec section 27: 完整事故的审计链。"""

    manager = IncidentManager()

    alert = _alert(
        alert_id="ALT-000001",
        labels={
            "venue": "NASDAQ",
            "service": "reconciliation",
        },
    )

    incident = manager.create_from_alert(alert)

    manager.assign(incident, "oncall-ops")
    manager.transition(
        incident,
        IncidentState.TRIAGED,
        actor="operator",
        reason="manual triage",
    )
    manager.transition(
        incident,
        IncidentState.INVESTIGATING,
    )
    manager.identify_root_cause(
        incident,
        "event-bus connection failure",
        actor="operator",
    )
    manager.transition(
        incident,
        IncidentState.MITIGATING,
    )

    request = manager.request_control(
        incident,
        action="PAUSE_TRADING",
        reason="position / ledger mismatch",
    )

    manager.approve_control(
        request,
        actor="risk-manager",
    )

    manager.transition(
        incident,
        IncidentState.RECOVERING,
    )
    manager.transition(
        incident,
        IncidentState.MONITORING,
    )

    assert manager.validate_recovery(
        incident,
        RECOVERY_OK,
    ) is True

    manager.transition(
        incident,
        IncidentState.CLOSED,
        actor="operator",
        reason="postmortem complete",
    )

    event_types = [
        event.event_type
        for event in manager.timeline(
            incident.context.incident_id
        )
    ]

    assert "INCIDENT_CREATED" in event_types
    assert "ALERT_ATTACHED" not in event_types
    assert "ASSIGNED" in event_types
    assert "STATE_CHANGED" in event_types
    assert "ROOT_CAUSE_IDENTIFIED" in event_types
    assert "CONTROL_REQUESTED" in event_types
    assert "CONTROL_APPROVED" in event_types
    assert "RECOVERY_VALIDATION" in event_types

    assert incident.state is IncidentState.CLOSED
    assert incident.closed_at is not None
    assert incident.root_cause == (
        "event-bus connection failure"
    )
