"""Tests for the recovery safety guard."""

import pytest

from services.reconciliation.models.repair import (
    RepairActionType,
    RepairPlan,
)
from services.reconciliation.safety_guard import (
    RecoverySafetyError,
    RecoverySafetyGuard,
)


def make_plan(action: RepairActionType) -> RepairPlan:
    return RepairPlan(
        action=action,
        reason="test",
        differences=(),
    )


def test_single_rebuild_attempt_is_safe():
    guard = RecoverySafetyGuard()

    guard.validate(
        make_plan(RepairActionType.REBUILD_POSITION),
        attempt=1,
    )


def test_second_attempt_is_rejected():
    guard = RecoverySafetyGuard()

    with pytest.raises(
        RecoverySafetyError,
        match="Maximum automatic repair attempt exceeded",
    ):
        guard.validate(
            make_plan(RepairActionType.REBUILD_POSITION),
            attempt=2,
        )


def test_manual_review_cannot_be_auto_executed():
    guard = RecoverySafetyGuard()

    with pytest.raises(
        RecoverySafetyError,
        match="Manual review cannot be auto-executed",
    ):
        guard.validate(
            make_plan(RepairActionType.MANUAL_REVIEW),
            attempt=1,
        )



