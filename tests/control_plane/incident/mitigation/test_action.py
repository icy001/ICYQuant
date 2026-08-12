"""Tests for mitigation actions and idempotency keys (spec section 8/15)."""
from __future__ import annotations

from uuid import UUID

from services.control_plane.incident.mitigation.action import (
    MitigationAction,
    build_idempotency_key,
)
from services.control_plane.incident.mitigation.action_type import (
    MitigationActionType,
)


def test_action_defaults():
    action = MitigationAction(
        incident_id="INC-1",
        action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
    )

    assert isinstance(action.action_id, UUID)
    assert action.incident_id == "INC-1"
    assert action.requested_by == "system"
    assert action.parameters == {}
    assert action.created_at is not None


def test_action_auto_generates_idempotency_key():
    action = MitigationAction(
        incident_id="INC-1",
        action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
    )

    assert action.idempotency_key == "INC-1:CANCEL_OPEN_ORDERS:v1"


def test_action_preserves_explicit_idempotency_key():
    action = MitigationAction(
        incident_id="INC-1",
        action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
        idempotency_key="INC-1:CANCEL_OPEN_ORDERS:v2",
    )

    assert action.idempotency_key == "INC-1:CANCEL_OPEN_ORDERS:v2"


def test_build_idempotency_key():
    assert (
        build_idempotency_key(
            "INC-1",
            MitigationActionType.KILL_SWITCH,
        )
        == "INC-1:KILL_SWITCH:v1"
    )
    assert (
        build_idempotency_key(
            "INC-1",
            MitigationActionType.CANCEL_OPEN_ORDERS,
            action_version="v3",
        )
        == "INC-1:CANCEL_OPEN_ORDERS:v3"
    )


def test_all_action_types():
    assert {t.value for t in MitigationActionType} == {
        "CANCEL_OPEN_ORDERS",
        "BLOCK_NEW_ORDERS",
        "REDUCE_POSITION",
        "FLATTEN_POSITION",
        "DISABLE_STRATEGY",
        "PAUSE_STRATEGY",
        "REDUCE_RISK_LIMIT",
        "DISABLE_EXECUTION",
        "KILL_SWITCH",
    }
