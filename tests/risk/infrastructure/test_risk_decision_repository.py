"""
Tests for the in-memory risk decision repository (Commit 41 Part 1.2/1.3).

Covers save / query by decision_id and request_id, request-level
idempotency, policy-trace queries (Commit 41 Part 1.3) and the
immutability of ``RiskDecisionRecord``.
"""

from datetime import datetime, timezone

import pytest

from decimal import Decimal

from services.risk.context_snapshot import RiskDecisionContextSnapshot
from services.risk.decision.decision_record import RiskDecisionRecord
from services.risk.infrastructure.repositories.in_memory_decision_repository import (
    InMemoryRiskDecisionRepository,
)
from services.risk.policy_trace import (
    PolicyEvaluationResult,
    RiskPolicyTrace,
)

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)

DEFAULT_SNAPSHOT = RiskDecisionContextSnapshot(
    account_id="acc-1",
    strategy_id="strat-1",
    signal_id="sig-1",
    instrument="BTCUSDT",
    side="BUY",
    current_position=Decimal("0"),
    proposed_quantity=Decimal("1"),
    available_cash=Decimal("100000"),
    daily_pnl=Decimal("-100"),
    daily_loss_limit=Decimal("-1000"),
    position_limit=Decimal("100"),
    market_price=Decimal("50000"),
    snapshot_at=FIXED_NOW,
)


def make_record(
    decision_id="DEC-001",
    request_id="REQ-001",
    decision="APPROVED",
    rejected_policy=None,
    policy_trace=None,
    context_snapshot=None,
    policy_version="risk-policy-v1",
):
    return RiskDecisionRecord(
        decision_id=decision_id,
        request_id=request_id,
        strategy_id="strat-1",
        instrument="BTCUSDT",
        decision=decision,
        reason="all risk policies passed",
        rejected_policy=rejected_policy,
        policy_trace=policy_trace or RiskPolicyTrace(evaluations=()),
        context_snapshot=context_snapshot or DEFAULT_SNAPSHOT,
        policy_version=policy_version,
        created_at=FIXED_NOW,
    )


def test_save_and_get_by_decision_id():
    repository = InMemoryRiskDecisionRepository()
    record = make_record()

    repository.save(record)

    assert repository.get_by_decision_id("DEC-001") == record


def test_save_and_get_by_request_id():
    repository = InMemoryRiskDecisionRepository()
    record = make_record()

    repository.save(record)

    assert repository.get_by_request_id("REQ-001") == record


def test_get_returns_none_when_missing():
    repository = InMemoryRiskDecisionRepository()

    assert repository.get_by_decision_id("DEC-UNKNOWN") is None
    assert repository.get_by_request_id("REQ-UNKNOWN") is None


def test_request_idempotency_rejects_second_decision_id():
    repository = InMemoryRiskDecisionRepository()
    repository.save(make_record(decision_id="DEC-001", request_id="REQ-001"))

    # REQ-001 already maps to DEC-001; generating DEC-002 must be rejected.
    with pytest.raises(ValueError, match="already exists"):
        repository.save(
            make_record(decision_id="DEC-002", request_id="REQ-001")
        )


def test_request_idempotency_allows_same_decision_id_again():
    repository = InMemoryRiskDecisionRepository()
    record = make_record(decision_id="DEC-001", request_id="REQ-001")
    repository.save(record)

    # Re-saving the exact same decision is a no-op.
    repository.save(record)

    assert repository.get_by_request_id("REQ-001") == record


def test_query_by_request_id_returns_record():
    repository = InMemoryRiskDecisionRepository()
    repository.save(make_record(decision_id="DEC-001", request_id="REQ-001"))

    record = repository.get_by_request_id("REQ-001")

    assert record is not None
    assert record.decision_id == "DEC-001"
    assert record.request_id == "REQ-001"


def test_record_is_immutable():
    record = make_record()

    with pytest.raises(Exception):
        record.decision = "REJECTED"  # type: ignore[misc]


def test_get_policy_trace_returns_trace():
    repository = InMemoryRiskDecisionRepository()
    trace = RiskPolicyTrace(
        evaluations=(
            PolicyEvaluationResult(
                policy_name="daily_loss_limit",
                status="PASS",
                reason="within limit",
                evaluation_order=1,
            ),
            PolicyEvaluationResult(
                policy_name="position_limit",
                status="REJECT",
                reason="projected position exceeds limit",
                evaluation_order=2,
            ),
        )
    )
    repository.save(
        make_record(
            decision_id="DEC-001",
            decision="REJECTED",
            rejected_policy=None,
            policy_trace=trace,
        )
    )

    assert repository.get_policy_trace("DEC-001") == trace


def test_get_policy_trace_returns_none_when_missing():
    repository = InMemoryRiskDecisionRepository()

    assert repository.get_policy_trace("DEC-UNKNOWN") is None
