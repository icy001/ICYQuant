import pytest

from services.risk import (
    RiskAuditRepository,
    RiskAuditService,
    RiskResult,
    RiskDecision,
)


@pytest.mark.asyncio
async def test_risk_audit():
    repo = RiskAuditRepository()
    service = RiskAuditService(repo)

    event = await service.record(
        order_id="ORDER001",
        account_id="ACC001",
        result=RiskResult(
            decision=RiskDecision.REJECT,
            reason="Limit exceeded",
        ),
    )

    assert event.order_id == "ORDER001"
    assert event.account_id == "ACC001"
    assert event.decision == "REJECT"
    assert event.reason == "Limit exceeded"

    events = await repo.list_all()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_risk_audit_approve():
    repo = RiskAuditRepository()
    service = RiskAuditService(repo)

    event = await service.record(
        order_id="ORDER002",
        account_id="ACC001",
        result=RiskResult(
            decision=RiskDecision.APPROVE,
        ),
        rule="MaxOrderSizeRule",
    )

    assert event.decision == "APPROVE"
    assert event.rule == "MaxOrderSizeRule"
    assert event.reason is None