"""
Risk decision trace & audit tests (Commit 41 Part 1.5).

Covers the spec scenarios:

- approved decision creates trace
- rejected decision creates trace
- triggered rules are preserved
- context snapshot is preserved
- decision trace is immutable
- audit records decision
- duplicate decision is idempotent
- historical trace is not recalculated

Every test keeps the invariant:

    Risk Decision == Audit Decision == Decision Trace
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.risk.audit import RiskDecisionAudit
from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import RiskDecisionStatus
from services.risk.domain import RiskDecisionTrace
from services.risk.evaluator.policy_evaluator import RiskPolicyEvaluator
from services.risk.infrastructure.repositories.in_memory_decision_repository import (
    InMemoryRiskDecisionRepository,
)
from services.risk.policies.cash_availability import CashAvailabilityPolicy
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy
from services.risk.policies.position_limit import PositionLimitPolicy
from services.risk.service.risk_decision_service import RiskDecisionService

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_context(
    *,
    account_id="acc-1",
    strategy_id="strat-1",
    signal_id="sig-1",
    instrument_id="BTCUSDT",
    side="BUY",
    quantity=Decimal("1"),
    price=Decimal("50000"),
    available_cash=Decimal("100000"),
    current_position=Decimal("0"),
    daily_pnl=Decimal("0"),
    daily_loss_limit=Decimal("1000"),
    max_position=Decimal("100"),
) -> RiskDecisionContext:
    return RiskDecisionContext(
        account_id=account_id,
        strategy_id=strategy_id,
        signal_id=signal_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=price,
        available_cash=available_cash,
        current_position=current_position,
        daily_pnl=daily_pnl,
        daily_loss_limit=daily_loss_limit,
        max_position=max_position,
    )


def make_evaluator() -> RiskPolicyEvaluator:
    return RiskPolicyEvaluator(
        [
            DailyLossLimitPolicy(),
            PositionLimitPolicy(),
            CashAvailabilityPolicy(),
        ]
    )


class EventPublisherSpy:
    def __init__(self) -> None:
        self.published = []

    def publish(self, event) -> None:
        self.published.append(event)


def make_service(
    *,
    audit: RiskDecisionAudit | None = None,
) -> tuple[RiskDecisionService, InMemoryRiskDecisionRepository, EventPublisherSpy]:
    repository = InMemoryRiskDecisionRepository()
    publisher = EventPublisherSpy()
    service = RiskDecisionService(
        make_evaluator(),
        publisher,
        repository,
        audit=audit,
        decision_id_factory=lambda: "DEC-001",
        now_provider=lambda: FIXED_NOW,
    )
    return service, repository, publisher


# ---------------------------------------------------------------------------
# approved decision creates trace
# ---------------------------------------------------------------------------


def test_approved_decision_creates_trace():
    audit = RiskDecisionAudit()
    service, repository, publisher = make_service(audit=audit)

    decision = service.evaluate(make_context(), request_id="REQ-001")

    assert decision.status == RiskDecisionStatus.APPROVED
    trace = audit.get("DEC-001")
    assert trace is not None
    assert trace.decision_id == "DEC-001"
    assert trace.request_id == "REQ-001"
    assert trace.strategy_id == "strat-1"
    assert trace.decision == decision
    assert trace.created_at == FIXED_NOW

    # Risk Decision == Audit Decision == Decision Trace
    record = repository.get_by_request_id("REQ-001")
    assert record is not None
    assert trace.decision.status == record.decision == decision.status

    # Decision Trace is written by the service, not by the decision itself.
    assert len(publisher.published) == 1


def test_service_without_audit_still_works_and_produces_no_trace():
    service, _, publisher = make_service(audit=None)

    decision = service.evaluate(make_context(), request_id="REQ-001")

    assert decision.status == RiskDecisionStatus.APPROVED
    assert len(publisher.published) == 1


# ---------------------------------------------------------------------------
# rejected decision creates trace
# ---------------------------------------------------------------------------


def test_rejected_decision_creates_trace():
    audit = RiskDecisionAudit()
    service, repository, _ = make_service(audit=audit)

    decision = service.evaluate(
        make_context(quantity=Decimal("150")),
        request_id="REQ-001",
    )

    assert decision.status == RiskDecisionStatus.REJECTED
    trace = audit.get("DEC-001")
    assert trace is not None
    assert trace.decision == decision
    assert trace.decision.status == RiskDecisionStatus.REJECTED

    # Risk Decision == Audit Decision == Decision Trace
    record = repository.get_by_request_id("REQ-001")
    assert record is not None
    assert trace.decision.status == record.decision == decision.status


# ---------------------------------------------------------------------------
# triggered rules are preserved
# ---------------------------------------------------------------------------


def test_triggered_rules_are_preserved():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    decision = service.evaluate(
        make_context(quantity=Decimal("150")),
        request_id="REQ-001",
    )

    assert decision.status == RiskDecisionStatus.REJECTED
    trace = audit.get("DEC-001")
    assert trace.evaluated_rules == ("daily_loss_limit", "position_limit")
    assert trace.triggered_rules == ("position_limit",)


def test_approved_decision_has_no_triggered_rules():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    service.evaluate(make_context(), request_id="REQ-001")

    trace = audit.get("DEC-001")
    assert trace.evaluated_rules == (
        "daily_loss_limit",
        "position_limit",
        "cash_availability",
    )
    assert trace.triggered_rules == ()


# ---------------------------------------------------------------------------
# context snapshot is preserved
# ---------------------------------------------------------------------------


def test_context_snapshot_is_preserved():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    service.evaluate(
        make_context(
            daily_pnl=Decimal("-2000"),
            daily_loss_limit=Decimal("-1000"),
            max_position=Decimal("50"),
        ),
        request_id="REQ-001",
    )

    trace = audit.get("DEC-001")
    snapshot = trace.context_snapshot
    assert snapshot["daily_pnl"] == Decimal("-2000")
    assert snapshot["daily_loss_limit"] == Decimal("-1000")
    assert snapshot["position_limit"] == Decimal("50")
    assert snapshot["proposed_quantity"] == Decimal("1")
    assert snapshot["available_cash"] == Decimal("100000")
    assert snapshot["snapshot_at"] == FIXED_NOW


# ---------------------------------------------------------------------------
# decision trace is immutable
# ---------------------------------------------------------------------------


def test_decision_trace_is_immutable():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    service.evaluate(make_context(), request_id="REQ-001")

    trace = audit.get("DEC-001")
    assert isinstance(trace, RiskDecisionTrace)

    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.decision_id = "DEC-OTHER"
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.triggered_rules = ("something",)
    with pytest.raises(dataclasses.FrozenInstanceError):
        trace.context_snapshot = {}


# ---------------------------------------------------------------------------
# audit records decision
# ---------------------------------------------------------------------------


def test_audit_records_decision():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    service.evaluate(make_context(), request_id="REQ-001")

    trace = audit.get("DEC-001")
    assert trace is not None
    assert audit.count() == 1
    assert audit.list_all() == (trace,)


# ---------------------------------------------------------------------------
# duplicate decision is idempotent
# ---------------------------------------------------------------------------


def test_duplicate_decision_is_idempotent():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    decision = service.evaluate(make_context(), request_id="REQ-001")
    original = audit.get("DEC-001")
    assert audit.count() == 1

    # A re-delivered trace for the SAME decision_id (consumer retry, event
    # replay, service restart) must be ignored.
    duplicate = RiskDecisionTrace(
        decision_id="DEC-001",
        request_id="REQ-001",
        strategy_id="strat-1",
        decision=decision,
        evaluated_rules=("other_rule",),
        triggered_rules=("other_rule",),
        context_snapshot={},
        created_at=FIXED_NOW,
    )
    audit.record(duplicate)

    assert audit.count() == 1
    assert audit.get("DEC-001") == original


# ---------------------------------------------------------------------------
# historical trace is not recalculated
# ---------------------------------------------------------------------------


def test_historical_trace_is_not_recalculated():
    audit = RiskDecisionAudit()
    service, _, _ = make_service(audit=audit)

    original_context = make_context(current_position=Decimal("0"))
    service.evaluate(original_context, request_id="REQ-001")
    original = audit.get("DEC-001")
    assert original.context_snapshot["current_position"] == Decimal("0")

    # Account state has drifted since the decision: the same request id is
    # refused (idempotency) and the historical trace is never overwritten.
    drifted_context = make_context(current_position=Decimal("999"))
    with pytest.raises(ValueError, match="already exists"):
        service.evaluate(drifted_context, request_id="REQ-001")

    assert audit.count() == 1
    assert audit.get("DEC-001") == original
    assert original.context_snapshot["current_position"] == Decimal("0")
