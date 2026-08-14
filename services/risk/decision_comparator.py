"""
Risk decision comparator (Commit 41 Part 1.4).

The comparator is the "why" layer of replay verification.  Merely comparing
``APPROVED`` vs ``REJECTED`` is not enough: two rejects caused by different
policies are materially different outcomes, and trace-level drift (a policy
that used to PASS now REJECTs) is exactly the signal production auditing
cares about.

Comparison dimensions:

- final ``decision``
- ``rejected_policy`` (which policy rejected, when rejected)
- ``reason``
- per-policy trace diff (status changes, newly executed, no longer executed)
"""

from __future__ import annotations

from .decision.decision_record import RiskDecisionRecord
from .decision.risk_decision import RiskDecision
from .policy_trace import (
    STATUS_NOT_EXECUTED,
    RiskPolicyTrace,
)


class RiskDecisionComparator:
    """Compares an original record against a replayed decision."""

    def compare(
        self,
        original: RiskDecisionRecord,
        replayed: RiskDecision,
    ) -> tuple[str, ...]:
        """Return the differences, or an empty tuple when both match."""
        differences: list[str] = []

        original_decision = original.decision
        replayed_decision = replayed.status.value

        if original_decision != replayed_decision:
            differences.append("decision changed")

        if original.rejected_policy != replayed.rejected_policy:
            differences.append(
                f"rejected_policy changed from {original.rejected_policy} "
                f"to {replayed.rejected_policy}"
            )

        if original.reason != replayed.reason:
            differences.append(
                f"reason changed from {original.reason} to {replayed.reason}"
            )

        differences.extend(
            self._trace_diff(
                original.policy_trace,
                replayed.policy_trace,
            )
        )

        return tuple(differences)

    @staticmethod
    def _trace_diff(
        original: RiskPolicyTrace,
        replayed: RiskPolicyTrace | None,
    ) -> list[str]:
        """Diff the two traces policy-by-policy.

        A policy that exists in one trace but not the other is reported with
        the synthetic status ``NOT_EXECUTED`` (the audit trail never
        fabricates an evaluation, and the comparator never pretends one
        happened).
        """
        replayed = replayed or RiskPolicyTrace(evaluations=())

        original_by_policy = {
            evaluation.policy_name: evaluation
            for evaluation in original.evaluations
        }
        replayed_by_policy = {
            evaluation.policy_name: evaluation
            for evaluation in replayed.evaluations
        }

        differences: list[str] = []
        for policy_name in sorted(
            set(original_by_policy) | set(replayed_by_policy)
        ):
            original_evaluation = original_by_policy.get(policy_name)
            replayed_evaluation = replayed_by_policy.get(policy_name)

            original_status = (
                original_evaluation.status
                if original_evaluation is not None
                else STATUS_NOT_EXECUTED
            )
            replayed_status = (
                replayed_evaluation.status
                if replayed_evaluation is not None
                else STATUS_NOT_EXECUTED
            )

            if original_status != replayed_status:
                differences.append(
                    f"{policy_name} changed from {original_status} "
                    f"to {replayed_status}"
                )

        return differences


__all__ = [
    "RiskDecisionComparator",
]
