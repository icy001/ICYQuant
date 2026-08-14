"""Recovery safety guard (Commit 40 Part 1.5).

Blocks unsafe automatic repairs:

- repeated automatic attempts beyond the allowed maximum
- manual review plans that must never be auto-executed
"""

from __future__ import annotations

from .models.repair import (
    RepairActionType,
    RepairPlan,
)


class RecoverySafetyError(Exception):
    """Raised when an automatic repair violates the safety guard."""


class RecoverySafetyGuard:
    """Rejects unsafe automatic repair attempts."""

    def validate(
        self,
        plan: RepairPlan,
        attempt: int,
    ) -> None:
        if attempt > 1:
            raise RecoverySafetyError(
                "Maximum automatic repair attempt exceeded"
            )

        if plan.action == RepairActionType.MANUAL_REVIEW:
            raise RecoverySafetyError(
                "Manual review cannot be auto-executed"
            )
