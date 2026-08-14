"""
Tests for the risk decision orchestration service (Commit 41 Part 1.1/1.2).

Covers the approved / rejected flows, first-reject-wins semantics,
idempotency per ``(request_id, snapshot)``, persistence of the immutable
decision record (persist before publish) and event-publisher failure
semantics.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.decision.risk_decision import (
    RiskDecision,
    RiskDecisionStatus,
)
from services.risk.events import (
    RISK_DECISION_APPROVED,
    RISK_DECISION_REJECTED,
)
from services.risk.evaluator.policy_evaluator import RiskPolicyEvaluator
from services.risk.infrastructure.repositories.in_memory_decision_repository import (
    InMemoryRiskDecisionRepository,
)
from services.risk.policies.base import RiskPolicy
from services.risk.policies.cash_availability import CashAvailabilityPolicy
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy
from services.risk.policies.position_limit import PositionLimitPolicy
from services.risk.policy_trace import (
    STATUS_PASS,
    STATUS_REJECT,
)
from services.risk.service.risk_decision_service import RiskDecisionService

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_context(**overrides):
    base = dict(
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        side="BUY",
        quantity=Decimal("10"),
        price=Decimal("100"),
        available_cash=Decimal("5000"),
        current_position=Decimal("0"),
        daily_pnl=Decimal("0"),
        daily_loss_limit=Decimal("1000"),
        max_position=Decimal("100"),
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )
    base.update(overrides)
    return RiskDecisionContext(**base)


class RecordingPublisher:
    """Test double for the ``RiskEventPublisher`` port."""

    def __init__(self):
        self.events = []
        self.fail = False

    def publish(self, event):
        if self.fail:
            raise RuntimeError("event bus unavailable")
        self.events.append(event)


def make_service(policies=None, publisher=None, repository=None):
    publisher = publisher or RecordingPublisher()
    repository = repository or InMemoryRiskDecisionRepository()
    evaluator = RiskPolicyEvaluator(
        policies=policies
        or [
            CashAvailabilityPolicy(),
            PositionLimitPolicy(),
            DailyLossLimitPolicy(),
        ]
    )
    service = RiskDecisionService(
        evaluator,
        publisher,
        repository,
        decision_id_factory=lambda: "decision-1",
        now_provider=lambda: FIXED_NOW,
    )
    return service, publisher, repository


def test_approves_and_publishes_approved_event():
    service, publisher, _ = make_service()

    decision = service.evaluate(make_context(), request_id="req-1")

    assert decision.status == RiskDecisionStatus.APPROVED
    assert len(publisher.events) == 1
    assert publisher.events[0].type == RISK_DECISION_APPROVED


def test_rejects_and_publishes_rejected_event():
    service, publisher, _ = make_service()

    context = make_context(
        side="BUY",
        quantity=Decimal("2000"),
        price=Decimal("100"),
        available_cash=Decimal("1000000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )
    decision = service.evaluate(context, request_id="req-1")

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.rejected_policy == "position_limit"
    assert len(publisher.events) == 1
    assert publisher.events[0].type == RISK_DECISION_REJECTED


def test_approved_event_carries_auditable_payload():
    service, publisher, _ = make_service()

    decision = service.evaluate(make_context(), request_id="req-1")

    event = publisher.events[0]
    assert event.decision_id == "decision-1"
    assert event.request_id == "req-1"
    assert event.strategy_id == "strat-1"
    assert event.instrument_id == "BTCUSDT"
    assert event.decision == RISK_DECISION_APPROVED
    assert event.timestamp == FIXED_NOW
    assert event.reason == decision.reason


def test_rejected_event_carries_auditable_payload():
    service, publisher, _ = make_service()

    context = make_context(
        side="BUY",
        quantity=Decimal("2000"),
        price=Decimal("100"),
        available_cash=Decimal("1000000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )
    decision = service.evaluate(context, request_id="req-1")

    event = publisher.events[0]
    assert event.type == RISK_DECISION_REJECTED
    assert event.decision_id == "decision-1"
    assert event.request_id == "req-1"
    assert event.strategy_id == "strat-1"
    assert event.instrument_id == "BTCUSDT"
    assert event.decision == RISK_DECISION_REJECTED
    assert event.timestamp == FIXED_NOW
    assert event.policy_id == decision.policy_id
    assert event.reason == decision.reason


def test_first_reject_wins_and_later_policies_not_executed():
    evaluated = []

    class PassingPolicy(RiskPolicy):
        policy_id = "passing"

        def evaluate(self, context):
            evaluated.append(self.policy_id)
            return RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                reason_code="PASSED",
                policy_id=self.policy_id,
            )

    class RejectingPolicy(RiskPolicy):
        policy_id = "rejecting"

        def evaluate(self, context):
            evaluated.append(self.policy_id)
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="REJECTED",
                policy_id=self.policy_id,
            )

    class MustNotRunPolicy(RiskPolicy):
        policy_id = "must_not_run"

        def evaluate(self, context):
            raise AssertionError("policy executed after first rejection")

    service, publisher, _ = make_service(
        policies=[
            PassingPolicy(),
            RejectingPolicy(),
            MustNotRunPolicy(),
        ]
    )

    decision = service.evaluate(make_context(), request_id="req-1")

    assert decision.status == RiskDecisionStatus.REJECTED
    assert decision.rejected_policy == "rejecting"
    assert evaluated == ["passing", "rejecting"]


def test_same_request_and_snapshot_is_idempotent():
    service, publisher, repository = make_service()

    first = service.evaluate(make_context(), request_id="req-1")
    second = service.evaluate(make_context(), request_id="req-1")

    assert first == second
    assert len(publisher.events) == 1
    assert repository.get_by_request_id("req-1") is not None


def test_same_request_different_snapshot_is_rejected():
    service, publisher, _ = make_service()

    service.evaluate(
        make_context(quantity=Decimal("10")),
        request_id="req-1",
    )

    with pytest.raises(ValueError, match="already exists"):
        service.evaluate(
            make_context(quantity=Decimal("2000")),
            request_id="req-1",
        )


def test_publish_failure_propagates_and_does_not_cache():
    publisher = RecordingPublisher()
    publisher.fail = True
    service, _, repository = make_service(publisher=publisher)

    with pytest.raises(RuntimeError, match="event bus unavailable"):
        service.evaluate(make_context(), request_id="req-1")

    # Persistence happens before publication: the record exists even though
    # the event was never published.
    record = repository.get_by_request_id("req-1")
    assert record is not None
    assert record.decision == "APPROVED"
    assert publisher.events == []

    # A retry with the same request_id is rejected: no second decision may
    # be produced for an already-recorded request.
    with pytest.raises(ValueError, match="already exists"):
        service.evaluate(make_context(), request_id="req-1")


def test_request_without_explicit_id_is_distinct():
    service, publisher, repository = make_service()

    first = service.evaluate(make_context())
    second = service.evaluate(make_context())

    assert first == second
    assert len(publisher.events) == 1
    # Falls back to the context signal id as the request identity.
    assert repository.get_by_request_id("sig-1") is not None


def test_approved_decision_is_persisted():
    service, _, repository = make_service()

    service.evaluate(make_context(), request_id="req-1")

    record = repository.get_by_decision_id("decision-1")
    assert record is not None
    assert record.decision == "APPROVED"
    assert record.request_id == "req-1"
    assert record.strategy_id == "strat-1"
    assert record.instrument == "BTCUSDT"
    assert record.created_at == FIXED_NOW

    # Commit 41 Part 1.3: the persisted audit record embeds the trace.
    trace = record.policy_trace
    assert trace is not None
    assert [e.policy_name for e in trace.evaluations] == [
        "cash_availability",
        "position_limit",
        "daily_loss_limit",
    ]
    assert [e.status for e in trace.evaluations] == [STATUS_PASS] * 3
    assert [e.evaluation_order for e in trace.evaluations] == [1, 2, 3]


def test_rejected_decision_is_persisted_with_policy():
    service, _, repository = make_service()

    context = make_context(
        side="BUY",
        quantity=Decimal("2000"),
        price=Decimal("100"),
        available_cash=Decimal("1000000"),
        current_position=Decimal("0"),
        max_position=Decimal("1000"),
    )
    service.evaluate(context, request_id="req-1")

    record = repository.get_by_decision_id("decision-1")
    assert record is not None
    assert record.decision == "REJECTED"
    assert record.rejected_policy == "position_limit"

    # Commit 41 Part 1.3: only executed policies appear in the trace.
    trace = record.policy_trace
    assert trace is not None
    assert [e.policy_name for e in trace.evaluations] == [
        "cash_availability",
        "position_limit",
    ]
    assert [e.status for e in trace.evaluations] == [
        STATUS_PASS,
        STATUS_REJECT,
    ]
    assert [e.evaluation_order for e in trace.evaluations] == [1, 2]
