"""Unit tests: TradingState, TradingGate and the TradingPolicy."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.control_policy import (
    PolicyContext,
    PolicyDecision,
    PolicyResult,
    TradingPolicy,
)
from services.control_plane.domain.state_decision import StateDecision
from services.control_plane.domain.system_state import StateReasonCode
from services.control_plane.domain.trading_gate import (
    GateDecision,
    RiskIntegrity,
    Severity,
    TradingGate,
    TradingGateResult,
)
from services.control_plane.domain.trading_state import (
    TradingState,
    TradingStateMachine,
    TradingStateTransitionError,
)

NOW = datetime.now(timezone.utc)


def _healthy_states() -> dict:
    return {
        "event_bus": ComponentState.HEALTHY,
        "risk_engine": ComponentState.HEALTHY,
        "execution_engine": ComponentState.HEALTHY,
        "position_service": ComponentState.HEALTHY,
        "ledger_service": ComponentState.HEALTHY,
        "analytics": ComponentState.HEALTHY,
    }


# ============================================================
# TradingState enum
# ============================================================

class TestTradingState:
    def test_all_states_defined(self):
        expected = {
            "TRADING_DISABLED",
            "TRADING_READY",
            "TRADING_DEGRADED",
            "TRADING_HALTED",
        }
        assert {s.value for s in TradingState} == expected

    def test_properties(self):
        assert TradingState.TRADING_READY.is_ready
        assert TradingState.TRADING_HALTED.is_halted
        assert TradingState.TRADING_DISABLED.is_disabled


class TestTradingStateMachine:
    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (TradingState.TRADING_DISABLED, TradingState.TRADING_READY),
            (TradingState.TRADING_READY, TradingState.TRADING_DEGRADED),
            (TradingState.TRADING_READY, TradingState.TRADING_HALTED),
            (TradingState.TRADING_DEGRADED, TradingState.TRADING_READY),
            (TradingState.TRADING_DEGRADED, TradingState.TRADING_HALTED),
            (TradingState.TRADING_HALTED, TradingState.TRADING_READY),
            (TradingState.TRADING_HALTED, TradingState.TRADING_DEGRADED),
        ],
    )
    def test_valid_transitions(self, from_state, to_state):
        assert TradingStateMachine.can_transition(from_state, to_state)
        TradingStateMachine.assert_transition(from_state, to_state)

    def test_invalid_transition_rejected(self):
        assert not TradingStateMachine.can_transition(
            TradingState.TRADING_READY, TradingState.TRADING_DISABLED
        )
        with pytest.raises(TradingStateTransitionError):
            TradingStateMachine.assert_transition(
                TradingState.TRADING_READY, TradingState.TRADING_DISABLED
            )


# ============================================================
# TradingGate
# ============================================================

class TestTradingGate:
    def setup_method(self):
        self.gate = TradingGate()

    def test_allow_when_critical_healthy(self):
        result = self.gate.evaluate(_healthy_states(), at=NOW)
        assert result.decision is GateDecision.ALLOW
        assert result.reason is StateReasonCode.SYSTEM_HEALTHY

    def test_deny_when_event_bus_down(self):
        states = _healthy_states()
        states["event_bus"] = ComponentState.STOPPED
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.DENY
        assert result.reason is StateReasonCode.EVENT_BUS_UNAVAILABLE
        assert "event_bus" in result.blocked_components

    def test_deny_when_risk_engine_unhealthy(self):
        states = _healthy_states()
        states["risk_engine"] = ComponentState.UNHEALTHY
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.DENY
        assert result.reason is StateReasonCode.RISK_ENGINE_UNHEALTHY

    def test_deny_when_execution_engine_unhealthy(self):
        states = _healthy_states()
        states["execution_engine"] = ComponentState.RECOVERING
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.DENY
        assert result.reason is StateReasonCode.EXECUTION_ENGINE_UNHEALTHY

    def test_deny_when_critical_unknown(self):
        # UNKNOWN (heartbeat timeout) still blocks trading — safer default.
        states = _healthy_states()
        states["event_bus"] = ComponentState.UNKNOWN
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.DENY

    def test_allow_when_non_critical_down(self):
        states = _healthy_states()
        states["analytics"] = ComponentState.STOPPED
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.ALLOW

    def test_deny_when_risk_integrity_untrusted(self):
        result = self.gate.evaluate(
            _healthy_states(), risk_integrity=RiskIntegrity.UNTRUSTED, at=NOW
        )
        assert result.decision is GateDecision.DENY
        assert result.reason is StateReasonCode.RISK_INTEGRITY_DEGRADED

    def test_allow_when_risk_integrity_degraded(self):
        # DEGRADED integrity constrains trading but does not hard-block it.
        result = self.gate.evaluate(
            _healthy_states(), risk_integrity=RiskIntegrity.DEGRADED, at=NOW
        )
        assert result.decision is GateDecision.ALLOW

    def test_position_degradation_allows_gate(self):
        # Position degraded → gate still ALLOWs; TradingState carries the DEGRADED level.
        states = _healthy_states()
        states["position_service"] = ComponentState.DEGRADED
        result = self.gate.evaluate(states, at=NOW)
        assert result.decision is GateDecision.ALLOW


class TestTradingGateResultSerialization:
    def test_roundtrip(self):
        result = TradingGateResult(
            decision=GateDecision.DENY,
            reason=StateReasonCode.RISK_ENGINE_UNHEALTHY,
            severity=Severity.CRITICAL,
            source="risk_engine",
            blocked_components=["risk_engine"],
            risk_integrity=RiskIntegrity.TRUSTED,
            checked_at=NOW,
        )
        restored = TradingGateResult.from_dict(result.to_dict())
        assert restored == result


# ============================================================
# TradingPolicy
# ============================================================

class TestTradingPolicy:
    def setup_method(self):
        self.policy = TradingPolicy()

    def _evaluate(self, states, **kwargs):
        context = PolicyContext(component_states=states, **kwargs)
        return self.policy.evaluate(context)

    def test_allow_when_healthy(self):
        result = self._evaluate(_healthy_states())
        assert result.policy_name == "TRADING_POLICY"
        assert result.decision is PolicyDecision.ALLOW
        assert result.severity is Severity.INFO

    def test_deny_when_critical_unhealthy(self):
        states = _healthy_states()
        states["event_bus"] = ComponentState.STOPPED
        result = self._evaluate(states)
        assert result.decision is PolicyDecision.DENY
        assert result.severity is Severity.CRITICAL
        assert result.reason is StateReasonCode.EVENT_BUS_UNAVAILABLE

    def test_deny_when_risk_integrity_untrusted(self):
        result = self._evaluate(_healthy_states(), risk_integrity=RiskIntegrity.UNTRUSTED)
        assert result.decision is PolicyDecision.DENY
        assert result.reason is StateReasonCode.RISK_INTEGRITY_DEGRADED

    def test_review_when_position_degraded(self):
        states = _healthy_states()
        states["position_service"] = ComponentState.DEGRADED
        result = self._evaluate(states)
        assert result.decision is PolicyDecision.REVIEW
        assert result.severity is Severity.WARNING
        assert result.reason is StateReasonCode.POSITION_MISMATCH

    def test_review_when_ledger_degraded(self):
        states = _healthy_states()
        states["ledger_service"] = ComponentState.UNHEALTHY
        result = self._evaluate(states)
        assert result.decision is PolicyDecision.REVIEW
        assert result.reason is StateReasonCode.LEDGER_MISMATCH

    def test_allow_when_analytics_down(self):
        states = _healthy_states()
        states["analytics"] = ComponentState.STOPPED
        result = self._evaluate(states)
        assert result.decision is PolicyDecision.ALLOW

    def test_policy_result_serialization(self):
        result = PolicyResult(
            policy_name="TRADING_POLICY",
            decision=PolicyDecision.DENY,
            severity=Severity.CRITICAL,
            reason=StateReasonCode.RISK_ENGINE_UNHEALTHY,
            source="risk_engine",
        )
        restored = PolicyResult.from_dict(result.to_dict())
        assert restored == result


# ============================================================
# StateDecision
# ============================================================

class TestStateDecision:
    def test_from_gate_allow(self):
        gate_result = TradingGateResult(
            decision=GateDecision.ALLOW,
            reason=StateReasonCode.SYSTEM_HEALTHY,
            severity=Severity.INFO,
            checked_at=NOW,
        )
        decision = StateDecision.from_gate(gate_result)
        assert decision.decision == "TRADING_ALLOW"
        assert decision.reason is StateReasonCode.SYSTEM_HEALTHY
        assert decision.severity is Severity.INFO

    def test_from_gate_deny(self):
        result = TradingGate().evaluate(
            {"event_bus": ComponentState.STOPPED}, at=NOW
        )
        decision = StateDecision.from_gate(result)
        assert decision.decision == "TRADING_DENY"
        assert decision.reason is StateReasonCode.EVENT_BUS_UNAVAILABLE
        assert decision.severity is Severity.CRITICAL
        assert decision.source == "event_bus"

    def test_serialization_roundtrip(self):
        decision = StateDecision.from_values(
            decision="TRADING_DENY",
            reason=StateReasonCode.RISK_ENGINE_UNHEALTHY,
            severity=Severity.CRITICAL,
            source="risk_engine",
        )
        restored = StateDecision.from_dict(decision.to_dict())
        assert restored == decision

    def test_always_carries_reason(self):
        decision = StateDecision.from_values(
            decision="TRADING_ALLOW",
            reason=StateReasonCode.SYSTEM_HEALTHY,
            severity=Severity.INFO,
        )
        assert decision.reason is not None
