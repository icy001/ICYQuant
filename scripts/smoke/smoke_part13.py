"""End-to-end smoke check for Commit 41 Part 1.3 (policy evaluation trace)."""

from datetime import datetime, timezone
from decimal import Decimal

from services.risk.context.decision_context import RiskDecisionContext
from services.risk.evaluator.policy_evaluator import RiskPolicyEvaluator
from services.risk.infrastructure.repositories.in_memory_decision_repository import (
    InMemoryRiskDecisionRepository,
)
from services.risk.policies.cash_availability import CashAvailabilityPolicy
from services.risk.policies.daily_loss_limit import DailyLossLimitPolicy
from services.risk.policies.position_limit import PositionLimitPolicy
from services.risk.policy_trace import (
    STATUS_ERROR,
    STATUS_PASS,
    STATUS_REJECT,
)
from services.risk.service.risk_decision_service import RiskDecisionService


class RecordingPublisher:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


def make_context(**overrides):
    base = dict(
        account_id="acc-1",
        strategy_id="strat-1",
        signal_id="sig-1",
        instrument_id="BTCUSDT",
        side="BUY",
        quantity=Decimal("2000"),
        price=Decimal("100"),
        available_cash=Decimal("1000000"),
        current_position=Decimal("0"),
        daily_pnl=Decimal("0"),
        daily_loss_limit=Decimal("1000"),
        max_position=Decimal("1000"),
        correlation_id="corr-1",
        causation_id="event-1",
        lineage_id="lineage-1",
    )
    base.update(overrides)
    return RiskDecisionContext(**base)


def main():
    publisher = RecordingPublisher()
    repository = InMemoryRiskDecisionRepository()
    evaluator = RiskPolicyEvaluator(
        policies=[
            DailyLossLimitPolicy(),
            PositionLimitPolicy(),
            CashAvailabilityPolicy(),
        ]
    )
    service = RiskDecisionService(
        evaluator,
        publisher,
        repository,
        decision_id_factory=lambda: "DEC-001",
        now_provider=lambda: datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc),
    )

    # First-reject-wins: daily_loss passes, position_limit rejects, cash skipped.
    decision = service.evaluate(make_context(), request_id="REQ-001")
    assert decision.status.value == "REJECTED"
    assert decision.rejected_policy == "position_limit"

    trace = repository.get_policy_trace("DEC-001")
    assert trace is not None
    print("Decision:", decision.status.value)
    print("Trace:")
    for entry in trace.evaluations:
        print(f"  {entry.evaluation_order}. {entry.policy_name} -> {entry.status}"
              f" (reason={entry.reason!r})")

    assert [e.status for e in trace.evaluations] == [STATUS_PASS, STATUS_REJECT]
    assert [e.policy_name for e in trace.evaluations] == [
        "daily_loss_limit",
        "position_limit",
    ]

    # Event carries the trace.
    event = publisher.events[0]
    assert event.policy_trace == trace

    # Immutability: persisted trace is frozen.
    try:
        trace.evaluations[0].status = STATUS_ERROR
    except Exception as exc:
        print("Immutability guard:", type(exc).__name__)
    else:
        raise SystemExit("FAIL: trace was mutable")

    # Missing decision -> None.
    assert repository.get_policy_trace("DEC-MISSING") is None

    print("OK: trace persisted, queryable and immutable")


if __name__ == "__main__":
    main()
