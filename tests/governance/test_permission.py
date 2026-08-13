"""Tests for services.governance.permission (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError

import pytest

from services.governance.permission import Permission, build_standard_permissions


def test_permission_construction():
    permission = Permission(
        permission_id="trading:pause",
        resource="trading",
        action="pause",
    )
    assert permission.permission_id == "trading:pause"
    assert permission.resource == "trading"
    assert permission.action == "pause"


def test_permission_is_frozen():
    permission = Permission("trading:pause", "trading", "pause")
    with pytest.raises(FrozenInstanceError):
        permission.action = "resume"  # type: ignore[misc]


def test_standard_permissions_cover_all_sections():
    permissions = build_standard_permissions()
    permission_ids = {permission.permission_id for permission in permissions}

    assert permission_ids == {
        "incident:read",
        "incident:update",
        "incident:escalate",
        "runbook:read",
        "runbook:execute",
        "runbook:approve",
        "trading:read",
        "trading:pause",
        "trading:resume",
        "trading:kill",
        "trading:failover",
        "recovery:read",
        "recovery:execute",
        "audit:read",
        "policy:read",
        "policy:update",
        "role:read",
        "role:update",
    }


def test_standard_permissions_are_unique():
    permissions = build_standard_permissions()
    permission_ids = [permission.permission_id for permission in permissions]
    assert len(permission_ids) == len(set(permission_ids))
