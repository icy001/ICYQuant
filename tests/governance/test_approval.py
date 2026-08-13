"""Tests for services.governance.approval (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError

import pytest

from services.governance.approval import Approval, ApprovalState


def test_approval_initial_state():
    """Spec section 34 — a new approval starts PENDING."""
    approval = Approval(
        approval_id="APR-001",
        resource="trading",
        action="pause",
        requested_by="ops-001",
    )

    assert approval.state == ApprovalState.PENDING


def test_approval_states():
    assert [state.value for state in ApprovalState] == [
        "PENDING",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
    ]


def test_approval_construction():
    approval = Approval(
        approval_id="APR-002",
        resource="trading",
        action="kill",
        requested_by="commander-001",
        state=ApprovalState.APPROVED,
    )
    assert approval.approval_id == "APR-002"
    assert approval.resource == "trading"
    assert approval.action == "kill"
    assert approval.requested_by == "commander-001"
    assert approval.state == ApprovalState.APPROVED


def test_approval_is_frozen():
    approval = Approval(
        approval_id="APR-001",
        resource="trading",
        action="pause",
        requested_by="ops-001",
    )
    with pytest.raises(FrozenInstanceError):
        approval.state = ApprovalState.APPROVED  # type: ignore[misc]
