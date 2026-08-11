"""Test Risk Guardian — risk monitoring and breach detection."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from services.governance.risk_guardian import RiskGuardian
from services.governance.governance_state import GovernanceRuntimeState
from services.governance.control_trigger import TriggerType


class TestRiskGuardian:
    """Test risk guardian breach detection."""

    def test_no_breaches_when_normal(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(portfolio_drawdown=0.01)
        triggers = guardian.check(state)
        assert len(triggers) == 0

    def test_drawdown_watch(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(portfolio_drawdown=0.03)
        triggers = guardian.check(state)
        assert len(triggers) >= 1
        assert any(t.trigger_type == TriggerType.DRAWDOWN_BREACH for t in triggers)

    def test_drawdown_restrict(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(portfolio_drawdown=0.05)
        triggers = guardian.check(state)
        assert any(
            t.trigger_type == TriggerType.DRAWDOWN_BREACH
            for t in triggers
        )

    def test_drawdown_freeze(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(portfolio_drawdown=0.08)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.DRAWDOWN_BREACH for t in triggers)

    def test_var_breach(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(value_at_risk=0.03)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.VAR_BREACH for t in triggers)

    def test_exposure_breach(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(portfolio_exposure=0.25)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.EXPOSURE_BREACH for t in triggers)

    def test_leverage_breach(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(leverage_ratio=3.5)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.LEVERAGE_BREACH for t in triggers)

    def test_stress_breach(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(stress_score=92)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.STRESS_BREACH for t in triggers)

    def test_liquidity_breach(self):
        guardian = RiskGuardian()
        state = GovernanceRuntimeState(liquidity_score=0.15)
        triggers = guardian.check(state)
        assert any(t.trigger_type == TriggerType.LIQUIDITY_BREACH for t in triggers)

    def test_metrics(self):
        guardian = RiskGuardian()
        metrics = guardian.get_metrics()
        assert "alerts_count" in metrics
        assert "thresholds" in metrics
