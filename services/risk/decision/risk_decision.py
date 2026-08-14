"""
Risk decision model.

The Risk pipeline always answers with a ``RiskDecision`` instead of a plain
boolean, so the system knows why a request passed or failed, which policy
rejected it, and which trading lineage it belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..context.decision_context import RiskDecisionContext
from ..context_snapshot import (
    DEFAULT_POLICY_VERSION,
    RiskDecisionContextSnapshot,
)
from ..events.risk_decision_approved import (
    RISK_DECISION_APPROVED,
    RiskDecisionApproved,
)
from ..events.risk_decision_rejected import (
    RISK_DECISION_REJECTED,
    RiskDecisionRejected,
)
from ..policy_trace import RiskPolicyTrace
from .decision_record import RiskDecisionRecord


class RiskDecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class RiskDecision:
    status: RiskDecisionStatus
    reason_code: str | None = None
    reason: str | None = None

    policy_id: str | None = None

    correlation_id: str | None = None
    causation_id: str | None = None
    lineage_id: str | None = None

    policy_trace: RiskPolicyTrace | None = None

    @property
    def approved(self) -> bool:
        return self.status == RiskDecisionStatus.APPROVED

    @property
    def rejected_policy(self) -> str | None:
        """Policy that rejected this request, or ``None`` when approved."""
        if self.status == RiskDecisionStatus.REJECTED:
            return self.policy_id
        return None

    def to_event(
        self,
        context: RiskDecisionContext,
        *,
        decision_id: str,
        request_id: str | None,
        timestamp: datetime,
    ) -> RiskDecisionApproved | RiskDecisionRejected:
        """Export this decision as its outbound domain event.

        The event carries the full auditable payload required by the
        decision-event contract: ``decision_id``, ``request_id``,
        ``strategy_id``, ``instrument``, ``decision``, ``reason`` and
        ``timestamp``.  Rejected decisions additionally expose the
        rejecting policy.  Both event types carry the immutable
        ``policy_trace`` so consumers get the full evaluation context.
        """
        if self.status == RiskDecisionStatus.APPROVED:
            return RiskDecisionApproved(
                decision_id=decision_id,
                account_id=context.account_id,
                strategy_id=context.strategy_id,
                signal_id=context.signal_id,
                instrument_id=context.instrument_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
                request_id=request_id,
                decision=RISK_DECISION_APPROVED,
                reason=self.reason,
                timestamp=timestamp,
                policy_trace=self.policy_trace,
            )

        return RiskDecisionRejected(
            decision_id=decision_id,
            account_id=context.account_id,
            strategy_id=context.strategy_id,
            signal_id=context.signal_id,
            instrument_id=context.instrument_id,
            reason_code=self.reason_code or "",
            reason=self.reason or "",
            policy_id=self.policy_id or "",
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            lineage_id=context.lineage_id,
            request_id=request_id,
            decision=RISK_DECISION_REJECTED,
            timestamp=timestamp,
            policy_trace=self.policy_trace,
        )

    def to_record(
        self,
        context: RiskDecisionContext,
        *,
        decision_id: str,
        request_id: str,
        created_at: datetime,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> RiskDecisionRecord:
        """Export this decision as its immutable audit record.

        ``RiskDecision`` is the transient business result; the returned
        ``RiskDecisionRecord`` is the persistence model that may be stored
        and queried independently of the in-memory decision object.  The
        record embeds the ``policy_trace`` so the persisted audit trail
        keeps every executed policy evaluation.

        Since Part 1.4 the record also embeds a frozen
        ``context_snapshot`` (the exact decision-time inputs) and the
        ``policy_version`` used to evaluate them, enabling deterministic
        decision replay.
        """
        return RiskDecisionRecord(
            decision_id=decision_id,
            request_id=request_id,
            strategy_id=context.strategy_id,
            instrument=context.instrument_id,
            decision=self.status.value,
            reason=self.reason,
            rejected_policy=self.rejected_policy,
            policy_trace=self.policy_trace or RiskPolicyTrace(evaluations=()),
            context_snapshot=RiskDecisionContextSnapshot.from_context(
                context,
                snapshot_at=created_at,
            ),
            policy_version=policy_version,
            created_at=created_at,
        )
