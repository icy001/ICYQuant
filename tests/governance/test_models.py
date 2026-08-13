"""Tests for services.governance.models — Principal (Commit 28 Part 1.1)."""

from dataclasses import FrozenInstanceError

import pytest

from services.governance.models import Principal


def test_principal_defaults_active():
    principal = Principal(
        principal_id="ops-001",
        name="production-operator",
        principal_type="USER",
    )

    assert principal.principal_id == "ops-001"
    assert principal.name == "production-operator"
    assert principal.principal_type == "USER"
    assert principal.active is True


def test_principal_supports_actor_types():
    for actor_type in ("USER", "SERVICE", "SYSTEM", "BOT"):
        principal = Principal(
            principal_id=f"p-{actor_type.lower()}",
            name=actor_type,
            principal_type=actor_type,
        )
        assert principal.principal_type == actor_type


def test_principal_can_be_inactive():
    principal = Principal(
        principal_id="ops-099",
        name="retired-operator",
        principal_type="USER",
        active=False,
    )
    assert principal.active is False


def test_principal_is_frozen():
    principal = Principal(
        principal_id="ops-001",
        name="production-operator",
        principal_type="USER",
    )
    with pytest.raises(FrozenInstanceError):
        principal.name = "renamed"  # type: ignore[misc]
