from __future__ import annotations

from .models.difference import DifferenceType
from .models.repair import (
    RepairActionType,
    RepairPlan,
)
from .models.result import ReconciliationResult
from .models.status import ReconciliationStatus


class RepairPlanner:
    def plan(
        self,
        result: ReconciliationResult,
    ) -> RepairPlan:
        if result.status == ReconciliationStatus.MATCHED:
            return RepairPlan(
                action=RepairActionType.NO_ACTION,
                reason="Reconciliation matched",
                differences=(),
            )

        differences = result.differences

        if not differences:
            return RepairPlan(
                action=RepairActionType.MANUAL_REVIEW,
                reason="Mismatch detected without classified differences",
                differences=(),
            )

        types = {difference.type for difference in differences}

        if DifferenceType.UNKNOWN_MISMATCH in types:
            return RepairPlan(
                action=RepairActionType.MANUAL_REVIEW,
                reason="Unknown reconciliation difference requires manual review",
                differences=tuple(differences),
            )

        return RepairPlan(
            action=RepairActionType.REBUILD_POSITION,
            reason="Execution-derived position differs from current position snapshot",
            differences=tuple(differences),
        )
