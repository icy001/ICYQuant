"""Tests for the recovery policy."""

from services.reconciliation.models.repair import (
    RepairActionType,
    RepairPlan,
)
from services.reconciliation.recovery_policy import RecoveryPolicy


def make_plan(action: RepairActionType) -> RepairPlan:
    return RepairPlan(
        action=action,
        reason="test",
        differences=(),
    )


def test_safe_rebuild_can_auto_repair():
    policy = RecoveryPolicy()

    assert (
        policy.can_auto_repair(
            make_plan(RepairActionType.REBUILD_POSITION)
        )
        is True
    )


def test_manual_review_cannot_auto_repair():
    policy = RecoveryPolicy()

    assert (
        policy.can_auto_repair(
            make_plan(RepairActionType.MANUAL_REVIEW)
        )
        is False
    )


def test_replay_events_cannot_auto_repair():
    policy = RecoveryPolicy()

    assert (
        policy.can_auto_repair(
            make_plan(RepairActionType.REPLAY_EVENTS)
        )
        is False
    )


def test_refresh_snapshot_cannot_auto_repair():
    policy = RecoveryPolicy()

    assert (
        policy.can_auto_repair(
            make_plan(RepairActionType.REFRESH_SNAPSHOT)
        )
        is False
    )


def test_no_action_cannot_auto_repair():
    policy = RecoveryPolicy()

    assert (
        policy.can_auto_repair(
            make_plan(RepairActionType.NO_ACTION)
        )
        is False
    )
