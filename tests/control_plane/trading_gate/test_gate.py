"""Unit tests: TradingGate facade — decision, audit snapshot, events."""

from __future__ import annotations

from datetime import datetime, timezone

from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.domain.system_state import SystemState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.readiness import DataFreshness
from services.control_plane.events.trading_blocked import TradingBlocked
from services.control_plane.events.trading_gate_changed import TradingGateChanged
from services.control_plane.kill_switch.kill_switch import KillSwitch
from services.control_plane.kill_switch.kill_switch_reason import KillSwitchReason
from services.control_plane.kill_switch.kill_switch_scope import KillSwitchScope
from services.control_plane.repositories.trading_gate_repository import TradingGateRepository
from services.control_plane.trading_gate.gate import TradingGate
from services.control_plane.trading_gate.gate_context import GateContext, OrderContext, RiskDecision
from services.control_plane.trading_gate.gate_decision import GateDecision
from services.control_plane.trading_gate.gate_policy import GatePolicy
from services.control_plane.trading_gate.gate_reason import GateReason

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def make_order(order_id="ORD-001"):
    return OrderContext(
        order_id=order_id,
        strategy_id="ALPHA",
        account_id="ACCT-1",
        instrument_id="NVDA",
    )


def healthy_context(order_id="ORD-001") -> GateContext:
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
        order=make_order(order_id),
    )


def make_gate(**kwargs) -> TradingGate:
    repo = TradingGateRepository()
    return TradingGate(
        policy=GatePolicy(version="trading-policy-v1.3"),
        repository=repo,
        **kwargs,
    ), repo


class TestGateDecision:
    def test_allow(self):
        gate, repo = make_gate()
        evaluation = gate.evaluate(healthy_context(), correlation_id="corr-1", now=NOW)
        assert evaluation.is_allow is True
        assert evaluation.record.reason is GateReason.SYSTEM_HEALTHY
        assert repo.allow_count() == 1

    def test_deny(self):
        gate, repo = make_gate()
        ctx = healthy_context()
        ctx.risk_health = HealthStatus.UNHEALTHY
        evaluation = gate.evaluate(ctx, correlation_id="corr-2", now=NOW)
        assert evaluation.is_deny is True
        assert evaluation.record.reason is GateReason.RISK_ENGINE_UNHEALTHY
        assert repo.deny_count() == 1

    def test_decision_snapshot_recorded(self):
        gate, repo = make_gate()
        gate.evaluate(healthy_context(), correlation_id="corr-3", now=NOW)
        latest = repo.get_latest()
        assert latest is not None
        assert latest.policy_version == "trading-policy-v1.3"
        assert latest.correlation_id == "corr-3"
        assert latest.snapshot["system_state"] == "READY"
        assert latest.snapshot["risk_decision"] == "APPROVED"

    def test_decision_history_per_order(self):
        gate, repo = make_gate()
        gate.evaluate(healthy_context("ORD-1"), correlation_id="c1", now=NOW)
        gate.evaluate(healthy_context("ORD-2"), correlation_id="c2", now=NOW)
        assert repo.record_count() == 2
        assert repo.get_latest_for_order("ORD-1").correlation_id == "c1"
        assert repo.get_latest_for_order("ORD-2").correlation_id == "c2"

    def test_gate_does_not_modify_order(self):
        gate, _ = make_gate()
        ctx = healthy_context()
        original = ctx.order.to_dict()
        gate.evaluate(ctx, correlation_id="corr-4", now=NOW)
        assert ctx.order.to_dict() == original


class TestGateEvents:
    def test_trading_blocked_event_on_deny(self):
        gate, _ = make_gate()
        ctx = healthy_context()
        ctx.event_bus_health = HealthStatus.UNHEALTHY
        evaluation = gate.evaluate(ctx, correlation_id="corr-5", now=NOW)
        blocked = [e for e in evaluation.events if isinstance(e, TradingBlocked)]
        assert len(blocked) == 1
        assert blocked[0].order_id == "ORD-001"
        assert blocked[0].reason is GateReason.EVENT_BUS_UNHEALTHY
        assert blocked[0].decision is GateDecision.DENY

    def test_no_blocked_event_on_allow(self):
        gate, _ = make_gate()
        evaluation = gate.evaluate(healthy_context(), correlation_id="corr-6", now=NOW)
        assert all(not isinstance(e, TradingBlocked) for e in evaluation.events)

    def test_gate_changed_event_on_flip(self):
        gate, _ = make_gate()
        # First evaluation: ALLOW (no previous, so no change event).
        gate.evaluate(healthy_context(), correlation_id="c-a", now=NOW)
        # Second evaluation: DENY → changed.
        ctx = healthy_context()
        ctx.risk_health = HealthStatus.UNHEALTHY
        evaluation = gate.evaluate(ctx, correlation_id="c-b", now=NOW)
        assert evaluation.changed is True
        changed = [e for e in evaluation.events if isinstance(e, TradingGateChanged)]
        assert len(changed) == 1
        assert changed[0].previous_decision is GateDecision.ALLOW
        assert changed[0].current_decision is GateDecision.DENY
        assert changed[0].reason is GateReason.RISK_ENGINE_UNHEALTHY

    def test_no_changed_event_when_same_decision(self):
        gate, _ = make_gate()
        gate.evaluate(healthy_context(), correlation_id="c-a", now=NOW)
        evaluation = gate.evaluate(healthy_context(), correlation_id="c-b", now=NOW)
        assert evaluation.changed is False
        assert all(not isinstance(e, TradingGateChanged) for e in evaluation.events)


class TestGateWithKillSwitch:
    def test_global_kill_denies_all(self):
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        gate, repo = make_gate(kill_switch=ks)
        evaluation = gate.evaluate(healthy_context(), correlation_id="corr-7", now=NOW)
        assert evaluation.is_deny is True
        assert evaluation.record.reason is GateReason.EMERGENCY_HALT
        assert repo.deny_count() == 1

    def test_kill_switch_is_priority_zero(self):
        # Even with everything else healthy, an ACTIVE kill switch → DENY.
        ks = KillSwitch()
        ks.activate(
            scope=KillSwitchScope.GLOBAL,
            reason=KillSwitchReason.EMERGENCY,
            actor="operator-001",
            now=NOW,
        )
        gate, _ = make_gate(kill_switch=ks)
        evaluation = gate.evaluate(healthy_context(), correlation_id="corr-8", now=NOW)
        assert evaluation.is_deny is True
