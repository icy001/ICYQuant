"""
Tests for policy_rule_set.py — PolicyRuleSet evaluation modes, activation conditions,
and rule evaluation.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.governance.policy_rule_set import (
    PolicyRuleSet,
    RuleSetEvaluationMode,
    RuleSetStatus,
    RuleEvaluation,
    RuleSetResult,
)
from services.governance.policy_rule import PolicyRule, RuleSeverity
from services.governance.policy_condition import PolicyCondition, ConditionLogic


class TestRuleEvaluation(unittest.TestCase):
    """Test single rule evaluation result."""

    def test_evaluation_passed(self):
        ev = RuleEvaluation(
            rule_id="R1",
            rule_name="Test Rule",
            passed=True,
            severity=RuleSeverity.INFO,
            metric="test_metric",
            actual=10.0,
            expected=">= 5.0",
        )
        self.assertTrue(ev.passed)
        self.assertEqual(ev.severity, RuleSeverity.INFO)

    def test_evaluation_failed_critical(self):
        ev = RuleEvaluation(
            rule_id="R1",
            rule_name="Critical Rule",
            passed=False,
            severity=RuleSeverity.CRITICAL,
        )
        self.assertFalse(ev.passed)

    def test_to_dict(self):
        ev = RuleEvaluation(
            rule_id="R1",
            rule_name="Test",
            passed=True,
            severity=RuleSeverity.WARNING,
            metric="m",
            actual=5.0,
            expected="< 10",
        )
        d = ev.to_dict()
        self.assertEqual(d["rule_id"], "R1")
        self.assertEqual(d["passed"], True)
        self.assertEqual(d["severity"], "WARNING")


class TestRuleSetResult(unittest.TestCase):
    """Test aggregated rule set results."""

    def test_all_passed(self):
        evals = [
            RuleEvaluation(rule_id="R1", passed=True, severity=RuleSeverity.INFO),
            RuleEvaluation(rule_id="R2", passed=True, severity=RuleSeverity.WARNING),
        ]
        result = RuleSetResult(
            rule_set_id="RS1",
            rule_set_name="All Pass",
            passed=True,
            rule_count=2,
            passed_count=2,
            failed_count=0,
            evaluations=evals,
        )
        self.assertTrue(result.passed)
        self.assertFalse(result.has_failures)
        self.assertFalse(result.is_blocking)

    def test_has_failures(self):
        evals = [
            RuleEvaluation(rule_id="R1", passed=False, severity=RuleSeverity.CRITICAL),
            RuleEvaluation(rule_id="R2", passed=True, severity=RuleSeverity.INFO),
        ]
        result = RuleSetResult(
            rule_set_id="RS1",
            passed=False,
            rule_count=2,
            passed_count=1,
            failed_count=1,
            highest_severity=RuleSeverity.CRITICAL,
            evaluations=evals,
        )
        self.assertTrue(result.has_failures)
        self.assertTrue(result.is_blocking)

    def test_requires_review(self):
        evals = [
            RuleEvaluation(rule_id="R1", passed=False, severity=RuleSeverity.REVIEW),
        ]
        result = RuleSetResult(
            rule_set_id="RS1",
            passed=False,
            rule_count=1,
            passed_count=0,
            failed_count=1,
            highest_severity=RuleSeverity.REVIEW,
            evaluations=evals,
        )
        self.assertTrue(result.requires_review)


class TestPolicyRuleSet(unittest.TestCase):
    """Test PolicyRuleSet operations."""

    def setUp(self):
        self.rs = PolicyRuleSet(
            name="Test Rule Set",
            description="A test rule set",
            evaluation_mode=RuleSetEvaluationMode.ALL,
        )

    def test_add_and_remove_rules(self):
        rule = PolicyRule(rule_id="R1", metric="m1")
        self.rs.add_rule(rule)
        self.assertEqual(self.rs.rule_count, 1)

        self.rs.remove_rule("R1")
        self.assertEqual(self.rs.rule_count, 0)

    def test_rule_weights(self):
        rule = PolicyRule(rule_id="R1")
        self.rs.add_rule(rule, weight=2.0)
        self.assertEqual(self.rs.get_rule_weight("R1"), 2.0)

        self.rs.set_rule_weight("R1", 3.0)
        self.assertEqual(self.rs.get_rule_weight("R1"), 3.0)

    def test_get_rule(self):
        rule = PolicyRule(rule_id="R1", metric="m1")
        self.rs.add_rule(rule)
        found = self.rs.get_rule("R1")
        self.assertIsNotNone(found)
        self.assertEqual(found.metric, "m1")

        not_found = self.rs.get_rule("NONEXISTENT")
        self.assertIsNone(not_found)

    def test_active_rules(self):
        r1 = PolicyRule(rule_id="R1", enabled=True)
        r2 = PolicyRule(rule_id="R2", enabled=False)
        self.rs.add_rule(r1)
        self.rs.add_rule(r2)
        self.assertEqual(len(self.rs.active_rules), 1)
        self.assertEqual(self.rs.active_rules[0].rule_id, "R1")

    def test_is_active_always(self):
        self.rs.status = RuleSetStatus.ALWAYS
        self.assertTrue(self.rs.is_active({}))

    def test_is_active_disabled(self):
        self.rs.status = RuleSetStatus.DISABLED
        self.assertFalse(self.rs.is_active({}))

    def test_is_active_conditional(self):
        self.rs.status = RuleSetStatus.CONDITIONAL
        cond = PolicyCondition(metric="market_open", operator="EQUAL", value=True)
        from services.governance.policy_condition import ConditionOperator
        cond.operator = ConditionOperator.EQUAL
        self.rs.activation_conditions = [cond]
        self.assertTrue(self.rs.is_active({"market_open": True}))
        self.assertFalse(self.rs.is_active({"market_open": False}))

    def test_serialization(self):
        self.rs.add_rule(PolicyRule(rule_id="R1"))
        data = self.rs.to_dict()
        restored = PolicyRuleSet.from_dict(data)
        self.assertEqual(restored.name, self.rs.name)
        self.assertEqual(restored.rule_count, self.rs.rule_count)


if __name__ == "__main__":
    unittest.main()
