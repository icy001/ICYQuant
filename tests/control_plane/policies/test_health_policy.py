"""Unit tests: core-health-policy."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.trading_gate import RiskIntegrity
from services.control_plane.policies.health_policy import (
    POLICY_ID,
    build_health_policy,
)
from services.control_plane.policy.policy_action import PolicyActionType
from services.control_plane.policy.policy_context import (
    MarketDataFreshness,
    PolicyContext,
)
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.policy.policy_priority import PolicyPriority


def _engine() -> PolicyEngine:
    engine = PolicyEngine()
    engine.register_policy(build_health_policy())
    return engine


def _evaluate(**kwargs):
    return _engine().evaluate(PolicyContext(**kwargs))


class TestRiskEngineRules:
    def test_risk_unhealthy_global_kill(self):
        evaluation = _evaluate(risk_health=ComponentState.UNHEALTHY)
        assert evaluation.decision is PolicyDecision.HALT
        assert evaluation.priority is PolicyPriority.CRITICAL
        assert "risk-dead-kill" in evaluation.matched_rules
        kill = [
            a
            for a in evaluation.actions
            if a.action_type is PolicyActionType.ACTIVATE_KILL_SWITCH
        ]
        assert len(kill) == 1
        assert kill[0].target == "GLOBAL"

    def test_risk_degraded_restrict(self):
        evaluation = _evaluate(risk_health=ComponentState.DEGRADED)
        assert evaluation.decision is PolicyDecision.DEGRADE
        assert evaluation.priority is PolicyPriority.HIGH


class TestExecutionAndEventBus:
    def test_execution_unhealthy_halts_and_escalates(self):
        evaluation = _evaluate(execution_health=ComponentState.UNHEALTHY)
        assert evaluation.decision is PolicyDecision.HALT
        types = {a.action_type for a in evaluation.actions}
        assert PolicyActionType.ESCALATE_INCIDENT in types

    def test_event_bus_unhealthy_blocks(self):
        evaluation = _evaluate(event_bus_health=ComponentState.UNHEALTHY)
        assert evaluation.decision is PolicyDecision.BLOCK
        assert evaluation.reasons == ["EVENT_BUS_UNHEALTHY"]


class TestPositionAndLedger:
    def test_position_untrusted_blocks_and_recovers(self):
        evaluation = _evaluate(
            position_integrity=RiskIntegrity.UNTRUSTED
        )
        assert evaluation.decision is PolicyDecision.BLOCK
        types = {a.action_type for a in evaluation.actions}
        assert PolicyActionType.START_RECOVERY in types
        assert evaluation.reasons == ["POSITION_STATE_UNTRUSTED"]

    def test_position_health_unhealthy_blocks(self):
        evaluation = _evaluate(position_health=ComponentState.UNHEALTHY)
        assert evaluation.decision is PolicyDecision.BLOCK

    def test_ledger_untrusted_blocks(self):
        evaluation = _evaluate(ledger_integrity=RiskIntegrity.UNTRUSTED)
        assert evaluation.decision is PolicyDecision.BLOCK
        assert evaluation.reasons == ["LEDGER_STATE_UNTRUSTED"]


class TestMarketDataEscalation:
    def test_stale_under_10s_degrades(self):
        evaluation = _evaluate(
            market_data_freshness=MarketDataFreshness.STALE,
            market_data_stale_seconds=5.0,
        )
        assert evaluation.decision is PolicyDecision.DEGRADE
        assert "market-stale-degrade" in evaluation.matched_rules

    def test_stale_over_10s_blocks(self):
        evaluation = _evaluate(
            market_data_freshness=MarketDataFreshness.STALE,
            market_data_stale_seconds=30.0,
        )
        assert evaluation.decision is PolicyDecision.BLOCK
        assert "market-stale-block" in evaluation.matched_rules

    def test_stale_over_60s_halts(self):
        evaluation = _evaluate(
            market_data_freshness=MarketDataFreshness.STALE,
            market_data_stale_seconds=120.0,
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert "market-critical-halt" in evaluation.matched_rules


class TestHysteresis:
    def test_three_failures_block(self):
        evaluation = _evaluate(consecutive_failures=3)
        assert "failure-threshold-block" in evaluation.matched_rules
        assert evaluation.decision is PolicyDecision.BLOCK

    def test_two_failures_not_blocked(self):
        evaluation = _evaluate(consecutive_failures=2)
        assert "failure-threshold-block" not in evaluation.matched_rules

    def test_five_healthy_checks_allow(self):
        evaluation = _evaluate(consecutive_healthy_checks=5)
        assert "recovery-threshold-allow" in evaluation.matched_rules
        assert evaluation.decision is PolicyDecision.ALLOW


class TestPolicyIdentity:
    def test_policy_registered(self):
        policy = build_health_policy()
        assert policy.policy_id == POLICY_ID
        assert len(policy.rules) >= 10
