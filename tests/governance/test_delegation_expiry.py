"""Delegation expiration & emergency delegation boundary (Commit 28 Part 1.4).

valid_until = 18:00 → 18:00 EXPIRED；18:01 delegate 再 Approve → DENY。
Emergency delegation 必须 time-bound、scope-bound、auto-expire，不能变成永久权限。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.delegation import (
    AuthorityDelegation,
    EmergencyDelegation,
    ScopedDelegationValidator,
)

NOW = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)


def make_delegation(**overrides):
    base = dict(
        delegation_id="DEL-001",
        delegator_id="commander-001",
        delegate_id="delegate-001",
        resource="trading",
        actions=("pause", "resume"),
        valid_from=NOW - timedelta(hours=1),
        valid_until=NOW + timedelta(hours=1),
        enabled=True,
    )
    base.update(overrides)
    return AuthorityDelegation(**base)


@pytest.fixture
def validator():
    return ScopedDelegationValidator()


def test_delegation_expired(validator):
    """Spec §28 — valid_until == now 已经是过期（now >= valid_until）。"""
    delegation = make_delegation(valid_until=NOW)
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )


def test_expired_delegation_denies_approval(validator):
    # 18:00 过期后，18:01 delegate 不能再 Approve → DENY。
    delegation = make_delegation(valid_until=NOW)
    assert not validator.is_valid(
        delegation,
        "delegate-001",
        "trading",
        "pause",
        NOW + timedelta(minutes=1),
    )


def test_not_yet_valid(validator):
    delegation = make_delegation(valid_from=NOW + timedelta(minutes=5))
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )


def test_valid_from_boundary_inclusive(validator):
    delegation = make_delegation(valid_from=NOW)
    assert validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )


def test_valid_until_boundary_exclusive(validator):
    delegation = make_delegation(valid_until=NOW)
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )


def test_disabled_delegation_expires_immediately(validator):
    delegation = make_delegation(enabled=False)
    assert not validator.is_valid(
        delegation, "delegate-001", "trading", "pause", NOW
    )


class TestEmergencyDelegation:

    def _emergency(self, **overrides):
        base = dict(
            delegation_id="DEL-EMERGENCY-001",
            delegator_id="commander-001",
            delegate_id="commander-002",
            resource="trading",
            action="kill",
            valid_from=datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc),
            valid_until=datetime(2026, 8, 13, 2, 30, tzinfo=timezone.utc),
        )
        base.update(overrides)
        return EmergencyDelegation(**base)

    def test_valid_inside_window(self):
        emergency = self._emergency()
        assert emergency.is_valid(datetime(2026, 8, 13, 2, 15, tzinfo=timezone.utc))

    def test_auto_expires_at_boundary(self):
        emergency = self._emergency()
        assert emergency.is_expired(datetime(2026, 8, 13, 2, 30, tzinfo=timezone.utc))
        assert not emergency.is_valid(datetime(2026, 8, 13, 2, 30, tzinfo=timezone.utc))

    def test_expired_after_window(self):
        emergency = self._emergency()
        assert not emergency.is_valid(datetime(2026, 8, 13, 2, 31, tzinfo=timezone.utc))

    def test_cannot_be_permanent(self):
        # 30 分钟的限制被突破 → 无效：Emergency Authority 必须 time-bound。
        emergency = self._emergency(
            valid_until=datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
        )
        assert emergency.duration_seconds > emergency.max_duration_seconds
        assert not emergency.is_valid(datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc))

    def test_disabled_invalid(self):
        emergency = self._emergency(enabled=False)
        assert not emergency.is_valid(datetime(2026, 8, 13, 2, 15, tzinfo=timezone.utc))
