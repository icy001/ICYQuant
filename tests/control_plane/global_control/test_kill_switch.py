"""
Tests for GlobalKillSwitch (Commit 26 Part 1.5,
spec sections 7-8, 31-33).
"""

from uuid import uuid4

import pytest

from services.control_plane.global_control import (
    GlobalControlState,
    GlobalControlTransitionError,
    KillSwitchActivation,
)
from services.control_plane.global_control.audit import (
    GlobalControlAuditEventType,
)


def _activation() -> KillSwitchActivation:
    return KillSwitchActivation(
        incident_id=uuid4(),
        reason="market disruption",
        actor="incident-responder",
    )


def test_activate_kills_global_control(kill_switch):
    kill_switch.activate(_activation())

    assert kill_switch.controller.state is GlobalControlState.KILLED


def test_activate_emits_kill_audit_event(kill_switch):
    kill_switch.activate(_activation())

    records = kill_switch.controller.audit_trail
    assert len(records) == 1
    assert (
        records[0].event_type
        is GlobalControlAuditEventType.GLOBAL_KILL_ACTIVATED
    )
    assert records[0].actor == "incident-responder"
    assert records[0].reason == "market disruption"
    assert records[0].incident_id is not None


def test_activate_is_idempotent(kill_switch):
    """连续收到多个 KILL 不产生重复副作用（spec section 31）。"""
    activation = _activation()

    kill_switch.activate(activation)
    kill_switch.activate(activation)
    kill_switch.activate(activation)

    assert kill_switch.controller.state is GlobalControlState.KILLED
    assert len(kill_switch.controller.audit_trail) == 1


def test_enter_recovery_moves_to_recovery(kill_switch):
    kill_switch.activate(_activation())

    kill_switch.enter_recovery()

    assert kill_switch.controller.state is GlobalControlState.RECOVERY


def test_enter_recovery_emits_audit_event(kill_switch):
    kill_switch.activate(_activation())

    kill_switch.enter_recovery()

    assert (
        kill_switch.controller.audit_trail[-1].event_type
        is GlobalControlAuditEventType.RECOVERY_STARTED
    )


def test_enter_recovery_requires_killed_state(kill_switch):
    """NORMAL -> RECOVERY 是非法迁移（spec section 33）。"""
    with pytest.raises(GlobalControlTransitionError):
        kill_switch.enter_recovery()


def test_enter_recovery_is_idempotent(kill_switch):
    kill_switch.activate(_activation())

    kill_switch.enter_recovery()
    kill_switch.enter_recovery()

    assert kill_switch.controller.state is GlobalControlState.RECOVERY
    assert [
        r.event_type for r in kill_switch.controller.audit_trail
    ].count(GlobalControlAuditEventType.RECOVERY_STARTED) == 1


def test_kill_switch_exposes_underlying_controller(kill_switch, controller):
    assert kill_switch.controller is controller
