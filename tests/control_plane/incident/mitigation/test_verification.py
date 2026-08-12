"""Tests for the verification gate (spec section 17/18)."""
from __future__ import annotations

from services.control_plane.incident.audit.event_type import IncidentAuditEventType
from services.control_plane.incident.audit.recorder import IncidentAuditRecorder
from services.control_plane.incident.audit.repository import (
    InMemoryIncidentAuditRepository,
)
from services.control_plane.incident.audit.service import IncidentAuditService
from services.control_plane.incident.incident_severity import IncidentSeverity
from services.control_plane.incident.incident_status import IncidentStatus
from services.control_plane.incident.mitigation.action import MitigationAction
from services.control_plane.incident.mitigation.action_type import (
    MitigationActionType,
)
from services.control_plane.incident.mitigation.executor import (
    MitigationEngine,
    MitigationExecutor,
    MitigationExecutorRegistry,
)
from services.control_plane.incident.mitigation.plan import MitigationPlan
from services.control_plane.incident.mitigation.result import MitigationResult
from services.control_plane.incident.mitigation.verification import (
    IncidentVerificationService,
    VerificationResult,
    VerificationStatus,
)


def _audit_service() -> IncidentAuditService:
    return IncidentAuditService(
        IncidentAuditRecorder(InMemoryIncidentAuditRepository())
    )


def test_verify_passes_when_all_checks_pass():
    service = IncidentVerificationService()
    incident = _incident()

    result = service.verify(incident, {"risk_level_normal": True})

    assert result.status is VerificationStatus.PASSED
    assert "passed" in result.message
    assert isinstance(result, VerificationResult)


def test_verify_fails_and_reports_failed_checks():
    service = IncidentVerificationService()
    incident = _incident()

    result = service.verify(
        incident,
        {"orders_cancelled": True, "risk_level_normal": False},
    )

    assert result.status is VerificationStatus.FAILED
    assert "risk_level_normal" in result.message


def test_successful_mitigation_requires_verification(incident_factory):
    """Key test: mitigation success alone never resolves the incident —
    verification is the mandatory gate before RESOLVED.
    """
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    incident.start_mitigation()

    registry = MitigationExecutorRegistry()

    class CancelExecutor(MitigationExecutor):
        def execute(self, action):
            return MitigationResult(
                action_id=action.action_id,
                success=True,
                message="all orders cancelled",
                external_reference="oms:batch-1",
            )

    registry.register(MitigationActionType.CANCEL_OPEN_ORDERS, CancelExecutor())
    engine = MitigationEngine(registry)

    plan = MitigationPlan(incident_id=incident.id)
    plan.add(
        MitigationAction(
            incident_id=incident.id,
            action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        )
    )

    results = engine.execute(plan)
    assert all(r.success for r in results)

    # Even though mitigation succeeded, the incident is still MITIGATING.
    assert incident.status is IncidentStatus.MITIGATING

    # The verification gate must pass before the incident can be resolved.
    verification = IncidentVerificationService()
    check = verification.verify_and_resolve(
        incident,
        {"orders_cancelled": True},
        resolution_reason="risk controlled",
        resolved_by="operator-1",
    )

    assert check.status is VerificationStatus.PASSED
    assert incident.status is IncidentStatus.RESOLVED


def test_failed_verification_reopens_incident(incident_factory):
    """Key test: a failed verification reopens a resolved incident."""
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    incident.start_mitigation()
    incident.resolve(
        "mitigation executed, verification pending",
        "operator-1",
        verification_result=VerificationStatus.PENDING.value,
    )
    assert incident.status is IncidentStatus.RESOLVED

    service = IncidentVerificationService()
    result = service.verify(
        incident,
        {"risk_level_normal": False},
        actor="verification-engine",
    )

    assert result.status is VerificationStatus.FAILED
    assert incident.status is IncidentStatus.REOPENED
    assert incident.reopen_count == 1


def test_verify_and_resolve_refuses_failed_checks(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.HIGH)
    incident.start_mitigation()

    service = IncidentVerificationService()
    result = service.verify_and_resolve(
        incident,
        {"risk_level_normal": False},
        resolution_reason="risk controlled",
        resolved_by="operator-1",
    )

    assert result.status is VerificationStatus.FAILED
    assert incident.status is IncidentStatus.MITIGATING


def test_verification_records_audit_events(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    incident.start_mitigation()
    incident.resolve(
        "mitigation executed",
        "operator-1",
        verification_result=VerificationStatus.PENDING.value,
    )
    audit = _audit_service()
    service = IncidentVerificationService(audit_service=audit)

    service.verify(incident, {"risk_level_normal": False})

    types = [e.event_type for e in audit.timeline(incident.id)]
    assert IncidentAuditEventType.VERIFICATION_STARTED in types
    assert IncidentAuditEventType.VERIFICATION_FAILED in types
    assert IncidentAuditEventType.VERIFICATION_PASSED not in types


def test_verification_passed_records_audit_event(incident_factory):
    incident = incident_factory(severity=IncidentSeverity.CRITICAL)
    incident.start_mitigation()
    audit = _audit_service()
    service = IncidentVerificationService(audit_service=audit)

    service.verify(incident, {"risk_level_normal": True})

    types = [e.event_type for e in audit.timeline(incident.id)]
    assert IncidentAuditEventType.VERIFICATION_STARTED in types
    assert IncidentAuditEventType.VERIFICATION_PASSED in types
    assert IncidentAuditEventType.VERIFICATION_FAILED not in types


def _incident():
    """Build a bare-minimum incident stub for verification-only tests."""
    from services.control_plane.incident.incident_id import IncidentId
    from services.control_plane.incident.incident_scope import IncidentScope
    from services.control_plane.incident.incident_source import IncidentSource
    from services.control_plane.incident.incident_type import IncidentType

    from services.control_plane.incident.incident import Incident

    return Incident(
        incident_id=IncidentId.generate(1),
        type=IncidentType.HEALTH_FAILURE,
        severity=IncidentSeverity.LOW,
        scope=IncidentScope.GLOBAL,
        source=IncidentSource.HEALTH_MONITOR,
    )
