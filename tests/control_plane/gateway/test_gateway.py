"""Tests for InstitutionalControlGateway (spec sections 11/12/18/21/22).

Covers the key production scenarios:

    * global kill switch blocks every new order
    * scoped controls isolate the affected target only
    * REDUCE_ONLY blocks new orders but never the close/reduce flow
    * fail-safe posture blocks new orders, never seals the reduce flow
    * control precedence is priority-driven, not registration-order-driven
    * expired temporary controls are ignored; KILL_SWITCH never auto-expires
    * registry failure degrades the gateway (fail-closed) unless fail-open
    * every decision is auditable
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.controls.control import ControlAction
from services.control_plane.controls.control_type import ControlType
from services.control_plane.controls.registry import ControlRegistry
from services.control_plane.controls.scope import ControlScope
from services.control_plane.gateway.context import (
    ControlContext,
    ControlRequest,
)
from services.control_plane.gateway.decision import (
    ControlDecision,
    ControlDecisionReason,
)
from services.control_plane.gateway.errors import GatewayError
from services.control_plane.gateway.gateway import (
    GatewayResult,
    InstitutionalControlGateway,
)
from services.control_plane.gateway.policy import GatewayPolicy
from services.control_plane.gateway.state import GatewayState


@pytest.fixture
def registry():
    return ControlRegistry()


@pytest.fixture
def gateway(registry):
    return InstitutionalControlGateway(registry)


def _control(
    control_type,
    scope,
    target,
    reason="test control",
    **kwargs,
):
    return ControlAction(
        control_type=control_type,
        scope=scope,
        target=target,
        reason=reason,
        **kwargs,
    )


def _nvda_context(**kwargs):
    defaults = {
        "account_id": "ACC001",
        "strategy_id": "alpha_nvda",
        "symbol": "NVDA",
        "venue": "NASDAQ",
    }
    defaults.update(kwargs)
    return ControlContext(**defaults)


# ----------------------------------------------------------------------
# spec section 22 — core scenarios
# ----------------------------------------------------------------------


def test_global_kill_switch_blocks_new_order(gateway, registry):
    registry.register(
        ControlAction(
            control_type=ControlType.KILL_SWITCH,
            scope=ControlScope.GLOBAL,
            target="GLOBAL",
            reason="critical incident",
        )
    )

    result = gateway.evaluate(
        ControlContext(
            strategy_id="alpha_nvda",
            symbol="NVDA",
        ),
        is_new_order=True,
    )

    assert result.decision == ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.GLOBAL_KILL_SWITCH


def test_strategy_control_does_not_block_other_strategy(gateway, registry):
    registry.register(
        ControlAction(
            control_type=ControlType.DISABLE_STRATEGY,
            scope=ControlScope.STRATEGY,
            target="alpha_nvda",
            reason="strategy incident",
        )
    )

    result = gateway.evaluate(
        ControlContext(
            strategy_id="alpha_spy",
            symbol="SPY",
        ),
        is_new_order=True,
    )

    assert result.decision == ControlDecision.ALLOW


def test_reduce_only_does_not_block_close_flow(gateway, registry):
    registry.register(
        ControlAction(
            control_type=ControlType.REDUCE_ONLY,
            scope=ControlScope.SYMBOL,
            target="NVDA",
            reason="risk reduction",
        )
    )

    result = gateway.evaluate(
        ControlContext(
            symbol="NVDA",
        ),
        is_new_order=False,
    )

    assert result.decision == ControlDecision.ALLOW


def test_gateway_fail_safe_blocks_new_orders(gateway):
    gateway.state = GatewayState.FAIL_SAFE

    result = gateway.evaluate(
        ControlContext(
            strategy_id="alpha_nvda",
        ),
        is_new_order=True,
    )

    assert result.decision == ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.EXECUTION_DISABLED


# ----------------------------------------------------------------------
# allow / reduce_only / block decisions
# ----------------------------------------------------------------------


def test_allows_when_no_active_control(gateway):
    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.ALLOW
    assert result.reason is ControlDecisionReason.NO_ACTIVE_CONTROL


def test_reduce_only_blocks_new_order(gateway, registry):
    registry.register(
        _control(ControlType.REDUCE_ONLY, ControlScope.SYMBOL, "NVDA")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.REDUCE_ONLY
    assert result.reason is ControlDecisionReason.REDUCE_ONLY_MODE


def test_disable_strategy_blocks_target_strategy(gateway, registry):
    registry.register(
        _control(ControlType.DISABLE_STRATEGY, ControlScope.STRATEGY, "alpha_nvda")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.STRATEGY_DISABLED


def test_account_block_blocks_new_order(gateway, registry):
    registry.register(
        _control(ControlType.BLOCK_NEW_ORDERS, ControlScope.ACCOUNT, "ACC001")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.ACCOUNT_BLOCKED


def test_symbol_block_blocks_new_order(gateway, registry):
    registry.register(
        _control(ControlType.BLOCK_NEW_ORDERS, ControlScope.SYMBOL, "NVDA")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.SYMBOL_BLOCKED


def test_venue_disable_blocks_new_order(gateway, registry):
    registry.register(
        _control(ControlType.DISABLE_EXECUTION, ControlScope.VENUE, "NASDAQ")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.VENUE_DISABLED


def test_global_disable_execution_blocks_new_order(gateway, registry):
    registry.register(
        _control(ControlType.DISABLE_EXECUTION, ControlScope.GLOBAL, "GLOBAL")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.EXECUTION_DISABLED


def test_scoped_block_does_not_affect_other_target(gateway, registry):
    registry.register(
        _control(ControlType.DISABLE_STRATEGY, ControlScope.STRATEGY, "alpha_nvda")
    )

    other = gateway.evaluate(
        ControlContext(strategy_id="alpha_spy", symbol="SPY"),
        is_new_order=True,
    )

    assert other.decision is ControlDecision.ALLOW


# ----------------------------------------------------------------------
# control precedence (spec section 15)
# ----------------------------------------------------------------------


def test_higher_priority_control_wins(gateway, registry):
    registry.register(
        _control(ControlType.REDUCE_ONLY, ControlScope.SYMBOL, "NVDA")
    )
    registry.register(
        _control(ControlType.BLOCK_NEW_ORDERS, ControlScope.ACCOUNT, "ACC001")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.ACCOUNT_BLOCKED


def test_priority_wins_regardless_of_registration_order(gateway, registry):
    # BLOCK_NEW_ORDERS (800) registered first, REDUCE_ONLY (600) second:
    # priority — not registration order — must decide.
    registry.register(
        _control(ControlType.BLOCK_NEW_ORDERS, ControlScope.ACCOUNT, "ACC001")
    )
    registry.register(
        _control(ControlType.REDUCE_ONLY, ControlScope.SYMBOL, "NVDA")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.ACCOUNT_BLOCKED


def test_kill_switch_overrides_other_controls(gateway, registry):
    registry.register(
        _control(ControlType.REDUCE_ONLY, ControlScope.SYMBOL, "NVDA")
    )
    registry.register(
        _control(ControlType.KILL_SWITCH, ControlScope.GLOBAL, "GLOBAL")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.GLOBAL_KILL_SWITCH


# ----------------------------------------------------------------------
# expiration (spec section 16)
# ----------------------------------------------------------------------


def _past(delta_minutes=30) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=delta_minutes)


def test_expired_temporary_control_is_ignored(gateway, registry):
    registry.register(
        _control(
            ControlType.REDUCE_ONLY,
            ControlScope.SYMBOL,
            "NVDA",
            expires_at=_past(),
        )
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.ALLOW


def test_active_temporary_control_is_enforced(gateway, registry):
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    registry.register(
        _control(
            ControlType.REDUCE_ONLY,
            ControlScope.SYMBOL,
            "NVDA",
            expires_at=future,
        )
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.REDUCE_ONLY


def test_kill_switch_never_auto_expires(gateway, registry):
    registry.register(
        _control(
            ControlType.KILL_SWITCH,
            ControlScope.GLOBAL,
            "GLOBAL",
            reason="critical incident",
            expires_at=_past(delta_minutes=10),
        )
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.GLOBAL_KILL_SWITCH


# ----------------------------------------------------------------------
# explicit recovery (spec section 17)
# ----------------------------------------------------------------------


def test_kill_switch_requires_explicit_clear(gateway, registry):
    control = _control(
        ControlType.KILL_SWITCH,
        ControlScope.GLOBAL,
        "GLOBAL",
        reason="critical incident",
    )
    registry.register(control)

    assert gateway.evaluate(_nvda_context(), is_new_order=True).decision is ControlDecision.BLOCK

    # Recovery is explicit: clear the control, never a silent TTL.
    registry.clear(control.control_id)

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.ALLOW


def test_temporary_control_recovers_after_expiry(gateway, registry):
    registry.register(
        _control(
            ControlType.REDUCE_ONLY,
            ControlScope.SYMBOL,
            "NVDA",
            expires_at=_past(),
        )
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.ALLOW


# ----------------------------------------------------------------------
# fail-safe behaviour (spec section 18)
# ----------------------------------------------------------------------


class _BrokenRegistry:
    """A registry whose backing store is unavailable."""

    def active(self, *, scope, target):
        raise RuntimeError("registry unavailable")

    def register(self, control):
        raise RuntimeError("registry unavailable")


def test_registry_failure_degrades_to_fail_safe():
    gateway = InstitutionalControlGateway(_BrokenRegistry())

    result = gateway.evaluate(
        ControlContext(strategy_id="alpha_nvda"),
        is_new_order=True,
    )

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.EXECUTION_DISABLED
    assert gateway.state is GatewayState.FAIL_SAFE
    assert gateway.failure_reason == "registry unavailable"


def test_fail_safe_never_seals_reduce_flow():
    gateway = InstitutionalControlGateway(_BrokenRegistry())

    result = gateway.evaluate(
        ControlContext(strategy_id="alpha_nvda", symbol="NVDA"),
        is_new_order=False,
    )

    assert result.decision is ControlDecision.ALLOW


def test_fail_open_policy_allows_on_failure():
    gateway = InstitutionalControlGateway(
        _BrokenRegistry(),
        GatewayPolicy(fail_open=True),
    )

    result = gateway.evaluate(
        ControlContext(strategy_id="alpha_nvda"),
        is_new_order=True,
    )

    assert result.decision is ControlDecision.ALLOW
    assert gateway.state is GatewayState.HEALTHY


def test_optional_registry_failure_does_not_degrade():
    gateway = InstitutionalControlGateway(
        _BrokenRegistry(),
        GatewayPolicy(require_control_registry=False),
    )

    result = gateway.evaluate(
        ControlContext(strategy_id="alpha_nvda"),
        is_new_order=True,
    )

    assert result.decision is ControlDecision.ALLOW
    assert gateway.state is GatewayState.HEALTHY


def test_disabled_state_blocks_new_order(gateway):
    gateway.state = GatewayState.DISABLED

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.EXECUTION_DISABLED


def test_degraded_state_still_evaluates_controls(gateway, registry):
    gateway.state = GatewayState.DEGRADED
    registry.register(
        _control(ControlType.DISABLE_STRATEGY, ControlScope.STRATEGY, "alpha_nvda")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.STRATEGY_DISABLED


# ----------------------------------------------------------------------
# explicit degradation API
# ----------------------------------------------------------------------


def test_degrade_transitions_to_fail_safe(gateway):
    gateway.degrade("risk engine unavailable")

    assert gateway.state is GatewayState.FAIL_SAFE
    assert gateway.failure_reason == "risk engine unavailable"

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK


# ----------------------------------------------------------------------
# gateway audit (spec section 21)
# ----------------------------------------------------------------------


def test_block_is_audited(gateway, registry):
    registry.register(
        _control(ControlType.KILL_SWITCH, ControlScope.GLOBAL, "GLOBAL")
    )

    gateway.evaluate(
        _nvda_context(account_id="ACC001", strategy_id="alpha_nvda", symbol="NVDA"),
        is_new_order=True,
    )

    assert len(gateway.audit_trail) == 1
    record = gateway.audit_trail[0]
    assert record["decision"] == "BLOCK"
    assert record["reason"] == "GLOBAL_KILL_SWITCH"
    assert record["strategy_id"] == "alpha_nvda"
    assert record["symbol"] == "NVDA"
    assert record["account_id"] == "ACC001"


def test_allow_is_audited(gateway):
    gateway.evaluate(_nvda_context(), is_new_order=True)

    assert len(gateway.audit_trail) == 1
    assert gateway.audit_trail[0]["decision"] == "ALLOW"
    assert gateway.audit_trail[0]["reason"] == "NO_ACTIVE_CONTROL"


def test_auditor_callback_receives_records(gateway, registry):
    received: list[dict] = []
    gateway.auditor = received.append

    registry.register(
        _control(ControlType.DISABLE_STRATEGY, ControlScope.STRATEGY, "alpha_nvda")
    )

    gateway.evaluate(_nvda_context(), is_new_order=True)

    assert len(received) == 1
    assert received[0]["control_type"] == "DISABLE_STRATEGY"


def test_audit_links_control_id_and_type(gateway, registry):
    control = _control(ControlType.REDUCE_ONLY, ControlScope.SYMBOL, "NVDA")
    registry.register(control)

    gateway.evaluate(_nvda_context(), is_new_order=True)

    record = gateway.audit_trail[0]
    assert record["control_id"] == str(control.control_id)
    assert record["control_type"] == "REDUCE_ONLY"


def test_auditor_failure_does_not_break_gating(gateway, registry):
    def _boom(record):
        raise RuntimeError("audit sink down")

    gateway.auditor = _boom
    registry.register(
        _control(ControlType.KILL_SWITCH, ControlScope.GLOBAL, "GLOBAL")
    )

    result = gateway.evaluate(_nvda_context(), is_new_order=True)

    assert result.decision is ControlDecision.BLOCK


# ----------------------------------------------------------------------
# ControlRequest admission (spec section 19)
# ----------------------------------------------------------------------


def test_admit_uses_request_context(gateway, registry):
    registry.register(
        _control(ControlType.BLOCK_NEW_ORDERS, ControlScope.ACCOUNT, "ACC001")
    )

    request = ControlRequest(
        context=ControlContext(account_id="ACC001", symbol="NVDA"),
        action="BUY",
        is_new_order=True,
    )

    result = gateway.admit(request)

    assert result.decision is ControlDecision.BLOCK
    assert result.reason is ControlDecisionReason.ACCOUNT_BLOCKED


def test_admit_rejects_invalid_request(gateway):
    with pytest.raises(GatewayError):
        gateway.admit("not a request")  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# result metadata
# ----------------------------------------------------------------------


def test_result_is_dataclass():
    result = GatewayResult(
        decision=ControlDecision.ALLOW,
        reason=ControlDecisionReason.NO_ACTIVE_CONTROL,
    )

    assert result.decision is ControlDecision.ALLOW
    assert result.matched_control is None
