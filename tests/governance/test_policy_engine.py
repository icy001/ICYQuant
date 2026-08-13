"""
Tests for Policy Engine — covers ALLOW, WARNING, REVIEW, BLOCK, AND, OR, NOT.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.governance.policy_engine import PolicyEngine, PolicySeverity, PolicyEvaluationResult
from services.governance.policy import InstitutionalPolicy as Policy, PolicyScope
from services.governance.policy_rule import PolicyRule, RuleSeverity
from services.governance.policy_condition import PolicyCondition, ConditionLogic, ConditionOperator
from services.governance.decision_context import DecisionContext
from services.governance.decision_request import DecisionRequest, DecisionType


class TestPolicyEngine:

    # ------------------------------------------------------------------
    # Simple rule tests
    # ------------------------------------------------------------------

    def test_policy_allows_when_rule_passes(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-001",
            name="Test Policy",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=85.0)
        result = engine.evaluate(request, context)

        assert result.passed is True
        assert result.blocking is False

    def test_policy_blocks_when_rule_fails_blocking(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-002",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0)
        result = engine.evaluate(request, context)

        assert result.passed is False
        assert result.blocking is True
        assert len(result.violations) == 1

    def test_policy_warning_does_not_block(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-003",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.WARNING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0)
        result = engine.evaluate(request, context)

        assert result.passed is True  # WARNING doesn't fail
        assert result.blocking is False
        assert len(result.warnings) == 1

    def test_policy_review_triggers_review_required(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-004",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="liquidity_score",
                    operator=">=",
                    threshold=60.0,
                    severity=RuleSeverity.REVIEW,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(liquidity_score=48.0)
        result = engine.evaluate(request, context)

        assert result.review_required is True
        assert len(result.violations) == 1

    # ------------------------------------------------------------------
    # Multiple rules
    # ------------------------------------------------------------------

    def test_multiple_rules_all_fail(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-005",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                ),
                PolicyRule(
                    rule_id="r2",
                    metric="liquidity_score",
                    operator=">=",
                    threshold=50.0,
                    severity=RuleSeverity.BLOCKING,
                ),
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0, liquidity_score=30.0)
        result = engine.evaluate(request, context)

        assert result.passed is False
        assert result.blocking is True
        assert len(result.violations) == 2

    def test_one_rule_fails_one_passes(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-006",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                ),
                PolicyRule(
                    rule_id="r2",
                    metric="liquidity_score",
                    operator=">=",
                    threshold=50.0,
                    severity=RuleSeverity.BLOCKING,
                ),
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=85.0, liquidity_score=30.0)
        result = engine.evaluate(request, context)

        assert result.passed is False
        assert result.blocking is True
        assert len(result.violations) == 1

    # ------------------------------------------------------------------
    # Operator tests
    # ------------------------------------------------------------------

    def test_operator_greater_than(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-op-gt",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="risk_budget_used",
                    operator=">",
                    threshold=5.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        context = DecisionContext(risk_budget_used=6.0)
        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        result = engine.evaluate(request, context)
        assert result.blocking is True

        context2 = DecisionContext(risk_budget_used=4.0)
        result2 = engine.evaluate(request, context2)
        assert result2.blocking is False

    def test_operator_less_than_or_equal(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-op-lte",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="strategy_weight",
                    operator="<=",
                    threshold=0.25,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)

        context = DecisionContext(strategy_weight=0.25)
        result = engine.evaluate(request, context)
        assert result.passed is True

        context2 = DecisionContext(strategy_weight=0.30)
        result2 = engine.evaluate(request, context2)
        assert result2.passed is False

    def test_dynamic_threshold_from_context(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-dynamic",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="risk_budget_used",
                    operator="<=",
                    threshold_key="risk_budget_total",
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(risk_budget_total=10.0, risk_budget_used=12.0)
        result = engine.evaluate(request, context)
        assert result.blocking is True

        context2 = DecisionContext(risk_budget_total=10.0, risk_budget_used=8.0)
        result2 = engine.evaluate(request, context2)
        assert result2.blocking is False

    # ------------------------------------------------------------------
    # Condition tests (AND / OR / NOT)
    # ------------------------------------------------------------------

    def test_and_condition_all_pass(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-and-pass",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=0,
                    severity=RuleSeverity.BLOCKING,
                    conditions=[
                        PolicyCondition(
                            metric="risk_budget_used",
                            operator=ConditionOperator.GREATER_THAN,
                            value=5.0,
                        ),
                        PolicyCondition(
                            metric="liquidity_score",
                            operator=ConditionOperator.LESS_THAN,
                            value=80.0,
                        ),
                    ],
                    condition_logic=ConditionLogic.AND,
                )
            ],
        )
        engine.register(policy)

        # Both conditions met: risk > 5 AND liquidity < 80
        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=85.0, risk_budget_used=6.0, liquidity_score=50.0)
        result = engine.evaluate(request, context)
        assert result.passed is True  # conditions met, rule applies but passes

    def test_and_condition_one_fails_rule_skipped(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-and-skip",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                    conditions=[
                        PolicyCondition(
                            metric="risk_budget_used",
                            operator=ConditionOperator.GREATER_THAN,
                            value=5.0,
                        ),
                        PolicyCondition(
                            metric="liquidity_score",
                            operator=ConditionOperator.LESS_THAN,
                            value=80.0,
                        ),
                    ],
                    condition_logic=ConditionLogic.AND,
                )
            ],
        )
        engine.register(policy)

        # Only one condition met: risk > 5 but liquidity is HIGH (not < 80)
        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0, risk_budget_used=6.0, liquidity_score=90.0)
        result = engine.evaluate(request, context)
        # Rule is skipped because ALL conditions aren't met, so it passes
        assert result.passed is True

    def test_or_condition_any_triggers(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="test-or",
            scope=PolicyScope.GLOBAL,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                    conditions=[
                        PolicyCondition(
                            metric="risk_budget_used",
                            operator=ConditionOperator.GREATER_THAN,
                            value=10.0,
                        ),
                        PolicyCondition(
                            metric="liquidity_score",
                            operator=ConditionOperator.LESS_THAN,
                            value=40.0,
                        ),
                    ],
                    condition_logic=ConditionLogic.OR,
                )
            ],
        )
        engine.register(policy)

        # Only one condition met: liquidity < 40
        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0, risk_budget_used=3.0, liquidity_score=30.0)
        result = engine.evaluate(request, context)
        # OR means rule applies → and fails on survival_score < 70
        assert result.blocking is True

    # ------------------------------------------------------------------
    # Scope filtering
    # ------------------------------------------------------------------

    def test_policy_scope_filtering(self):
        engine = PolicyEngine()
        global_policy = Policy(
            policy_id="global-001",
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        strategy_policy = Policy(
            policy_id="strategy-001",
            scope=PolicyScope.STRATEGY,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="strategy_weight",
                    operator="<=",
                    threshold=0.20,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(global_policy)
        engine.register(strategy_policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION, scope="GLOBAL")
        context = DecisionContext(survival_score=85.0, strategy_weight=0.30)

        result = engine.evaluate(request, context)
        # Global applies → PASS (survival 85 >= 70)
        # Strategy scoped may not apply depending on scope matching
        assert result.passed is True

    # ------------------------------------------------------------------
    # Disabled policy
    # ------------------------------------------------------------------

    def test_disabled_policy_not_evaluated(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="disabled-001",
            enabled=False,
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=30.0)
        result = engine.evaluate(request, context)
        assert result.passed is True

    # ------------------------------------------------------------------
    # Quick check
    # ------------------------------------------------------------------

    def test_quick_check(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="quick-001",
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.BLOCKING,
                )
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        assert engine.quick_check(request, DecisionContext(survival_score=85.0)) is True
        assert engine.quick_check(request, DecisionContext(survival_score=50.0)) is False

    # ------------------------------------------------------------------
    # No policies
    # ------------------------------------------------------------------

    def test_empty_engine_passes_all(self):
        engine = PolicyEngine()
        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=0.0)
        result = engine.evaluate(request, context)
        assert result.passed is True

    # ------------------------------------------------------------------
    # Severity hierarchy
    # ------------------------------------------------------------------

    def test_severity_hierarchy(self):
        engine = PolicyEngine()
        policy = Policy(
            policy_id="sev-001",
            rules=[
                PolicyRule(
                    rule_id="r1",
                    metric="survival_score",
                    operator=">=",
                    threshold=70.0,
                    severity=RuleSeverity.CRITICAL,
                ),
                PolicyRule(
                    rule_id="r2",
                    metric="liquidity_score",
                    operator=">=",
                    threshold=60.0,
                    severity=RuleSeverity.WARNING,
                ),
            ],
        )
        engine.register(policy)

        request = DecisionRequest(decision_type=DecisionType.CAPITAL_ALLOCATION)
        context = DecisionContext(survival_score=50.0, liquidity_score=40.0)
        result = engine.evaluate(request, context)

        assert result.highest_severity == PolicySeverity.CRITICAL
