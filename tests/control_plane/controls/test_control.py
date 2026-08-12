"""Tests for ControlAction and control expiration (spec sections 5 and 16)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.controls.control import is_expired
from services.control_plane.controls.control_type import ControlType
from services.control_plane.controls.scope import ControlScope


def _action(**kwargs):
    kwargs.setdefault("control_type", ControlType.REDUCE_ONLY)
    kwargs.setdefault("scope", ControlScope.SYMBOL)
    kwargs.setdefault("target", "NVDA")
    kwargs.setdefault("reason", "risk reduction")
    from services.control_plane.controls.control import ControlAction

    return ControlAction(**kwargs)


def test_control_action_defaults():
    control = _action()

    assert control.control_type is ControlType.REDUCE_ONLY
    assert control.scope is ControlScope.SYMBOL
    assert control.target == "NVDA"
    assert control.reason == "risk reduction"
    assert control.incident_id is None
    assert control.expires_at is None
    assert control.metadata == {}
    assert control.created_at.tzinfo is not None


def test_control_id_is_unique():
    assert _action().control_id != _action().control_id


def test_control_action_is_frozen():
    control = _action()

    with pytest.raises(FrozenInstanceError):
        control.target = "SPY"  # type: ignore[misc]


def test_control_carries_incident_link():
    from uuid import uuid4

    incident_id = uuid4()
    control = _action(incident_id=incident_id)

    assert control.incident_id == incident_id


def test_control_carries_metadata():
    control = _action(metadata={"escalation_level": "P1", "owner": "ops"})

    assert control.metadata == {"escalation_level": "P1", "owner": "ops"}


def test_is_expired_returns_false_without_expiry():
    assert is_expired(_action(expires_at=None)) is False


def test_is_expired_false_for_future_expiry():
    future = datetime.now(timezone.utc) + timedelta(minutes=30)

    assert is_expired(_action(expires_at=future)) is False


def test_is_expired_true_for_past_expiry():
    past = datetime.now(timezone.utc) - timedelta(minutes=30)

    assert is_expired(_action(expires_at=past)) is True
