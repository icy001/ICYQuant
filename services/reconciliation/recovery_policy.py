"""Recovery policy (Commit 40 Part 1.5).

Determines which repair actions may run automatically. Only deterministic
actions are auto-repairable; anything uncertain goes to manual review.
"""

from __future__ import annotations

from .models.repair import (
    RepairActionType,
    RepairPlan,
)


class RecoveryPolicy:
    """Gate that decides whether a plan may be auto-executed."""

    _AUTO_REPAIRABLE_ACTIONS = frozenset(
        {
            RepairActionType.REBUILD_POSITION,
        }
    )

    def can_auto_repair(
        self,
        plan: RepairPlan,
    ) -> bool:
        return plan.action in self._AUTO_REPAIRABLE_ACTIONS
