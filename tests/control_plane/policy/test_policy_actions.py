"""Unit tests: action executors (allow/block/degrade/halt/kill/recovery)."""

from __future__ import annotations

import pytest

from services.control_plane.actions import ActionRequest, get_executor
from services.control_plane.policy.policy_action import (
    PolicyAction,
    PolicyActionType,
)
from services.control_plane.policy.policy_context import (
    KillSwitchState,
    PolicyContext,
)


class TestAllowTrading:
    def test_allow_requested(self):
        action = PolicyAction(PolicyActionType.ALLOW_TRADING, target="GLOBAL")
        request = get_executor(PolicyActionType.ALLOW_TRADING).execute(
            action, PolicyContext()
        )
        assert isinstance(request, ActionRequest)
        assert request.status == "REQUESTED"
        assert request.action_type is PolicyActionType.ALLOW_TRADING

    def test_allow_refused_while_kill_active(self):
        action = PolicyAction(PolicyActionType.ALLOW_TRADING, target="GLOBAL")
        request = get_executor(PolicyActionType.ALLOW_TRADING).execute(
            action,
            PolicyContext(kill_switch_state=KillSwitchState.ACTIVE),
        )
        assert request.status == "BLOCKED"
        assert "kill switch" in request.detail


class TestBlockTrading:
    def test_block_requested(self):
        action = PolicyAction(PolicyActionType.BLOCK_TRADING, target="GLOBAL")
        request = get_executor(PolicyActionType.BLOCK_TRADING).execute(
            action, PolicyContext()
        )
        assert request.status == "REQUESTED"


class TestDegradeTrading:
    def test_degrade_requested(self):
        action = PolicyAction(
            PolicyActionType.DEGRADE_TRADING, target="GLOBAL"
        )
        request = get_executor(PolicyActionType.DEGRADE_TRADING).execute(
            action, PolicyContext()
        )
        assert request.status == "REQUESTED"
        assert "reduce-only" in request.detail


class TestHaltTrading:
    def test_halt_requested(self):
        action = PolicyAction(PolicyActionType.HALT_TRADING, target="GLOBAL")
        request = get_executor(PolicyActionType.HALT_TRADING).execute(
            action, PolicyContext()
        )
        assert request.status == "REQUESTED"

    def test_halt_idempotent_when_already_halted(self):
        action = PolicyAction(PolicyActionType.HALT_TRADING, target="GLOBAL")
        request = get_executor(PolicyActionType.HALT_TRADING).execute(
            action,
            PolicyContext(kill_switch_state=KillSwitchState.ACTIVE),
        )
        assert request.status == "ALREADY_HALTED"


class TestActivateKillSwitch:
    def test_kill_without_reason_rejected(self):
        action = PolicyAction(
            PolicyActionType.ACTIVATE_KILL_SWITCH,
            target="GLOBAL",
            reason="",
        )
        request = get_executor(
            PolicyActionType.ACTIVATE_KILL_SWITCH
        ).execute(action, PolicyContext())
        assert request.status == "REJECTED"

    def test_kill_requested(self):
        action = PolicyAction(
            PolicyActionType.ACTIVATE_KILL_SWITCH,
            target="GLOBAL",
            reason="RISK_ENGINE_UNHEALTHY",
        )
        request = get_executor(
            PolicyActionType.ACTIVATE_KILL_SWITCH
        ).execute(action, PolicyContext())
        assert request.status == "REQUESTED"

    def test_kill_idempotent_when_already_active(self):
        action = PolicyAction(
            PolicyActionType.ACTIVATE_KILL_SWITCH,
            target="GLOBAL",
            reason="RISK_ENGINE_UNHEALTHY",
        )
        request = get_executor(
            PolicyActionType.ACTIVATE_KILL_SWITCH
        ).execute(
            action,
            PolicyContext(
                kill_switch_state=KillSwitchState.ACTIVE,
                kill_switch_scope="GLOBAL",
            ),
        )
        assert request.status == "ALREADY_ACTIVE"


class TestStartRecovery:
    def test_recovery_requested(self):
        action = PolicyAction(
            PolicyActionType.START_RECOVERY,
            target="POSITION",
            reason="POSITION_INTEGRITY_FAILED",
        )
        request = get_executor(PolicyActionType.START_RECOVERY).execute(
            action, PolicyContext()
        )
        assert request.status == "REQUESTED"
        assert request.target == "POSITION"


class TestRegistry:
    def test_unknown_executor_raises(self):
        from services.control_plane.policy.policy_action import (
            PolicyActionType as _T,
        )

        with pytest.raises(ValueError):
            get_executor(_T.REQUIRE_MANUAL_APPROVAL)

    def test_all_core_executors_registered(self):
        from services.control_plane import actions as actions_pkg

        actions_pkg._import_executors()
        from services.control_plane.actions import EXECUTOR_TYPES

        for action_type in (
            PolicyActionType.ALLOW_TRADING,
            PolicyActionType.BLOCK_TRADING,
            PolicyActionType.DEGRADE_TRADING,
            PolicyActionType.HALT_TRADING,
            PolicyActionType.ACTIVATE_KILL_SWITCH,
            PolicyActionType.START_RECOVERY,
        ):
            assert action_type in EXECUTOR_TYPES
