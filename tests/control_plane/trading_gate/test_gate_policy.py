"""Unit tests: GatePolicy — evaluation order, reasons, severity."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.readiness import DataFreshness
from services.control_plane.kill_switch.kill_switch import KillSwitch
from services.control_plane.kill_switch.kill_switch_reason import KillSwitchReason
from services.control_plane.kill_switch.kill_switch_scope import KillSwitchScope
from services.control_plane.recovery.recovery_state import RecoveryState
from services.control_plane.trading_gate.gate_context import GateContext, OrderContext, RiskDecision
from services.control_plane.trading_gate.gate_decision import (
    GateDecision,
    GateSeverity,
)
from services.control_plane.trading_gate.gate_policy import GatePolicy
from services.control_plane.trading_gate.gate_reason import GateReason

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)

POLICY = GatePolicy(version="trading-policy-v1.3")


def healthy_context(**overrides) -> GateContext:
    ctx = GateContext(
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
        order=OrderContext(order_id="ORD-001", strategy_id="ALPHA", account_id="ACCT-1"),
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def evaluate(ctx: GateContext, kill_switch=None):
    return POLICY.evaluate(ctx, kill_switch=kill_switch, now=NOW, correlation_id="corr-1")


class TestAllow:
    def test_all_healthy_allow(self):
        record = evaluate(healthy_context())
        assert record.decision is GateDecision.ALLOW
        assert record.reason is GateReason.SYSTEM_HEALTHY
        assert record.severity is GateSeverity.INFO
        assert record.policy_version == "trading-policy-v1.3"

    def test_allow_ignores_noncritical_degradation(self):
        ctx = healthy_context(position_health=HealthStatus.DEGRADED)
        assert evaluate(ctx).decision is GateDecision.ALLOW


class TestEvaluationOrder:
    def test_kill_switch_beats_system_not_ready(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        ctx = healthy_context(system_state=SystemState.STARTING)
        record = evaluate(ctx, kill_switch=ks)
        assert record.decision is GateDecision.DENY
        assert record.reason is GateReason.EMERGENCY_HALT
        assert record.snapshot.get("kill_switch_scope") == "STRATEGY"

    def test_system_not_ready_deny(self):
        record = evaluate(healthy_context(system_state=SystemState.STARTING))
        assert record.reason is GateReason.SYSTEM_NOT_READY

    def test_risk_unhealthy_deny(self):
        record = evaluate(healthy_context(risk_health=HealthStatus.UNHEALTHY))
        assert record.decision is GateDecision.DENY
        assert record.reason is GateReason.RISK_ENGINE_UNHEALTHY
        assert record.severity is GateSeverity.CRITICAL

    def test_execution_unhealthy_deny(self):
        record = evaluate(healthy_context(execution_health=HealthStatus.UNHEALTHY))
        assert record.reason is GateReason.EXECUTION_ENGINE_UNHEALTHY

    def test_event_bus_unhealthy_deny(self):
        record = evaluate(healthy_context(event_bus_health=HealthStatus.UNHEALTHY))
        assert record.reason is GateReason.EVENT_BUS_UNHEALTHY

    def test_trading_halted_deny(self):
        record = evaluate(healthy_context(trading_state=TradingState.TRADING_HALTED))
        assert record.reason is GateReason.TRADING_HALTED

    def test_recovery_active_deny(self):
        record = evaluate(healthy_context(active_recovery=RecoveryState.RECOVERING))
        assert record.reason is GateReason.RECOVERY_IN_PROGRESS

    def test_market_data_stale_deny(self):
        record = evaluate(healthy_context(market_data_freshness=DataFreshness.STALE))
        assert record.reason is GateReason.MARKET_DATA_STALE

    def test_risk_not_approved_deny(self):
        record = evaluate(healthy_context(risk_decision=RiskDecision.REJECTED))
        assert record.reason is GateReason.RISK_NOT_APPROVED

    def test_position_untrusted_deny(self):
        record = evaluate(healthy_context(position_health=HealthStatus.UNHEALTHY))
        assert record.reason is GateReason.POSITION_STATE_UNTRUSTED
        assert record.severity is GateSeverity.CRITICAL

    def test_ledger_untrusted_deny(self):
        record = evaluate(healthy_context(ledger_health=HealthStatus.UNHEALTHY))
        assert record.reason is GateReason.LEDGER_STATE_UNTRUSTED

    def test_ledger_degraded_does_not_deny(self):
        record = evaluate(healthy_context(ledger_health=HealthStatus.DEGRADED))
        assert record.decision is GateDecision.ALLOW

    def test_emergency_operational_deny(self):
        record = evaluate(healthy_context(operational_state=OperationalState.EMERGENCY))
        assert record.reason is GateReason.EMERGENCY_HALT

    def test_maintenance_deny(self):
        record = evaluate(healthy_context(operational_state=OperationalState.MAINTENANCE))
        assert record.reason is GateReason.MAINTENANCE_MODE

    def test_manual_halt_deny(self):
        record = evaluate(healthy_context(operational_state=OperationalState.HALT))
        assert record.reason is GateReason.MANUAL_HALT


class TestKillSwitchIntegration:
    def test_global_kill_deny(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        record = evaluate(healthy_context(), kill_switch=ks)
        assert record.decision is GateDecision.DENY
        assert record.reason is GateReason.EMERGENCY_HALT

    def test_scoped_kill_only_denies_matching_strategy(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.STRATEGY,
            scope_id="ALPHA",
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        alpha = evaluate(healthy_context(), kill_switch=ks)
        beta = evaluate(
            healthy_context(
                order=OrderContext(order_id="ORD-2", strategy_id="BETA", account_id="ACCT-1")
            ),
            kill_switch=ks,
        )
        assert alpha.decision is GateDecision.DENY
        assert beta.decision is GateDecision.ALLOW

    def test_kill_switch_state_field_deny(self):
        from services.control_plane.kill_switch.kill_switch_state import KillSwitchState

        ctx = healthy_context(kill_switch_state=KillSwitchState.ACTIVE)
        record = evaluate(ctx)
        assert record.decision is GateDecision.DENY
        assert record.reason is GateReason.EMERGENCY_HALT
