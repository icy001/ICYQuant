"""Tests for services.governance.evaluator — PolicyEvaluator (Commit 28 Part 1.2)."""

from services.governance.condition import ConditionEvaluator, ConditionOperator, PolicyCondition
from services.governance.decision import GovernanceContext
from services.governance.evaluator import PolicyEvaluator
from services.governance.policy import Policy


def _context(**overrides):
    base = dict(
        principal_id="ops-001",
        role_ids=("OPERATOR",),
        resource="trading",
        action="pause",
        environment="production",
        severity="WARNING",
        incident_id="INC-001",
    )
    base.update(overrides)
    return GovernanceContext(**base)


def _evaluator():
    return PolicyEvaluator(ConditionEvaluator())


def _policy(**overrides):
    base = dict(
        policy_id="POLICY-001",
        name="Trading Pause",
        resource="trading",
        action="pause",
    )
    base.update(overrides)
    return Policy(**base)


def test_matches_empty_policy():
    evaluator = _evaluator()
    assert evaluator.matches(_policy(), _context())


def test_disabled_policy_never_matches():
    evaluator = _evaluator()
    policy = _policy(enabled=False)
    assert not evaluator.matches(policy, _context())


def test_resource_and_action_must_match():
    evaluator = _evaluator()
    policy = _policy()
    assert not evaluator.matches(policy, _context(resource="risk"))
    assert not evaluator.matches(policy, _context(action="resume"))


def test_required_roles_match():
    evaluator = _evaluator()
    policy = _policy(required_roles=("OPERATOR", "CONTROL_OPERATOR"))
    assert evaluator.matches(policy, _context(role_ids=("OPERATOR",)))
    assert evaluator.matches(policy, _context(role_ids=("OBSERVER", "CONTROL_OPERATOR")))
    assert not evaluator.matches(policy, _context(role_ids=("OBSERVER",)))


def test_all_conditions_and_semantics():
    """Spec section 11 — every condition must pass (AND semantics)."""
    evaluator = _evaluator()
    policy = _policy(
        conditions=(
            PolicyCondition("environment", ConditionOperator.EQUALS, "production"),
            PolicyCondition("severity", ConditionOperator.IN, ("CRITICAL", "EMERGENCY")),
            PolicyCondition("incident_id", ConditionOperator.EXISTS, None),
        )
    )

    assert evaluator.matches(
        policy, _context(severity="CRITICAL", incident_id="INC-001")
    )

    assert not evaluator.matches(policy, _context(severity="WARNING"))
    assert not evaluator.matches(policy, _context(incident_id=None))
    assert not evaluator.matches(
        policy, _context(environment="staging", severity="CRITICAL")
    )
