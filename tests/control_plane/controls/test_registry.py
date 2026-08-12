"""Tests for ControlRegistry (spec section 6)."""
from __future__ import annotations

import pytest

from services.control_plane.controls.control import ControlAction
from services.control_plane.controls.control_type import ControlType
from services.control_plane.controls.registry import (
    ControlRegistry,
    ControlRegistryError,
)
from services.control_plane.controls.scope import ControlScope


def _control(
    control_type=ControlType.REDUCE_ONLY,
    scope=ControlScope.SYMBOL,
    target="NVDA",
):
    return ControlAction(
        control_type=control_type,
        scope=scope,
        target=target,
        reason="test control",
    )


def test_active_returns_registered_control():
    registry = ControlRegistry()
    control = _control()

    registry.register(control)

    assert registry.active(scope=ControlScope.SYMBOL, target="NVDA") == [control]


def test_active_filters_by_scope_and_target():
    registry = ControlRegistry()
    nvda = _control(scope=ControlScope.SYMBOL, target="NVDA")
    spy = _control(scope=ControlScope.SYMBOL, target="SPY")
    account = _control(control_type=ControlType.BLOCK_NEW_ORDERS, scope=ControlScope.ACCOUNT, target="ACC001")

    registry.register(nvda)
    registry.register(spy)
    registry.register(account)

    assert registry.active(scope=ControlScope.SYMBOL, target="NVDA") == [nvda]
    assert registry.active(scope=ControlScope.SYMBOL, target="SPY") == [spy]
    assert registry.active(scope=ControlScope.ACCOUNT, target="ACC001") == [account]
    assert registry.active(scope=ControlScope.SYMBOL, target="GOOG") == []


def test_active_keeps_registration_order():
    registry = ControlRegistry()
    first = _control()
    second = _control()

    registry.register(first)
    registry.register(second)

    assert registry.active(scope=ControlScope.SYMBOL, target="NVDA") == [first, second]


def test_clear_removes_control():
    registry = ControlRegistry()
    control = _control()

    registry.register(control)
    assert registry.count() == 1

    registry.clear(control.control_id)

    assert registry.count() == 0
    assert registry.active(scope=ControlScope.SYMBOL, target="NVDA") == []


def test_clear_unknown_id_is_noop():
    from uuid import uuid4

    registry = ControlRegistry()
    control = _control()

    registry.register(control)
    registry.clear(uuid4())

    assert registry.count() == 1


def test_clear_only_removes_matching_control():
    registry = ControlRegistry()
    nvda = _control(target="NVDA")
    spy = _control(target="SPY")

    registry.register(nvda)
    registry.register(spy)

    registry.clear(nvda.control_id)

    assert registry.active(scope=ControlScope.SYMBOL, target="SPY") == [spy]


def test_get_returns_control_by_id():
    registry = ControlRegistry()
    control = _control()

    registry.register(control)

    assert registry.get(control.control_id) is control
    assert registry.get(control.control_id) is not None


def test_register_rejects_non_control():
    registry = ControlRegistry()

    with pytest.raises(ControlRegistryError):
        registry.register("not a control")  # type: ignore[arg-type]


def test_clear_all_empties_registry():
    registry = ControlRegistry()
    registry.register(_control())
    registry.register(_control(target="SPY"))

    registry.clear_all()

    assert registry.count() == 0
