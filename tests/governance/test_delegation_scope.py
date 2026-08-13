"""Delegation scope — resource + action restrictions (Commit 28 Part 1.4).

Commander A 委托 ``trading:pause``，并不能自动获得 ``trading:kill``，
更不能获得 ``risk:override``。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.delegation import (
    AuthorityDelegation,
    ScopedDelegationValidator,
)

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_delegation(**overrides):
    base = dict(
        delegation_id="DEL-001",
        delegator_id="commander-001",
        delegate_id="delegate-001",
        resource="trading",
        actions=("pause",),
        valid_from=NOW - timedelta(hours=1),
        valid_until=NOW + timedelta(hours=1),
        enabled=True,
    )
    base.update(overrides)
    return AuthorityDelegation(**base)


@pytest.fixture
def validator():
    return ScopedDelegationValidator()


def test_delegation_scope():
    """Spec §29 — pause ok, kill not ok."""
    delegation = make_delegation(actions=("pause",))
    validator = ScopedDelegationValidator()

    assert validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "kill", NOW
    )


def test_resource_scope_not_transferable(validator):
    # trading:pause 的委托不能用于 risk:override —— resource 不同。
    delegation = make_delegation(actions=("pause",))
    assert not validator.is_valid(
        delegation, "delegate-001", "risk", "override", NOW
    )


def test_action_scope_with_multiple_actions(validator):
    delegation = make_delegation(actions=("pause", "resume"))
    assert validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )
    assert validator.is_valid(
        delegation, "delegate-001", "trading", "resume", NOW
    )
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "kill", NOW
    )


def test_scope_never_includes_unlisted_actions(validator):
    delegation = make_delegation(actions=("pause",))
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "kill", NOW
    )
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "resume", NOW
    )


def test_delegator_cannot_use_own_delegation(validator):
    # 委托是给 delegate 的：delegator 自己使用自己的委托无效。
    delegation = make_delegation(actions=("pause",))
    assert not validator.is_valid(
        delegation, "commander-001", "trading", "pause", NOW
    )
