"""
Risk decision trace builder (Commit 41 Part 1.5).

Builds the immutable ``RiskDecisionTrace`` for an already-formed decision,
without re-running any Risk rule.

The builder is a pure mapping from the decision-time inputs to the trace:

    context_snapshot  -> frozen dict of the exact decision-time context
    policy_trace      -> evaluated_rules (executed, in order)
                         triggered_rules (REJECT / ERROR, in order)
    decision          -> the final decision that was actually produced

``evaluated_rules`` / ``triggered_rules`` are derived from the executed
``RiskPolicyTrace`` so the trace can never contradict the persisted audit
record (Commit 41 Part 1.3) of the same decision.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from ..context.decision_context import RiskDecisionContext
from ..context_snapshot import RiskDecisionContextSnapshot
from ..decision.risk_decision import RiskDecision
from ..domain.risk_decision_trace import RiskDecisionTrace
from ..policy_trace import STATUS_ERROR, STATUS_REJECT


class RiskDecisionTraceBuilder:
    """Builds an immutable decision trace from decision-time inputs."""

    def build(
        self,
        *,
        decision_id: str,
        request_id: str,
        context: RiskDecisionContext,
        decision: RiskDecision,
        created_at: datetime,
    ) -> RiskDecisionTrace:
        policy_trace = decision.policy_trace
        evaluations = (
            policy_trace.evaluations if policy_trace is not None else ()
        )

        evaluated_rules = tuple(
            evaluation.policy_name for evaluation in evaluations
        )
        triggered_rules = tuple(
            evaluation.policy_name
            for evaluation in evaluations
            if evaluation.status in (STATUS_REJECT, STATUS_ERROR)
        )
        context_snapshot = asdict(
            RiskDecisionContextSnapshot.from_context(
                context,
                snapshot_at=created_at,
            )
        )

        return RiskDecisionTrace(
            decision_id=decision_id,
            request_id=request_id,
            strategy_id=context.strategy_id,
            decision=decision,
            evaluated_rules=evaluated_rules,
            triggered_rules=triggered_rules,
            context_snapshot=context_snapshot,
            created_at=created_at,
        )


__all__ = [
    "RiskDecisionTraceBuilder",
]
