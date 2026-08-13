"""Recovery checklist / gate tests (Commit 27 Part 1.5,
spec sections 24-25, 39-40)."""

import pytest

from services.operations import (
    RECOVERY_CHECKLIST_ITEMS,
    build_recovery_checklist,
)
from services.operations.runbook import RecoveryGate


def test_recovery_blocked_when_checklist_incomplete():
    # spec section 39
    from services.operations import Checklist, ChecklistItem

    checklist = Checklist(
        [
            ChecklistItem(
                item_id="risk",
                description="Risk healthy",
            ),
        ]
    )

    gate = RecoveryGate()

    with pytest.raises(RuntimeError):
        gate.validate(checklist)


def test_recovery_allowed_when_all_checks_pass():
    # spec section 40
    from services.operations import Checklist, ChecklistItem

    checklist = Checklist(
        [
            ChecklistItem(
                item_id="risk",
                description="Risk healthy",
            ),
            ChecklistItem(
                item_id="recon",
                description="Reconciliation passed",
            ),
        ]
    )

    checklist.complete("risk")
    checklist.complete("recon")

    gate = RecoveryGate()

    assert gate.validate(checklist)


def test_standard_recovery_checklist_has_15_items():
    # spec section 24
    assert len(RECOVERY_CHECKLIST_ITEMS) == 15

    item_ids = [item.item_id for item in RECOVERY_CHECKLIST_ITEMS]

    assert "service_health" in item_ids
    assert "reconciliation" in item_ids
    assert "resume_trading" in item_ids
    assert all(item.required for item in RECOVERY_CHECKLIST_ITEMS)


def test_build_recovery_checklist():

    checklist = build_recovery_checklist()

    assert len(checklist.items) == 15
    assert not checklist.all_required_completed()


def test_full_recovery_checklist_passes():

    checklist = build_recovery_checklist()

    for item in checklist.items:
        checklist.complete(item.item_id)

    gate = RecoveryGate()

    assert gate.validate(checklist)


def test_recovery_checklist_missing_one_blocks():

    checklist = build_recovery_checklist()

    for item in checklist.items[:-1]:
        checklist.complete(item.item_id)

    gate = RecoveryGate()

    with pytest.raises(RuntimeError):
        gate.validate(checklist)
