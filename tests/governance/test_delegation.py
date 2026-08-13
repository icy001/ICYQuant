"""Tests for scoped approval delegation (Commit 28 Part 1.4).

Delegation 是"限定范围内的 Authority"，不是 Role Transfer；
delegated authority cannot delegate again (A -> B ok, A -> B -> C forbidden)。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.authority import Authority, AuthoritySource
from services.governance.delegation import (
    AuthorityDelegation,
    DelegationAuthorityValidator,
    ScopedDelegationValidator,
    can_delegate,
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


class TestDelegationModel:

    def test_constructor_sets_fields(self):
        delegation = make_delegation()
        assert delegation.delegation_id == "DEL-001"
        assert delegation.delegator_id == "commander-001"
        assert delegation.delegate_id == "delegate-001"
        assert delegation.resource == "trading"
        assert delegation.actions == ("pause", "resume")
        assert delegation.valid_from < delegation.valid_until
        assert delegation.enabled is True

    def test_is_frozen(self):
        delegation = make_delegation()
        with pytest.raises(Exception):
            delegation.enabled = False

    def test_actions_normalized_to_tuple(self):
        delegation = make_delegation(actions=["pause", "resume"])
        assert isinstance(delegation.actions, tuple)
        assert delegation.actions == ("pause", "resume")


class TestScopedDelegationValidator:

    def test_valid_delegation(self, validator):
        delegation = make_delegation()
        assert validator.is_valid(
            delegation, "delegate-001", "trading", "pause", NOW
        )
        assert validator.is_valid(
            delegation, "delegate-001", "trading", "resume", NOW
        )

    def test_disabled_delegation_invalid(self, validator):
        delegation = make_delegation(enabled=False)
        assert not validator.is_valid(
            delegation, "delegate-001", "trading", "pause", NOW
        )

    def test_wrong_principal_invalid(self, validator):
        delegation = make_delegation()
        assert not validator.is_valid(
            delegation, "stranger-001", "trading", "pause", NOW
        )

    def test_wrong_resource_invalid(self, validator):
        delegation = make_delegation()
        assert not validator.is_valid(
            delegation, "delegate-001", "risk", "pause", NOW
        )

    def test_action_outside_scope_invalid(self, validator):
        delegation = make_delegation()
        assert not validator.is_valid(
            delegation, "delegate-001", "trading", "kill", NOW
        )

    def test_before_valid_from_invalid(self, validator):
        delegation = make_delegation(valid_from=NOW + timedelta(minutes=10))
        assert not validator.is_valid(
            delegation, "delegate-001", "trading", "pause", NOW
        )

    def test_at_valid_until_expired(self, validator):
        delegation = make_delegation(valid_until=NOW)
        assert not validator.is_valid(
            delegation, "delegate-001", "trading", "pause", NOW
        )


class TestDelegationChainPrevention:

    def test_role_authority_can_delegate(self):
        authority = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
            source_id="INCIDENT_COMMANDER",
        )
        assert can_delegate(authority)

    def test_delegated_authority_cannot_delegate_again(self):
        # B 的权限来自 DELEGATION —— 不能再传给 C (A -> B -> C 禁止)。
        authority = Authority(
            principal_id="commander-002",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.DELEGATION,
            source_id="DEL-001",
        )
        assert not can_delegate(authority)

    def test_emergency_authority_is_not_delegable_chain(self):
        authority = Authority(
            principal_id="commander-002",
            resource="trading",
            actions=("kill",),
            source=AuthoritySource.EMERGENCY,
        )
        # 紧急授权也是 time/scope-bound 的，不能作为"永久代理"来源。
        assert can_delegate(authority)  # 允许作为委托源头，但委托本身仍受
        # DelegationAuthorityValidator 的范围限制。


class TestDelegationAuthorityValidator:

    def test_subset_delegation_allowed(self):
        parent = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
        )
        delegation = make_delegation(actions=("pause",))
        assert DelegationAuthorityValidator().validate(parent, delegation)

    def test_delegation_cannot_escalate(self):
        """Spec §30 — delegate 永远不能拿到超过 delegator 的权限。"""
        parent = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
        )
        delegation = make_delegation(actions=("kill",))
        assert not DelegationAuthorityValidator().validate(parent, delegation)

    def test_cross_resource_escalation_denied(self):
        parent = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
        )
        delegation = make_delegation(resource="risk", actions=("override",))
        assert not DelegationAuthorityValidator().validate(parent, delegation)
