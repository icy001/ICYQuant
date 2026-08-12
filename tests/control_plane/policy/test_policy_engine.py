"""Unit tests: PolicyEngine evaluation, conflict resolution, overrides."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.domain.operational_state import OperationalState
from services.control_plane.policy.policy import Policy
from services.control_plane.policy.policy_action import (
    PolicyAction,
    PolicyActionType,
)
from services.control_plane.policy.policy_condition import condition
from services.control_plane.policy.policy_context import (
    KillSwitchState,
    MarketDataFreshness,
    PolicyContext,
    RecoveryState,
)
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_engine import (
    ManualOverride,
    OverrideScope,
    PolicyEngine,
    PolicyEvaluation,
)
from services.control_plane.policy.policy_priority import PolicyPriority
from services.control_plane.policy.policy_rule import PolicyRule


def _ctx(**kwargs) -> PolicyContext:
    return PolicyContext(**kwargs)


def _simple_engine() -> PolicyEngine:
    """Engine with one ALLOW and one HALT policy to test conflict resolution."""
    engine = PolicyEngine()
    engine.register_policy(
        Policy(
            policy_id="allow-policy",
            policy_version="1.0.0",
            name="Allow",
            priority=PolicyPriority.LOW,
        ).add_rule(
            PolicyRule(
                rule_id="allow-rule",
                condition=condition("trading_state", "equals", "TRADING_READY"),
                decision=PolicyDecision.ALLOW,
                priority=PolicyPriority.LOW,
            )
        )
    )
    engine.register_policy(
        Policy(
            policy_id="halt-policy",
            policy_version="1.0.0",
            name="Halt",
            priority=PolicyPriority.CRITICAL,
        ).add_rule(
            PolicyRule(
                rule_id="halt-rule",
                condition=condition("risk_health", "equals", "UNHEALTHY"),
                decision=PolicyDecision.HALT,
                reason="RISK_UNHEALTHY",
                priority=PolicyPriority.CRITICAL,
            )
        )
    )
    return engine


class TestRegistry:
    def test_register_and_list(self):
        engine = _simple_engine()
        assert engine.policy_count == 2
        assert {p.policy_id for p in engine.list_policies()} == {
            "allow-policy",
            "halt-policy",
        }

    def test_duplicate_registration_rejected(self):
        engine = _simple_engine()
        with pytest.raises(ValueError):
            engine.register_policy(
                Policy("allow-policy", "2.0.0", "dup")
            )

    def test_unregister(self):
        engine = _simple_engine()
        assert engine.unregister_policy("halt-policy") is True
        assert engine.unregister_policy("missing") is False
        assert engine.policy_count == 1

    def test_register_policies_varargs(self):
        engine = PolicyEngine()
        engine.register_policies(
            Policy("a", "1.0.0", "A"),
            Policy("b", "1.0.0", "B"),
        )
        assert engine.policy_count == 2

    def test_rejects_non_policy(self):
        engine = PolicyEngine()
        with pytest.raises(TypeError):
            engine.register_policy("not a policy")  # type: ignore[arg-type]


class TestEngineEvaluation:
    def test_healthy_context_allows(self):
        engine = _simple_engine()
        evaluation = engine.evaluate(_ctx())
        assert evaluation.decision is PolicyDecision.ALLOW
        assert evaluation.matched_policies == ["allow-policy"]
        assert evaluation.priority is PolicyPriority.LOW

    def test_no_policies_defaults_to_allow(self):
        engine = PolicyEngine()
        evaluation = engine.evaluate(_ctx())
        assert evaluation.decision is PolicyDecision.ALLOW
        assert evaluation.matched_policies == []

    def test_halt_wins_over_allow(self):
        engine = _simple_engine()
        evaluation = engine.evaluate(
            _ctx(risk_health=ComponentState.UNHEALTHY)
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert set(evaluation.matched_policies) == {
            "allow-policy",
            "halt-policy",
        }
        assert evaluation.reasons == ["RISK_UNHEALTHY"]

    def test_decision_for_shortcut(self):
        engine = _simple_engine()
        assert (
            engine.decision_for(_ctx(risk_health=ComponentState.UNHEALTHY))
            is PolicyDecision.HALT
        )

    def test_deterministic_evaluation(self):
        engine = _simple_engine()
        ctx = _ctx(risk_health=ComponentState.UNHEALTHY)
        at = datetime.now(timezone.utc)
        first = engine.evaluate(ctx, at=at, correlation_id="c1").to_dict()
        second = engine.evaluate(ctx, at=at, correlation_id="c1").to_dict()
        assert first == second

    def test_actions_merged_across_policies(self):
        engine = PolicyEngine()
        engine.register_policy(
            Policy(
                "p1", "1.0.0", "P1", priority=PolicyPriority.CRITICAL
            ).add_rule(
                PolicyRule(
                    rule_id="r1",
                    condition=condition("risk_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    actions=[
                        PolicyAction(
                            PolicyActionType.HALT_TRADING,
                            target="GLOBAL",
                            reason="RISK",
                        )
                    ],
                )
            )
        )
        engine.register_policy(
            Policy(
                "p2", "1.0.0", "P2", priority=PolicyPriority.CRITICAL
            ).add_rule(
                PolicyRule(
                    rule_id="r2",
                    condition=condition("risk_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    actions=[
                        PolicyAction(
                            PolicyActionType.ACTIVATE_KILL_SWITCH,
                            target="GLOBAL",
                            reason="RISK",
                        )
                    ],
                )
            )
        )
        evaluation = engine.evaluate(
            _ctx(risk_health=ComponentState.UNHEALTHY)
        )
        types = {a.action_type for a in evaluation.actions}
        assert types == {
            PolicyActionType.HALT_TRADING,
            PolicyActionType.ACTIVATE_KILL_SWITCH,
        }

    def test_policy_versions_tracked(self):
        engine = _simple_engine()
        evaluation = engine.evaluate(
            _ctx(risk_health=ComponentState.UNHEALTHY)
        )
        assert evaluation.policy_versions["halt-policy"] == "1.0.0"
        assert evaluation.policy_versions["allow-policy"] == "1.0.0"


class TestPolicyContextResolution:
    def test_dot_path_into_component_states(self):
        ctx = _ctx(
            component_states={"position_service": ComponentState.UNHEALTHY}
        )
        assert ctx.resolve("component_states.position_service") is (
            ComponentState.UNHEALTHY
        )

    def test_missing_path_returns_none(self):
        ctx = _ctx()
        assert ctx.resolve("nope.deep") is None

    def test_snapshot_round_trip(self):
        ctx = _ctx(
            risk_health=ComponentState.DEGRADED,
            correlation_id="trace-123",
        )
        restored = PolicyContext.from_dict(ctx.to_dict())
        assert restored.risk_health is ComponentState.DEGRADED
        assert restored.correlation_id == "trace-123"
        assert restored.to_dict() == ctx.to_dict()


class TestManualOverride:
    def test_override_requires_full_chain(self):
        override = ManualOverride(
            scope=OverrideScope.STRATEGY,
            scope_id="strat-a",
            requested_by="ops",
            authorized=True,
            approved=False,
            policy_valid=True,
        )
        assert override.is_effective() is False
        assert override.can_override(PolicyDecision.HALT) is False

    def test_override_effective_when_approved(self):
        override = ManualOverride(
            scope=OverrideScope.STRATEGY,
            scope_id="strat-a",
            requested_by="ops",
            authorized=True,
            approved=True,
            policy_valid=True,
        )
        assert override.is_effective() is True
        assert override.can_override(PolicyDecision.BLOCK) is True

    def test_global_override_cannot_lift_halt(self):
        override = ManualOverride(
            scope=OverrideScope.GLOBAL,
            scope_id="",
            requested_by="ops",
            authorized=True,
            approved=True,
            policy_valid=True,
        )
        assert override.is_effective() is True
        assert override.can_override(PolicyDecision.HALT) is False
        assert override.can_override(PolicyDecision.ESCALATE) is False

    def test_scope_values(self):
        assert {s.value for s in OverrideScope} == {
            "GLOBAL",
            "ACCOUNT",
            "STRATEGY",
            "INSTRUMENT",
            "VENUE",
        }


class TestEngineIntegration:
    def test_escalation_market_data_stale(self):
        """Stale ≤10s → DEGRADE; >10s → BLOCK; >60s → HALT."""
        from services.control_plane.policies.health_policy import (
            build_health_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_health_policy())

        mild = engine.evaluate(
            _ctx(
                market_data_freshness=MarketDataFreshness.STALE,
                market_data_stale_seconds=5.0,
            )
        )
        assert mild.decision is PolicyDecision.DEGRADE

        medium = engine.evaluate(
            _ctx(
                market_data_freshness=MarketDataFreshness.STALE,
                market_data_stale_seconds=30.0,
            )
        )
        assert medium.decision is PolicyDecision.BLOCK

        severe = engine.evaluate(
            _ctx(
                market_data_freshness=MarketDataFreshness.STALE,
                market_data_stale_seconds=120.0,
            )
        )
        assert severe.decision is PolicyDecision.HALT

    def test_hysteresis(self):
        from services.control_plane.policies.health_policy import (
            build_health_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_health_policy())

        # 2 failures → no threshold rule
        low = engine.evaluate(_ctx(consecutive_failures=2))
        assert "failure-threshold-block" not in low.matched_rules

        # 3 failures → BLOCK
        triggered = engine.evaluate(_ctx(consecutive_failures=3))
        assert "failure-threshold-block" in triggered.matched_rules
        assert triggered.decision is PolicyDecision.BLOCK

        # 5 healthy checks → ALLOW
        recovered = engine.evaluate(_ctx(consecutive_healthy_checks=5))
        assert "recovery-threshold-allow" in recovered.matched_rules
        assert recovered.decision is PolicyDecision.ALLOW

    def test_risk_engine_unhealthy_global_kill(self):
        from services.control_plane.policies.emergency_policy import (
            build_emergency_policy,
        )
        from services.control_plane.policies.health_policy import (
            build_health_policy,
        )
        from services.control_plane.policies.risk_policy import (
            build_risk_policy,
        )

        engine = PolicyEngine()
        engine.register_policies(
            build_emergency_policy(),
            build_risk_policy(),
            build_health_policy(),
        )
        evaluation = engine.evaluate(
            _ctx(risk_health=ComponentState.UNHEALTHY)
        )
        assert evaluation.decision is PolicyDecision.HALT
        kill_actions = [
            a
            for a in evaluation.actions
            if a.action_type is PolicyActionType.ACTIVATE_KILL_SWITCH
        ]
        assert any(a.target == "GLOBAL" for a in kill_actions)

    def test_emergency_mode_escalates(self):
        from services.control_plane.policies.emergency_policy import (
            build_emergency_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_emergency_policy())
        evaluation = engine.evaluate(
            _ctx(operational_state=OperationalState.EMERGENCY)
        )
        assert evaluation.decision is PolicyDecision.ESCALATE
        types = {a.action_type for a in evaluation.actions}
        assert PolicyActionType.ACTIVATE_KILL_SWITCH in types
        assert PolicyActionType.ESCALATE_INCIDENT in types

    def test_global_kill_active_halts(self):
        from services.control_plane.policies.emergency_policy import (
            build_emergency_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_emergency_policy())
        evaluation = engine.evaluate(
            _ctx(
                kill_switch_state=KillSwitchState.ACTIVE,
                kill_switch_scope="GLOBAL",
            )
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert evaluation.reasons == ["GLOBAL_KILL_ACTIVE"]

    def test_multiple_critical_components_kill(self):
        from services.control_plane.policies.emergency_policy import (
            build_emergency_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_emergency_policy())
        evaluation = engine.evaluate(
            _ctx(critical_unhealthy_components=2)
        )
        assert evaluation.decision is PolicyDecision.HALT
        assert "multiple-critical-failures-kill" in evaluation.matched_rules

    def test_recovery_progression(self):
        from services.control_plane.policies.recovery_policy import (
            build_recovery_policy,
        )

        engine = PolicyEngine()
        engine.register_policy(build_recovery_policy())

        running = engine.evaluate(_ctx(recovery_state=RecoveryState.RUNNING))
        assert running.decision is PolicyDecision.DEGRADE

        failed = engine.evaluate(_ctx(recovery_state=RecoveryState.FAILED))
        assert failed.decision is PolicyDecision.BLOCK
        assert PolicyActionType.START_RECOVERY in {
            a.action_type for a in failed.actions
        }

        verified = engine.evaluate(
            _ctx(
                recovery_state=RecoveryState.COMPLETED,
                position_integrity="TRUSTED",
                ledger_integrity="TRUSTED",
                risk_health=ComponentState.HEALTHY,
            )
        )
        assert verified.decision is PolicyDecision.RECOVER

    def test_evaluation_serialization_round_trip(self):
        engine = _simple_engine()
        evaluation = engine.evaluate(
            _ctx(risk_health=ComponentState.UNHEALTHY),
            correlation_id="trace-1",
        )
        restored = PolicyEvaluation.from_dict(evaluation.to_dict())
        assert restored.decision is PolicyDecision.HALT
        assert restored.correlation_id == "trace-1"
        assert restored.to_dict() == evaluation.to_dict()

    def test_rejects_non_context(self):
        engine = _simple_engine()
        with pytest.raises(TypeError):
            engine.evaluate({"risk_health": "UNHEALTHY"})  # type: ignore[arg-type]
