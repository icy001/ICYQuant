"""Authority model & resolution (Commit 28 Part 1.4).

Authority = "你能做什么"。来源：ROLE / DELEGATION / EMERGENCY。
AuthorityResolver 把 Role Authority 和 Delegated Authority 统一解析为
带有 source 标记的 Authority 集合。
"""

from datetime import datetime, timedelta, timezone

import pytest

from services.governance.authority import (
    Authority,
    AuthorityResolver,
    AuthoritySource,
    RolePermissionView,
)
from services.governance.delegation import AuthorityDelegation
from services.governance.models import Principal
from services.governance.registry import build_standard_governance

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


class TestAuthorityModel:

    def test_fields_and_source(self):
        authority = Authority(
            principal_id="commander-001",
            resource="trading",
            actions=("pause", "resume"),
            source=AuthoritySource.ROLE,
            source_id="INCIDENT_COMMANDER",
        )
        assert authority.principal_id == "commander-001"
        assert authority.resource == "trading"
        assert authority.actions == ("pause", "resume")
        assert authority.source == "ROLE"
        assert authority.source_id == "INCIDENT_COMMANDER"

    def test_allows_exact_resource_and_action(self):
        authority = Authority(
            "commander-001", "trading", ("pause", "resume"), "ROLE"
        )
        assert authority.allows("trading", "pause")
        assert authority.allows("trading", "resume")
        assert not authority.allows("trading", "kill")
        assert not authority.allows("risk", "override")

    def test_source_enum_values(self):
        assert AuthoritySource.ROLE.value == "ROLE"
        assert AuthoritySource.DELEGATION.value == "DELEGATION"
        assert AuthoritySource.EMERGENCY.value == "EMERGENCY"

    def test_source_id_optional(self):
        authority = Authority(
            "commander-001", "trading", ("pause",), "EMERGENCY"
        )
        assert authority.source_id is None


class TestAuthorityResolver:

    def test_resolve_from_role_permissions(self):
        roles = [
            RolePermissionView(
                role_id="INCIDENT_COMMANDER",
                permissions=frozenset(
                    {("trading", "pause"), ("trading", "resume")}
                ),
            )
        ]
        resolver = AuthorityResolver()
        authorities = resolver.resolve(
            "commander-001", "trading", "pause", roles, now=NOW
        )
        assert len(authorities) == 1
        assert authorities[0].source == "ROLE"
        assert authorities[0].source_id == "INCIDENT_COMMANDER"
        assert authorities[0].allows("trading", "pause")

    def test_resolve_no_match_returns_empty(self):
        roles = [
            RolePermissionView(
                role_id="OPERATOR",
                permissions=frozenset({("trading", "pause")}),
            )
        ]
        resolver = AuthorityResolver()
        assert resolver.resolve(
            "ops-001", "risk", "override", roles, now=NOW
        ) == ()

    def test_resolve_from_delegation(self):
        delegation = make_delegation(actions=("pause", "resume"))
        resolver = AuthorityResolver(delegations=(delegation,))
        authorities = resolver.resolve(
            "delegate-001", "trading", "pause", roles=(), now=NOW
        )
        assert len(authorities) == 1
        assert authorities[0].source == "DELEGATION"
        assert authorities[0].source_id == "DEL-001"

    def test_resolve_from_both_sources(self):
        roles = [
            RolePermissionView(
                role_id="INCIDENT_COMMANDER",
                permissions=frozenset({("trading", "resume")}),
            )
        ]
        delegation = make_delegation(actions=("resume",))
        resolver = AuthorityResolver(delegations=(delegation,))
        authorities = resolver.resolve(
            "delegate-001", "trading", "resume", roles, now=NOW
        )
        assert len(authorities) == 2
        assert {a.source for a in authorities} == {"ROLE", "DELEGATION"}

    def test_expired_delegation_not_resolved(self):
        delegation = make_delegation(valid_until=NOW)
        resolver = AuthorityResolver(delegations=(delegation,))
        assert resolver.resolve(
            "delegate-001", "trading", "pause", roles=(), now=NOW
        ) == ()

    def test_resolve_with_explicit_delegations_argument(self):
        # spec 签名：resolve(principal_id, resource, action, roles, delegations, now)
        delegation = make_delegation(actions=("pause",))
        resolver = AuthorityResolver()
        authorities = resolver.resolve(
            "delegate-001", "trading", "pause", (), (delegation,), NOW
        )
        assert len(authorities) == 1
        assert authorities[0].source_id == "DEL-001"

    def test_resolve_from_registry(self):
        registry = build_standard_governance()
        registry.register_principal(Principal("control-001", "Control", "operator"))
        resolver = AuthorityResolver()
        authorities = resolver.resolve_from_registry(
            "control-001",
            "trading",
            "pause",
            registry,
            role_ids=("CONTROL_OPERATOR",),
            now=NOW,
        )
        assert len(authorities) == 1
        assert authorities[0].source == "ROLE"
        assert authorities[0].source_id == "CONTROL_OPERATOR"
