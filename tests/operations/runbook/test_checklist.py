"""Checklist tests (Commit 27 Part 1.5, spec sections 7-8, 27, 36)."""

from services.operations import Checklist, ChecklistItem


def test_required_checklist():
    # spec section 36
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

    assert not checklist.all_required_completed()

    checklist.complete("risk")
    checklist.complete("recon")

    assert checklist.all_required_completed()


def test_optional_items_do_not_block():

    checklist = Checklist(
        [
            ChecklistItem(
                item_id="risk",
                description="Risk healthy",
            ),
            ChecklistItem(
                item_id="notes",
                description="Optional notes",
                required=False,
            ),
        ]
    )

    checklist.complete("risk")

    assert checklist.all_required_completed()


def test_complete_marks_item():

    checklist = Checklist(
        [
            ChecklistItem(
                item_id="risk",
                description="Risk healthy",
            ),
        ]
    )

    item = checklist.complete("risk")

    assert item.completed is True
    assert checklist.is_completed("risk")


def test_pending_and_completed():

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

    assert [i.item_id for i in checklist.pending_items] == ["recon"]
    assert [i.item_id for i in checklist.completed_items] == ["risk"]


def test_all_items_required_by_default():

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

    assert [i.required for i in checklist.items] == [True, True]
