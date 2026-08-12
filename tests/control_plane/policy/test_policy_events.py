"""Unit tests: POLICY_EVALUATED / POLICY_TRIGGERED / POLICY_ACTION_REQUESTED."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.events.policy_action_requested import (
    PolicyActionRequested,
)
from services.control_plane.events.policy_evaluated import PolicyEvaluated
from services.control_plane.events.policy_triggered import PolicyTriggered
from services.control_plane.policy.policy_action import (
    PolicyAction,
    PolicyActionType,
)
from services.control_plane.policy.policy_condition import condition
from services.control_plane.policy.policy_context import PolicyContext
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_priority import PolicyPriority
from services.control_plane.policy.policy_rule import PolicyRule


class TestPolicyEvaluatedEvent:
    def test_from_evaluation(self):
        from services.control_plane.policy.policy import Policy
        from services.control_plane.policy.policy_engine import PolicyEngine

        engine = PolicyEngine()
        engine.register_policy(
            Policy("p1", "1.0.0", "P1").add_rule(
                PolicyRule(
                    rule_id="r1",
                    condition=condition(
                        "risk_health", "equals", "UNHEALTHY"
                    ),
                    decision=PolicyDecision.HALT,
                    priority=PolicyPriority.CRITICAL,
                )
            )
        )
        evaluation = engine.evaluate(
            PolicyContext(risk_health=ComponentState.UNHEALTHY),
            correlation_id="trace-9",
        )
        event = PolicyEvaluated.from_evaluation(evaluation)
        assert event.event_type == "POLICY_EVALUATED"
        assert event.decision is PolicyDecision.HALT
        assert event.matched_policies == ["p1"]
        assert event.policy_versions == {"p1": "1.0.0"}
        assert event.correlation_id == "trace-9"
        assert event.context_snapshot["risk_health"] == "UNHEALTHY"

    def test_serialization_round_trip(self):
        event = PolicyEvaluated(
            decision=PolicyDecision.BLOCK,
            priority=PolicyPriority.HIGH,
            context_snapshot={"risk_health": "UNHEALTHY"},
            correlation_id="trace-1",
            matched_policies=["p1"],
            policy_versions={"p1": "1.0.0"},
            matched_rules=["r1"],
            reasons=["RISK_UNHEALTHY"],
        )
        restored = PolicyEvaluated.from_dict(event.to_dict())
        assert restored.decision is PolicyDecision.BLOCK
        assert restored.correlation_id == "trace-1"
        assert restored.to_dict() == event.to_dict()


class TestPolicyTriggeredEvent:
    def test_from_rule_result(self):
        rule = PolicyRule(
            rule_id="risk-dead-kill",
            condition=condition("risk_health", "equals", "UNHEALTHY"),
            decision=PolicyDecision.HALT,
            priority=PolicyPriority.CRITICAL,
        )
        result = rule.evaluate(
            PolicyContext(risk_health=ComponentState.UNHEALTHY)
        )
        event = PolicyTriggered.from_rule_result(
            "core-health-policy", "1.0.0", result, "trace-2"
        )
        assert event.event_type == "POLICY_TRIGGERED"
        assert event.policy_id == "core-health-policy"
        assert event.rule_id == "risk-dead-kill"
        assert event.decision is PolicyDecision.HALT
        assert event.correlation_id == "trace-2"
        assert event.condition["field"] == "risk_health"

    def test_serialization_round_trip(self):
        event = PolicyTriggered(
            policy_id="p1",
            policy_version="1.0.0",
            rule_id="r1",
            decision=PolicyDecision.BLOCK,
            reason="X",
        )
        restored = PolicyTriggered.from_dict(event.to_dict())
        assert restored.policy_id == "p1"
        assert restored.decision is PolicyDecision.BLOCK
        assert restored.to_dict() == event.to_dict()


class TestPolicyActionRequestedEvent:
    def test_from_action(self):
        action = PolicyAction(
            PolicyActionType.START_RECOVERY,
            target="POSITION",
            reason="POSITION_INTEGRITY_FAILED",
            priority=PolicyPriority.CRITICAL,
        )
        event = PolicyActionRequested.from_action(
            action, "risk-policy", "1.0.0", "trace-3"
        )
        assert event.event_type == "POLICY_ACTION_REQUESTED"
        assert event.action_type is PolicyActionType.START_RECOVERY
        assert event.target == "POSITION"
        assert event.policy_id == "risk-policy"
        assert event.correlation_id == "trace-3"

    def test_serialization_round_trip(self):
        event = PolicyActionRequested(
            action_type=PolicyActionType.ACTIVATE_KILL_SWITCH,
            target="GLOBAL",
            policy_id="emergency-policy",
            reason="EMERGENCY_MODE",
        )
        restored = PolicyActionRequested.from_dict(event.to_dict())
        assert (
            restored.action_type is PolicyActionType.ACTIVATE_KILL_SWITCH
        )
        assert restored.to_dict() == event.to_dict()
