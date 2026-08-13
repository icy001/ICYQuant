"""Tests for services.governance.role (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError

import pytest

from services.governance.role import (
    STANDARD_ROLE_IDS,
    STANDARD_ROLE_PERMISSIONS,
    Role,
    build_standard_roles,
)


def test_role_construction():
    role = Role(
        role_id="OPERATOR",
        name="Operator",
        description="Handles incidents and executes runbook steps.",
    )
    assert role.role_id == "OPERATOR"
    assert role.name == "Operator"
    assert role.description


def test_role_is_frozen():
    role = Role("OPERATOR", "Operator", "Handles incidents.")
    with pytest.raises(FrozenInstanceError):
        role.name = "Renamed"  # type: ignore[misc]


def test_standard_roles_include_all_seven():
    roles = build_standard_roles()
    role_ids = {role.role_id for role in roles}
    assert role_ids == set(STANDARD_ROLE_IDS)


def test_observer_role_is_read_only():
    observer_permissions = set(STANDARD_ROLE_PERMISSIONS["OBSERVER"])
    assert observer_permissions == {
        "incident:read",
        "runbook:read",
        "trading:read",
        "recovery:read",
        "audit:read",
    }
    assert not (observer_permissions & {"trading:pause", "trading:kill"})


def test_operator_role_does_not_include_trading_kill():
    operator_permissions = set(STANDARD_ROLE_PERMISSIONS["OPERATOR"])
    assert "incident:update" in operator_permissions
    assert "runbook:execute" in operator_permissions
    assert "recovery:execute" in operator_permissions
    assert "trading:kill" not in operator_permissions


def test_administrator_role_is_not_a_control_operator():
    administrator_permissions = set(STANDARD_ROLE_PERMISSIONS["ADMINISTRATOR"])
    assert {"policy:read", "policy:update", "role:read", "role:update"} <= administrator_permissions
    assert not (administrator_permissions & {"trading:pause", "trading:kill"})
