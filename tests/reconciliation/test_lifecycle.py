"""Tests for the reconciliation lifecycle state machine."""

import pytest

from services.reconciliation.lifecycle import (
    InvalidLifecycleTransition,
    ReconciliationLifecycle,
    ReconciliationLifecycleManager,
)


def make_manager(
    initial: ReconciliationLifecycle = ReconciliationLifecycle.CREATED,
) -> ReconciliationLifecycleManager:
    return ReconciliationLifecycleManager(initial=initial)


def test_created_to_running_transition():
    manager = make_manager()

    target = manager.transition(
        ReconciliationLifecycle.CREATED,
        ReconciliationLifecycle.RUNNING,
    )

    assert target == ReconciliationLifecycle.RUNNING


def test_running_to_matched_transition():
    manager = make_manager(initial=ReconciliationLifecycle.RUNNING)

    target = manager.transition(
        ReconciliationLifecycle.RUNNING,
        ReconciliationLifecycle.MATCHED,
    )

    assert target == ReconciliationLifecycle.MATCHED


def test_running_to_mismatched_transition():
    manager = make_manager(initial=ReconciliationLifecycle.RUNNING)

    target = manager.transition(
        ReconciliationLifecycle.RUNNING,
        ReconciliationLifecycle.MISMATCHED,
    )

    assert target == ReconciliationLifecycle.MISMATCHED


def test_mismatched_to_repair_planned_transition():
    manager = make_manager(initial=ReconciliationLifecycle.MISMATCHED)

    target = manager.transition(
        ReconciliationLifecycle.MISMATCHED,
        ReconciliationLifecycle.REPAIR_PLANNED,
    )

    assert target == ReconciliationLifecycle.REPAIR_PLANNED


def test_repair_planned_to_repairing_transition():
    manager = make_manager(initial=ReconciliationLifecycle.REPAIR_PLANNED)

    target = manager.transition(
        ReconciliationLifecycle.REPAIR_PLANNED,
        ReconciliationLifecycle.REPAIRING,
    )

    assert target == ReconciliationLifecycle.REPAIRING


def test_repairing_to_verifying_transition():
    manager = make_manager(initial=ReconciliationLifecycle.REPAIRING)

    target = manager.transition(
        ReconciliationLifecycle.REPAIRING,
        ReconciliationLifecycle.VERIFYING,
    )

    assert target == ReconciliationLifecycle.VERIFYING


def test_verifying_to_recovered_transition():
    manager = make_manager(initial=ReconciliationLifecycle.VERIFYING)

    target = manager.transition(
        ReconciliationLifecycle.VERIFYING,
        ReconciliationLifecycle.RECOVERED,
    )

    assert target == ReconciliationLifecycle.RECOVERED


def test_verifying_to_manual_review_transition():
    manager = make_manager(initial=ReconciliationLifecycle.VERIFYING)

    target = manager.transition(
        ReconciliationLifecycle.VERIFYING,
        ReconciliationLifecycle.MANUAL_REVIEW,
    )

    assert target == ReconciliationLifecycle.MANUAL_REVIEW


def test_invalid_lifecycle_transition():
    manager = make_manager(initial=ReconciliationLifecycle.MATCHED)

    with pytest.raises(InvalidLifecycleTransition):
        manager.transition(
            ReconciliationLifecycle.MATCHED,
            ReconciliationLifecycle.REPAIRING,
        )


def test_created_cannot_jump_to_recovered():
    manager = make_manager()

    with pytest.raises(InvalidLifecycleTransition):
        manager.transition(
            ReconciliationLifecycle.CREATED,
            ReconciliationLifecycle.RECOVERED,
        )


def test_advance_tracks_state():
    manager = make_manager()

    manager.advance(ReconciliationLifecycle.RUNNING)
    manager.advance(ReconciliationLifecycle.MISMATCHED)
    manager.advance(ReconciliationLifecycle.REPAIR_PLANNED)
    manager.advance(ReconciliationLifecycle.REPAIRING)
    manager.advance(ReconciliationLifecycle.VERIFYING)
    manager.advance(ReconciliationLifecycle.RECOVERED)

    assert manager.state == ReconciliationLifecycle.RECOVERED


def test_advance_rejects_invalid_target():
    manager = make_manager()

    manager.advance(ReconciliationLifecycle.RUNNING)

    with pytest.raises(InvalidLifecycleTransition):
        manager.advance(ReconciliationLifecycle.RECOVERED)
