"""
TradingGate — the production gate facade.

``TradingGate`` composes:

    GateContext  +  GatePolicy  +  KillSwitch  +  repository

into a single ``evaluate()`` call.  It is a **pure decision boundary**:

    ❌ never creates orders
    ❌ never modifies orders
    ❌ never modifies positions / risk state
    ✅ returns ALLOW or DENY
    ✅ records a decision snapshot for audit
    ✅ emits TRADING_BLOCKED / TRADING_GATE_CHANGED events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from ..events.trading_blocked import TradingBlocked
from ..events.trading_gate_changed import TradingGateChanged
from ..repositories.trading_gate_repository import TradingGateRepository
from .gate_context import GateContext
from .gate_decision import GateDecision, GateDecisionRecord
from .gate_policy import GatePolicy


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


@dataclass
class GateEvaluation:
    """Result of one TradingGate.evaluate() call."""

    record: GateDecisionRecord
    previous: Optional[GateDecisionRecord] = None
    changed: bool = False
    events: List[Any] = field(default_factory=list)

    @property
    def decision(self) -> GateDecision:
        return self.record.decision

    @property
    def is_allow(self) -> bool:
        return self.record.is_allow

    @property
    def is_deny(self) -> bool:
        return self.record.is_deny


class TradingGate:
    """Composes policy + kill switch + audit repository into one gate."""

    def __init__(
        self,
        policy: Optional[GatePolicy] = None,
        repository: Optional[TradingGateRepository] = None,
        kill_switch=None,
        policy_version: str = "trading-policy-v1.0",
    ) -> None:
        self.policy = policy or GatePolicy(version=policy_version)
        self.repository = repository or TradingGateRepository()
        self.kill_switch = kill_switch

    # ------------------------------------------------------------------
    # evaluate
    # ------------------------------------------------------------------

    def evaluate(
        self,
        context: GateContext,
        correlation_id: str = "",
        now: Optional[datetime] = None,
    ) -> GateEvaluation:
        now = now or _utcnow()

        record = self.policy.evaluate(
            context,
            kill_switch=self.kill_switch,
            now=now,
            correlation_id=correlation_id,
        )
        record.order_id = context.order.order_id if context.order else ""

        previous = self.repository.get_latest_for_order(record.order_id)
        self.repository.save_record(record)

        changed = previous is None or previous.decision is not record.decision
        events: List[Any] = []

        if record.is_deny:
            events.append(
                TradingBlocked(
                    order_id=record.order_id,
                    strategy_id=context.order.strategy_id if context.order else "",
                    account_id=context.order.account_id if context.order else "",
                    instrument_id=context.order.instrument_id if context.order else "",
                    reason=record.reason,
                    decision=record.decision,
                    correlation_id=correlation_id,
                    blocked_at=now,
                )
            )

        if changed and previous is not None:
            events.append(
                TradingGateChanged(
                    order_id=record.order_id,
                    previous_decision=previous.decision,
                    current_decision=record.decision,
                    reason=record.reason,
                    policy_version=self.policy.version,
                    correlation_id=correlation_id,
                    changed_at=now,
                )
            )

        return GateEvaluation(
            record=record,
            previous=previous,
            changed=changed,
            events=events,
        )
