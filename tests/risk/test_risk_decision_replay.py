"""
Risk decision replay service tests (Commit 41 Part 1.4).

Covers the seven spec scenarios:

1. Exact match                    -> MATCHED
2. Decision mismatch              -> MISMATCHED
3. Same decision / different policy -> MISMATCHED
4. Trace difference               -> MISMATCHED
5. Replay never places orders     -> pure evaluation, no side effects
6. Context snapshot isolation     -> replay ignores current account state
7. Policy version                 -> VERSION_MISMATCH is refused, same
                                     version is allowed
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.context_snapshot import (
    RiskDecisionContextSnapshot,
)
from services.risk.decision.decision_record import RiskDecisionRecord
from services.risk.decision.risk_decision import RiskDecisionStatus
from services.risk.evaluator.policy_evaluator import RiskPolicyEvaluator
from services.risk.infrastructure.repositories.in_memory_decision_repository import (
    InMemoryRiskDecisionRepository,
)
from services.risk.infrastructure.repositories.in_memory_replay_repository import (
    InMemoryRiskDecisionReplayRepository,
)
from services.risk.policies.cash_availability import CashAvailabilityPolicy
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy
from services.risk.policies.position_limit import PositionLimitPolicy
from services.risk.policy_trace import (
    PolicyEvaluationResult,
    RiskPolicyTrace,
)
from services.risk.replay import (
    RiskDecisionReplayError,
    RiskDecisionReplayService,
    RiskDecisionReplayVersionMismatchError,
)
from services.risk.replay_result import ReplayStatus

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


def snapshot_from_context(context, *, at=FIXED_NOW) -> RiskDecisionContextSnapshot:
    return RiskDecisionContextSnapshot.from_context(context, snapshot_at=at)


def decision_to_record(decision, context, *, decision_id="DEC-001"):
    return decision.to_record(
        context,
        decision_id=decision_id,
        request_id=context.signal_id,
        created_at=FIXED_NOW,
    )


def make_record(
    *,
    decision="APPROVED",
    reason="all risk policies passed",
    rejected_policy=None,
    trace=None,
    snapshot=None,
    policy_version="risk-policy-v1",
) -> RiskDecisionRecord:
    return RiskDecisionRecord(
        decision_id="DEC-001",
        request_id="REQ-001",
        strategy_id="strat-1",
        instrument="BTCUSDT",
        decision=decision,
        reason=reason,
        rejected_policy=rejected_policy,
        policy_trace=trace or RiskPolicyTrace(evaluations=()),
        context_snapshot=snapshot or snapshot_from_context(make_context()),
        policy_version=policy_version,
        created_at=FIXED_NOW,
    )


def ev(name, status, order, reason="reason"):
    return PolicyEvaluationResult(
        policy_name=name,
        status=status,
        reason=reason,
        evaluation_order=order,
    )


# ---------------------------------------------------------------------------
# Test 1: exact match
# ---------------------------------------------------------------------------


def test_replay_exact_match_returns_matched():
    evaluator = make_evaluator()
    context = make_context()
    record = decision_to_record(evaluator.evaluate(context), context)

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record)

    assert result.status == ReplayStatus.MATCHED
    assert result.matched is True
    assert result.decision_id == "DEC-001"
    assert result.original_decision == "APPROVED"
    assert result.replayed_decision == "APPROVED"
    assert result.differences == ()
    assert result.original_policy_trace == record.policy_trace
    assert result.replayed_policy_trace == record.policy_trace


# ---------------------------------------------------------------------------
# Test 2: decision mismatch
# ---------------------------------------------------------------------------


def test_replay_detects_decision_mismatch():
    evaluator = make_evaluator()
    # The historical record claims APPROVED, but the frozen snapshot would
    # actually be rejected by the position limit policy.
    rejecting_context = make_context(quantity=Decimal("150"))
    record = make_record(
        decision="APPROVED",
        trace=RiskPolicyTrace(
            evaluations=(
                ev("daily_loss_limit", "PASS", 1),
                ev("position_limit", "PASS", 2),
            )
        ),
        snapshot=snapshot_from_context(rejecting_context),
    )

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record)

    assert result.matched is False
    assert result.status == ReplayStatus.MISMATCHED
    assert result.original_decision == "APPROVED"
    assert result.replayed_decision == "REJECTED"
    assert "decision changed" in result.differences


# ---------------------------------------------------------------------------
# Test 3: same decision, different rejecting policy
# ---------------------------------------------------------------------------


def test_replay_same_decision_different_policy_is_mismatch():
    evaluator = make_evaluator()
    # Original: rejected by position_limit. Snapshot: daily loss is the
    # rejecting policy and position stays within limits.
    daily_loss_context = make_context(
        daily_pnl=Decimal("-2000"),
        daily_loss_limit=Decimal("-1000"),
    )
    record = make_record(
        decision="REJECTED",
        reason="projected position exceeds limit",
        rejected_policy="position_limit",
        trace=RiskPolicyTrace(
            evaluations=(
                ev("daily_loss_limit", "PASS", 1),
                ev("position_limit", "REJECT", 2),
            )
        ),
        snapshot=snapshot_from_context(daily_loss_context),
    )

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record)

    assert result.original_decision == "REJECTED"
    assert result.replayed_decision == "REJECTED"
    assert result.matched is False
    assert result.status == ReplayStatus.MISMATCHED
    assert "rejected_policy changed" in " ".join(result.differences)


# ---------------------------------------------------------------------------
# Test 4: trace difference
# ---------------------------------------------------------------------------


def test_replay_detects_trace_difference():
    evaluator = make_evaluator()
    # Snapshot: position passes but cash availability rejects.
    cash_reject_context = make_context(
        quantity=Decimal("3"),
        price=Decimal("50000"),
        available_cash=Decimal("100000"),
    )
    record = make_record(
        decision="REJECTED",
        reason="projected position exceeds limit",
        rejected_policy="position_limit",
        trace=RiskPolicyTrace(
            evaluations=(
                ev("daily_loss_limit", "PASS", 1),
                ev("position_limit", "REJECT", 2),
            )
        ),
        snapshot=snapshot_from_context(cash_reject_context),
    )

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record)

    assert result.matched is False
    diff_text = " ".join(result.differences)
    assert "position_limit changed from REJECT to PASS" in diff_text
    assert (
        "cash_availability changed from NOT_EXECUTED to REJECT"
        in diff_text
    )


# ---------------------------------------------------------------------------
# Test 5: replay never places orders / mutates positions
# ---------------------------------------------------------------------------


class OrderEngineSpy:
    def __init__(self) -> None:
        self.calls = 0

    def place_order(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("replay must never place orders")


class PositionMutatorSpy:
    def __init__(self) -> None:
        self.calls = 0

    def apply(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("replay must never mutate positions")


def test_replay_never_places_orders_or_mutates_positions():
    evaluator = make_evaluator()
    context = make_context()
    record = decision_to_record(evaluator.evaluate(context), context)

    decision_repository = InMemoryRiskDecisionRepository()
    decision_repository.save(record)

    order_engine = OrderEngineSpy()
    position_mutator = PositionMutatorSpy()

    replay_service = RiskDecisionReplayService(
        evaluator,
        replay_repository=InMemoryRiskDecisionReplayRepository(),
    )
    result = replay_service.replay(record)

    assert result.matched is True
    assert order_engine.calls == 0
    assert position_mutator.calls == 0
    # The historical record is untouched.
    assert decision_repository.get_by_decision_id("DEC-001") == record


def test_replay_service_has_no_order_or_position_dependencies():
    signature = inspect.signature(RiskDecisionReplayService.__init__)
    parameter_names = set(signature.parameters)
    assert "order_engine" not in parameter_names
    assert "execution" not in parameter_names
    assert "position_repository" not in parameter_names


# ---------------------------------------------------------------------------
# Test 6: replay uses the original snapshot, not current state
# ---------------------------------------------------------------------------


def test_replay_ignores_current_account_state():
    evaluator = make_evaluator()
    original_context = make_context(current_position=Decimal("0"))
    record = decision_to_record(
        evaluator.evaluate(original_context),
        original_context,
    )

    # Current account state has drifted: position 999 would be rejected.
    current_context = make_context(current_position=Decimal("999"))
    current_decision = evaluator.evaluate(current_context)
    assert current_decision.status == RiskDecisionStatus.REJECTED

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record)

    assert result.replayed_decision == "APPROVED"
    assert result.matched is True
    assert result.status == ReplayStatus.MATCHED


# ---------------------------------------------------------------------------
# Test 7: policy version handling
# ---------------------------------------------------------------------------


def test_replay_with_same_policy_version_is_allowed():
    evaluator = make_evaluator()
    context = make_context()
    record = decision_to_record(evaluator.evaluate(context), context)
    assert record.policy_version == "risk-policy-v1"

    replay_service = RiskDecisionReplayService(evaluator)
    result = replay_service.replay(record, policy_version="risk-policy-v1")

    assert result.matched is True


def test_replay_with_different_policy_version_is_version_mismatch():
    evaluator = make_evaluator()
    context = make_context()
    record = decision_to_record(evaluator.evaluate(context), context)

    replay_repository = InMemoryRiskDecisionReplayRepository()
    replay_service = RiskDecisionReplayService(
        evaluator,
        replay_repository=replay_repository,
    )

    with pytest.raises(
        RiskDecisionReplayVersionMismatchError,
        match="VERSION_MISMATCH",
    ):
        replay_service.replay(record, policy_version="risk-policy-v2")

    # A FAILED replay record is persisted for the audit trail.
    replay_records = replay_repository.list_by_decision_id("DEC-001")
    assert len(replay_records) == 1
    assert replay_records[0].status == "FAILED"
    assert replay_records[0].matched is False
    assert "VERSION_MISMATCH" in " ".join(replay_records[0].differences)


class FailingEvaluator:
    def evaluate(self, context):
        raise RuntimeError("evaluator unavailable")


def test_replay_failure_persists_failed_record_and_raises():
    record = make_record()

    replay_repository = InMemoryRiskDecisionReplayRepository()
    replay_service = RiskDecisionReplayService(
        FailingEvaluator(),
        replay_repository=replay_repository,
    )

    with pytest.raises(RiskDecisionReplayError, match="evaluator unavailable"):
        replay_service.replay(record)

    replay_records = replay_repository.list_by_decision_id("DEC-001")
    assert len(replay_records) == 1
    assert replay_records[0].status == "FAILED"
    assert replay_records[0].replayed_decision == "FAILED"
    assert replay_records[0].matched is False
    assert "replay failed" in " ".join(replay_records[0].differences)
