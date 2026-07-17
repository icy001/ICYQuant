from datetime import datetime, timedelta

from services.data.access_workflow import (
    AccessRequest,
    ApprovalWorkflow,
    Approval,
    PermissionGrant,
    ExpirationPolicy,
    AccessWorkflowService,
)


def test_access_approval():
    request = AccessRequest(
        user="alice",
        dataset="NASDAQ",
        reason="research",
    )

    workflow = ApprovalWorkflow()

    result = workflow.approve(request)

    assert result.status == "APPROVED"


def test_access_request_initial():
    request = AccessRequest(
        user="bob",
        dataset="SP500",
        reason="trading",
    )

    assert request.status == "REQUESTED"
    assert request.user == "bob"


def test_approval():
    approval = Approval(approver="admin", decision="APPROVE")

    assert approval.approver == "admin"
    assert approval.decision == "APPROVE"


def test_permission_grant():
    grant = PermissionGrant(
        user="trader",
        dataset="REALTIME_QUOTES",
        permission="READ",
    )

    assert grant.user == "trader"
    assert grant.permission == "READ"


def test_expiration_policy_not_expired():
    policy = ExpirationPolicy()
    future_time = datetime.now() + timedelta(days=1)

    result = policy.expired(future_time)

    assert result is False


def test_expiration_policy_expired():
    policy = ExpirationPolicy()
    past_time = datetime.now() - timedelta(days=1)

    result = policy.expired(past_time)

    assert result is True


def test_access_workflow_service_submit():
    workflow = ApprovalWorkflow()
    service = AccessWorkflowService(workflow)

    request = AccessRequest(user="charlie", dataset="NYSE", reason="analysis")
    result = service.submit(request)

    assert result.user == "charlie"


def test_access_workflow_service_approve():
    workflow = ApprovalWorkflow()
    service = AccessWorkflowService(workflow)

    request = AccessRequest(user="dave", dataset="FOREX", reason="research")
    result = service.approve(request)

    assert result.status == "APPROVED"