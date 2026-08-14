"""Risk decision aggregation (Commit 37 Part 1.5).

A single risk rule must never decide the final order outcome. The
``RiskDecisionAggregator`` merges every rule decision into one gate decision
with a fixed priority:

.. code-block:: text

    REJECT
        ↓
    REVIEW
        ↓
    REDUCE
        ↓
    ALLOW

The accepted quantity resolves to the most restrictive reduction / allowance
across all contributing decisions.
"""

from __future__ import annotations

from collections.abc import Iterable

from services.risk.domain.decision import (
    RiskDecision,
    RiskDecisionStatus,
)


class RiskDecisionAggregator:
    """
    Aggregate multiple risk decisions into one final decision.

    Priority:

        REJECT
            ↓
        REVIEW
            ↓
        REDUCE
            ↓
        ALLOW
    """

    _PRIORITY = {
        RiskDecisionStatus.ALLOW: 0,
        RiskDecisionStatus.REDUCE: 1,
        RiskDecisionStatus.REVIEW: 2,
        RiskDecisionStatus.REJECT: 3,
    }

    def aggregate(
        self,
        decisions: Iterable[RiskDecision],
    ) -> RiskDecision:
        decisions = tuple(decisions)

        if not decisions:
            return RiskDecision.allow()

        final_status = max(
            decisions,
            key=lambda decision: self._PRIORITY[decision.status],
        ).status

        reasons: list[str] = []
        rules: list[str] = []

        for decision in decisions:
            reasons.extend(decision.reasons)
            rules.extend(decision.triggered_rules)

        accepted_quantity = self._resolve_quantity(
            decisions,
            final_status,
        )

        metadata = {
            "decision_count": len(decisions),
            "source_statuses": [
                decision.status.value
                for decision in decisions
            ],
        }

        return RiskDecision(
            status=final_status,
            accepted_quantity=accepted_quantity,
            reasons=tuple(reasons),
            triggered_rules=tuple(rules),
            metadata=metadata,
        )

    @staticmethod
    def _resolve_quantity(
        decisions: tuple[RiskDecision, ...],
        status: RiskDecisionStatus,
    ) -> float | None:

        if status == RiskDecisionStatus.REJECT:
            return 0.0

        reductions = [
            decision.accepted_quantity
            for decision in decisions
            if decision.status == RiskDecisionStatus.REDUCE
            and decision.accepted_quantity is not None
        ]

        if reductions:
            return min(reductions)

        allows = [
            decision.accepted_quantity
            for decision in decisions
            if decision.accepted_quantity is not None
        ]

        if allows:
            return min(allows)

        return None
