"""Unit tests: trading-safety-policy."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.trading_state import TradingState
from services.control_plane.policies.trading_policy import (
    POLICY_ID,
    POLICY_VERSION,
    build_trading_policy,
)
from services.control_plane.policy.policy import Policy
from services.control_plane.policy.policy_context import PolicyContext
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import PolicyEngine
from services.control_plane.policy.policy_priority import PolicyPriority


def _engine() -> PolicyEngine:
    engine = PolicyEngine()
    engine.register_policy(build_trading_policy())
    return engine


class TestTradingPolicyDefinition:
    def test_policy_id_and_version(self):
        policy = build_trading_policy()
        assert policy.policy_id == POLICY_ID
        assert policy.policy_version == POLICY_VERSION
        assert isinstance(policy, Policy)

    def test_ready_allow(self):
        evaluation = _engine().evaluate(PolicyContext())
        assert evaluation.decision is PolicyDecision.ALLOW
        assert POLICY_ID in evaluation.matched_policies
        assert evaluation.policy_versions[POLICY_ID] == POLICY_VERSION

    def test_halted_block(self):
        evaluation = _engine().evaluate(
            PolicyContext(trading_state=TradingState.TRADING_HALTED)
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert evaluation.priority is PolicyPriority.HIGH

    def test_disabled_block(self):
        evaluation = _engine().evaluate(
            PolicyContext(trading_state=TradingState.TRADING_DISABLED)
        )
        assert evaluation.decision is PolicyDecision.BLOCK

    def test_degraded_restrict(self):
        evaluation = _engine().evaluate(
            PolicyContext(trading_state=TradingState.TRADING_DEGRADED)
        )
        assert evaluation.decision is PolicyDecision.DEGRADE

    def test_ready_but_risk_unhealthy_not_allowed(self):
        evaluation = _engine().evaluate(
            PolicyContext(risk_health=ComponentState.UNHEALTHY)
        )
        assert "trading-ready-allow" not in evaluation.matched_rules
