"""Tests for services.governance.resolver — PermissionResolver (Commit 28 Part 1.2)."""

from services.governance.registry import build_standard_governance
from services.governance.resolver import PermissionResolver


def test_has_permission_when_role_holds():
    resolver = PermissionResolver(build_standard_governance())

    assert resolver.has_permission(("OPERATOR",), "trading", "pause")
    assert resolver.has_permission(("CONTROL_OPERATOR",), "trading", "kill")
    assert resolver.has_permission(("OBSERVER",), "incident", "read")


def test_any_role_satisfies():
    resolver = PermissionResolver(build_standard_governance())

    assert resolver.has_permission(("AUDITOR", "OPERATOR"), "trading", "pause")
    assert resolver.has_permission(("OPERATOR",), "trading", "pause")


def test_deny_when_no_role_holds():
    resolver = PermissionResolver(build_standard_governance())

    assert not resolver.has_permission(("OBSERVER",), "trading", "pause")
    assert not resolver.has_permission(("ADMINISTRATOR",), "trading", "kill")


def test_deny_when_permission_missing():
    resolver = PermissionResolver(build_standard_governance())

    assert not resolver.has_permission(("OPERATOR",), "trading", "kill")
    assert not resolver.has_permission(("OPERATOR",), "policy", "update")
    assert not resolver.has_permission(("CONTROL_OPERATOR",), "incident", "read")


def test_deny_for_empty_roles():
    resolver = PermissionResolver(build_standard_governance())

    assert not resolver.has_permission((), "trading", "pause")
