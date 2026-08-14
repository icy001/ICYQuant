"""
Risk policy evaluation pipeline.

The pipeline is a hard-constraint decision system, not a scoring system:
the first policy that rejects wins (fail-fast / first-reject-wins).

Since Commit 41 Part 1.3 the evaluator also produces the immutable
``RiskPolicyTrace``: every policy that was *actually executed* is recorded
with its outcome in deterministic order.  Policies that were never run
(because an earlier policy already rejected) do NOT appear in the trace,
so the audit trail never fabricates evaluations.

An evaluation ``ERROR`` is distinct from a ``REJECT``: the rule could not
complete its check (e.g. market data unavailable).  The evaluator fails
closed and answers ``REJECTED``, but the trace keeps ``ERROR`` so the audit
record preserves the real cause.
"""

from __future__ import annotations

from dataclasses import replace

from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision, RiskDecisionStatus
from ..policies.base import RiskPolicy
from ..policy_trace import (
    STATUS_ERROR,
    STATUS_PASS,
    STATUS_REJECT,
    PolicyEvaluationResult,
    RiskPolicyTrace,
)


class RiskPolicyEvaluator:

    def __init__(self, policies: list[RiskPolicy]):
        self._policies = policies

    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:
        evaluations: list[PolicyEvaluationResult] = []

        for index, policy in enumerate(self._policies, start=1):
            try:
                decision = policy.evaluate(context)
            except Exception as exc:  # noqa: BLE001 - fail closed, keep cause
                evaluations.append(
                    PolicyEvaluationResult(
                        policy_name=policy.policy_id,
                        status=STATUS_ERROR,
                        reason=str(exc),
                        evaluation_order=index,
                    )
                )
                return RiskDecision(
                    status=RiskDecisionStatus.REJECTED,
                    reason_code="POLICY_EVALUATION_ERROR",
                    reason=(
                        f"risk policy {policy.policy_id} failed to "
                        f"evaluate: {exc}"
                    ),
                    policy_id=policy.policy_id,
                    correlation_id=context.correlation_id,
                    causation_id=context.causation_id,
                    lineage_id=context.lineage_id,
                    policy_trace=RiskPolicyTrace(evaluations=tuple(evaluations)),
                )

            evaluations.append(
                PolicyEvaluationResult(
                    policy_name=policy.policy_id,
                    status=(
                        STATUS_REJECT
                        if decision.status == RiskDecisionStatus.REJECTED
                        else STATUS_PASS
                    ),
                    reason=decision.reason,
                    evaluation_order=index,
                )
            )

            if decision.status == RiskDecisionStatus.REJECTED:
                return replace(
                    decision,
                    policy_trace=RiskPolicyTrace(evaluations=tuple(evaluations)),
                )

        return RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            reason_code="ALL_POLICIES_PASSED",
            reason="all risk policies passed",
            policy_id="risk_pipeline",
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            lineage_id=context.lineage_id,
            policy_trace=RiskPolicyTrace(evaluations=tuple(evaluations)),
        )
