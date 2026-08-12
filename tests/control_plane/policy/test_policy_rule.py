"""Unit tests: PolicyRule evaluation and Policy aggregation."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.policy.policy import Policy, PolicyResult
from services.control_plane.policy.policy_action import (
    PolicyAction,
    PolicyActionType,
)
from services.control_plane.policy.policy_condition import (
    and_,
    condition,
    or_,
)
from services.control_plane.policy.policy_context import PolicyContext
from services.control_plane.policy.policy_decision import PolicyDecision
from services.control_plane.policy.policy_priority import PolicyPriority
from services.control_plane.policy.policy_rule import (
    PolicyRule,
    PolicyRuleResult,
)


def _ctx(**kwargs) -> PolicyContext:
    return PolicyContext(**kwargs)


class TestPolicyRule:
    def test_matches(self):
        rule = PolicyRule(
            rule_id="r1",
            condition=condition("risk_health", "equals", "UNHEALTHY"),
            decision=PolicyDecision.HALT,
            priority=PolicyPriority.CRITICAL,
            reason="RISK_UNHEALTHY",
        )
        result = rule.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY))
        assert isinstance(result, PolicyRuleResult)
        assert result.matched is True
        assert result.decision is PolicyDecision.HALT
        assert result.priority is PolicyPriority.CRITICAL
        assert result.reason == "RISK_UNHEALTHY"

    def test_no_match(self):
        rule = PolicyRule(
            rule_id="r1",
            condition=condition("risk_health", "equals", "UNHEALTHY"),
            decision=PolicyDecision.HALT,
        )
        result = rule.evaluate(_ctx(risk_health=ComponentState.HEALTHY))
        assert result.matched is False
        assert result.decision is None
        assert result.actions == []

    def test_disabled_rule_never_matches(self):
        rule = PolicyRule(
            rule_id="r1",
            condition=condition("risk_health", "equals", "UNHEALTHY"),
            decision=PolicyDecision.HALT,
            enabled=False,
        )
        result = rule.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY))
        assert result.matched is False

    def test_actions_carried_on_match(self):
        act = PolicyAction(
            PolicyActionType.HALT_TRADING, target="GLOBAL", reason="RISK_UNHEALTHY"
        )
        rule = PolicyRule(
            rule_id="r1",
            condition=condition("risk_health", "equals", "UNHEALTHY"),
            decision=PolicyDecision.HALT,
            actions=[act],
        )
        result = rule.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY))
        assert result.actions == [act]

    def test_composite_condition(self):
        rule = PolicyRule(
            rule_id="r1",
            condition=or_(
                condition("risk_health", "equals", "UNHEALTHY"),
                condition("position_integrity", "equals", "UNTRUSTED"),
            ),
            decision=PolicyDecision.BLOCK,
        )
        assert (
            rule.evaluate(_ctx(position_integrity="UNTRUSTED")).matched is True
        )
        assert (
            rule.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY)).matched
            is True
        )
        assert (
            rule.evaluate(
                _ctx(
                    risk_health=ComponentState.HEALTHY,
                    position_integrity="TRUSTED",
                )
            ).matched
            is False
        )

    def test_serialization_round_trip(self):
        rule = PolicyRule(
            rule_id="r1",
            condition=and_(
                condition("risk_health", "equals", "UNHEALTHY"),
                condition("trading_state", "equals", "TRADING_READY"),
            ),
            decision=PolicyDecision.HALT,
            actions=[
                PolicyAction(
                    PolicyActionType.ACTIVATE_KILL_SWITCH,
                    target="GLOBAL",
                    reason="x",
                )
            ],
            reason="reason",
            priority=PolicyPriority.CRITICAL,
        )
        restored = PolicyRule.from_dict(rule.to_dict())
        assert restored.rule_id == "r1"
        assert restored.decision is PolicyDecision.HALT
        assert restored.priority is PolicyPriority.CRITICAL
        ctx = _ctx(
            risk_health=ComponentState.UNHEALTHY,
            trading_state="TRADING_READY",
        )
        assert restored.evaluate(ctx).matched is True


class TestPolicyAggregation:
    def _policy(self):
        return Policy(
            policy_id="p1",
            policy_version="1.0.0",
            name="Test Policy",
        )

    def test_no_rule_matched(self):
        p = self._policy().add_rule(
            PolicyRule(
                rule_id="r1",
                condition=condition("risk_health", "equals", "UNHEALTHY"),
                decision=PolicyDecision.HALT,
            )
        )
        result = p.evaluate(_ctx(risk_health=ComponentState.HEALTHY))
        assert isinstance(result, PolicyResult)
        assert result.matched is False
        assert result.decision is None

    def test_multiple_rules_resolve_to_most_severe(self):
        p = (
            self._policy()
            .add_rule(
                PolicyRule(
                    rule_id="allow",
                    condition=condition("trading_state", "equals", "TRADING_READY"),
                    decision=PolicyDecision.ALLOW,
                    priority=PolicyPriority.LOW,
                )
            )
            .add_rule(
                PolicyRule(
                    rule_id="halt",
                    condition=condition("risk_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    priority=PolicyPriority.CRITICAL,
                )
            )
        )
        ctx = _ctx(
            trading_state="TRADING_READY",
            risk_health=ComponentState.UNHEALTHY,
        )
        result = p.evaluate(ctx)
        assert result.matched is True
        assert result.decision is PolicyDecision.HALT
        assert result.priority is PolicyPriority.CRITICAL
        assert set(result.matched_rules) == {"allow", "halt"}

    def test_actions_deduplicated(self):
        act = PolicyAction(
            PolicyActionType.HALT_TRADING, target="GLOBAL", reason="x"
        )
        p = (
            self._policy()
            .add_rule(
                PolicyRule(
                    rule_id="r1",
                    condition=condition("risk_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    actions=[act],
                )
            )
            .add_rule(
                PolicyRule(
                    rule_id="r2",
                    condition=condition("execution_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    actions=[act],
                )
            )
        )
        ctx = _ctx(
            risk_health=ComponentState.UNHEALTHY,
            execution_health=ComponentState.UNHEALTHY,
        )
        result = p.evaluate(ctx)
        assert len(result.actions) == 1
        assert result.actions[0] == act

    def test_disabled_policy(self):
        p = self._policy()
        p.enabled = False
        p.add_rule(
            PolicyRule(
                rule_id="r1",
                condition=condition("risk_health", "equals", "UNHEALTHY"),
                decision=PolicyDecision.HALT,
            )
        )
        result = p.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY))
        assert result.matched is False

    def test_policy_serialization_round_trip(self):
        p = (
            self._policy()
            .add_rule(
                PolicyRule(
                    rule_id="r1",
                    condition=condition("risk_health", "equals", "UNHEALTHY"),
                    decision=PolicyDecision.HALT,
                    priority=PolicyPriority.CRITICAL,
                )
            )
        )
        restored = Policy.from_dict(p.to_dict())
        assert restored.policy_id == "p1"
        assert restored.policy_version == "1.0.0"
        assert len(restored.rules) == 1
        result = restored.evaluate(_ctx(risk_health=ComponentState.UNHEALTHY))
        assert result.matched is True
        assert result.decision is PolicyDecision.HALT
