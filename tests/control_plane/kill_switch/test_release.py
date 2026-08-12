"""Unit tests: KillSwitch release flow, validation and idempotency."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.readiness import DataFreshness
from services.control_plane.kill_switch.kill_switch import (
    KillSwitch,
    KillSwitchReleaseOutcome,
)
from services.control_plane.kill_switch.kill_switch_reason import KillSwitchReason
from services.control_plane.kill_switch.kill_switch_scope import KillSwitchScope
from services.control_plane.kill_switch.kill_switch_state import KillSwitchState
from services.control_plane.commands.release_kill_switch import (
    ReleaseKillSwitch,
    release_precondition_blocks,
)
from services.control_plane.trading_gate.gate_context import (
    GateContext,
    OrderContext,
    RiskDecision,
)
from services.control_plane.trading_gate.gate_reason import GateReason

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def activate(ks, scope=KillSwitchScope.GLOBAL, scope_id=None):
    ks.activate(
        scope=scope,
        scope_id=scope_id,
        reason=KillSwitchReason.EMERGENCY,
        actor="operator-001",
        now=NOW,
    )


def healthy_context() -> GateContext:
    return GateContext(
        system_state=SystemState.READY,
        trading_state=TradingState.TRADING_READY,
        operational_state=OperationalState.NORMAL,
        risk_health=HealthStatus.HEALTHY,
        position_health=HealthStatus.HEALTHY,
        ledger_health=HealthStatus.HEALTHY,
        execution_health=HealthStatus.HEALTHY,
        event_bus_health=HealthStatus.HEALTHY,
        market_data_freshness=DataFreshness.FRESH,
        risk_decision=RiskDecision.APPROVED,
        order=OrderContext(order_id="ORD-1"),
    )


class TestReleaseFlow:
    def test_release_is_two_phase(self):
        ks = KillSwitch()
        activate(ks)
        requested = ks.request_release(KillSwitchScope.GLOBAL, now=NOW)
        assert requested.outcome is KillSwitchReleaseOutcome.RELEASE_REQUESTED
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.RELEASING
        completed = ks.complete_release(KillSwitchScope.GLOBAL, now=NOW)
        assert completed.outcome is KillSwitchReleaseOutcome.RELEASED
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.INACTIVE

    def test_release_with_validation_passes(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        result = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert result.outcome is KillSwitchReleaseOutcome.RELEASED
        assert result.event is not None
        assert result.event.event_type == "KILL_SWITCH_RELEASED"
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.INACTIVE

    def test_release_blocked_when_risk_unhealthy(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        context.risk_health = HealthStatus.UNHEALTHY
        result = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_BLOCKED
        assert GateReason.RISK_ENGINE_UNHEALTHY in result.blocked_reasons
        # Switch stays ACTIVE — release is not a blind reopen.
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.ACTIVE

    def test_release_blocked_when_system_not_ready(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        context.system_state = SystemState.HALTED
        result = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_BLOCKED
        assert GateReason.SYSTEM_NOT_READY in result.blocked_reasons

    def test_release_blocked_when_data_stale(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        context.market_data_freshness = DataFreshness.EXPIRED
        result = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_BLOCKED
        assert GateReason.MARKET_DATA_STALE in result.blocked_reasons


class TestReleaseIdempotency:
    def test_release_inactive_is_already_released(self):
        ks = KillSwitch()
        result = ks.release(KillSwitchScope.GLOBAL, now=NOW)
        assert result.outcome is KillSwitchReleaseOutcome.ALREADY_RELEASED

    def test_release_unknown_scope_is_already_released(self):
        ks = KillSwitch()
        result = ks.release(KillSwitchScope.STRATEGY, scope_id="NOPE", now=NOW)
        assert result.outcome is KillSwitchReleaseOutcome.ALREADY_RELEASED

    def test_double_release_second_is_idempotent(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        first = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert first.outcome is KillSwitchReleaseOutcome.RELEASED
        second = ks.release(
            KillSwitchScope.GLOBAL,
            validate=lambda: release_precondition_blocks(context),
            now=NOW,
        )
        assert second.outcome is KillSwitchReleaseOutcome.ALREADY_RELEASED


class TestReleaseCommand:
    def test_release_command_without_context_requests_release(self):
        ks = KillSwitch()
        activate(ks)
        result = ReleaseKillSwitch(
            scope=KillSwitchScope.GLOBAL, actor="operator-001", now=NOW
        ).execute(ks)
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_REQUESTED
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.RELEASING

    def test_release_command_with_healthy_context_releases(self):
        ks = KillSwitch()
        activate(ks)
        result = ReleaseKillSwitch(
            scope=KillSwitchScope.GLOBAL, actor="operator-001", now=NOW
        ).execute(ks, context=healthy_context())
        assert result.outcome is KillSwitchReleaseOutcome.RELEASED
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.INACTIVE

    def test_release_command_with_bad_context_blocks(self):
        ks = KillSwitch()
        activate(ks)
        context = healthy_context()
        context.event_bus_health = HealthStatus.UNHEALTHY
        result = ReleaseKillSwitch(
            scope=KillSwitchScope.GLOBAL, actor="operator-001", now=NOW
        ).execute(ks, context=context)
        assert result.outcome is KillSwitchReleaseOutcome.RELEASE_BLOCKED
        assert GateReason.EVENT_BUS_UNHEALTHY in result.blocked_reasons
        assert ks.get(KillSwitchScope.GLOBAL).state is KillSwitchState.ACTIVE

    def test_release_scoped_command(self):
        ks = KillSwitch()
        activate(ks, scope=KillSwitchScope.STRATEGY, scope_id="ALPHA")
        result = ReleaseKillSwitch(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            actor="operator-001",
            now=NOW,
        ).execute(ks, context=healthy_context())
        assert result.outcome is KillSwitchReleaseOutcome.RELEASED
        assert ks.get(KillSwitchScope.STRATEGY, "ALPHA").state is KillSwitchState.INACTIVE


class TestPreconditions:
    def test_all_healthy_has_no_blocks(self):
        assert release_precondition_blocks(healthy_context()) == []

    def test_ledger_untrusted_blocks(self):
        context = healthy_context()
        context.ledger_health = HealthStatus.UNHEALTHY
        assert GateReason.LEDGER_STATE_UNTRUSTED in release_precondition_blocks(context)

    def test_recovery_active_blocks(self):
        from services.control_plane.recovery.recovery_state import RecoveryState

        context = healthy_context()
        context.active_recovery = RecoveryState.RECOVERING
        assert GateReason.RECOVERY_IN_PROGRESS in release_precondition_blocks(context)
