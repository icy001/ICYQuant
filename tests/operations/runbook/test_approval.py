"""Approval workflow tests (Commit 27 Part 1.5, spec sections 11-13, 29, 38)."""

import pytest

from services.operations import (
    ApprovalRequest,
    ApprovalWorkflow,
    IncidentSeverity,
    requires_approval,
)


def test_kill_requires_approval():
    # spec section 38
    assert requires_approval(
        severity=5,
        action="KILL_TRADING",
    )


def test_failover_requires_approval():

    assert requires_approval(
        severity=1,
        action="FAILOVER_VENUE",
    )


def test_pause_requires_approval_at_critical():

    assert requires_approval(
        severity=3,
        action="PAUSE_TRADING",
    )


def test_pause_no_approval_below_critical():

    assert not requires_approval(
        severity=2,
        action="PAUSE_TRADING",
    )


def test_incident_severity_accepted():

    assert requires_approval(
        IncidentSeverity.CRITICAL,
        action="PAUSE_TRADING",
    )

    assert not requires_approval(
        IncidentSeverity.MODERATE,
        action="PAUSE_TRADING",
    )


def test_other_actions_do_not_require_approval():

    assert not requires_approval(
        severity=5,
        action="RESTART_SERVICE",
    )


def test_workflow_request_approve(clock):

    workflow = ApprovalWorkflow(clock=clock)

    request = workflow.request(
        incident_id="INC-001",
        action="PAUSE_TRADING",
        requested_by="runbook",
        reason="Position / Ledger mismatch",
    )

    assert isinstance(request, ApprovalRequest)
    assert request.approved is False
    assert request.requested_at == clock()
    assert workflow.is_approved(request.approval_id) is False


def test_workflow_approve(clock):

    workflow = ApprovalWorkflow(clock=clock)

    request = workflow.request(
        incident_id="INC-001",
        action="KILL_TRADING",
        requested_by="runbook",
        reason="Catastrophic event",
    )

    approved = workflow.approve(
        request.approval_id,
        approved_by="incident-commander",
    )

    assert approved.approved is True
    assert approved.approved_by == "incident-commander"
    assert approved.approved_at == clock()
    assert workflow.is_approved(request.approval_id)


def test_approve_requires_actor(clock):

    workflow = ApprovalWorkflow(clock=clock)

    request = workflow.request(
        incident_id="INC-001",
        action="PAUSE_TRADING",
        requested_by="runbook",
        reason="mismatch",
    )

    with pytest.raises(ValueError):
        workflow.approve(
            request.approval_id,
            approved_by="",
        )


def test_reject(clock):

    workflow = ApprovalWorkflow(clock=clock)

    request = workflow.request(
        incident_id="INC-001",
        action="PAUSE_TRADING",
        requested_by="runbook",
        reason="mismatch",
    )

    rejected = workflow.reject(
        request.approval_id,
        rejected_by="operator",
        reason="impact contained",
    )

    assert rejected.approved is False
    assert rejected.approved_by == "operator"


def test_pending_requests(clock):

    workflow = ApprovalWorkflow(clock=clock)

    first = workflow.request(
        incident_id="INC-001",
        action="PAUSE_TRADING",
        requested_by="runbook",
        reason="mismatch",
    )

    second = workflow.request(
        incident_id="INC-002",
        action="KILL_TRADING",
        requested_by="runbook",
        reason="catastrophic",
    )

    workflow.approve(first.approval_id, approved_by="commander")

    assert [r.approval_id for r in workflow.pending()] == [second.approval_id]
    assert [r.approval_id for r in workflow.pending("INC-002")] == [second.approval_id]
    assert workflow.pending("INC-001") == ()
