"""
Comprehensive validation script for targeting rules engine.
Tests all 12 operators, AND/OR/NOT logic, nested groups,
priority resolution, caching, and diagnostics.
"""

import asyncio
import sys
import time

from infrastructure.feature_flags import (
    FeatureContext,
    FeatureEvaluator,
    FeatureFlag,
    FeatureFlagType,
    EvaluationStrategy,
    TargetingEngine,
    TargetRule,
    TargetContext,
    RuleParser,
    RuleCompiler,
    RuleMatcher,
    RuleValidator,
    RuleMetrics,
    RuleDiagnostics,
    PriorityResolver,
    PriorityLevel,
    PriorityResult,
    CompiledRuleCache,
    EvaluationCache,
    parse_expression,
    Operator,
    AndNode,
    ConditionNode,
    NotNode,
    OrNode,
)

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [OK] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} - {detail}")


async def test_operators():
    print("\n=== 1. Operator Tests ===")

    from infrastructure.feature_flags.targeting.operators import (
        compare_eq, compare_neq, compare_gt, compare_gte,
        compare_lt, compare_lte, compare_in, compare_not_in,
        compare_starts_with, compare_ends_with, compare_contains,
        compare_regex,
    )

    check("compare_eq (equal)", compare_eq("hello", "hello"))
    check("compare_eq (not equal)", not compare_eq("hello", "world"))
    check("compare_eq (case insensitive)", compare_eq("Hello", "hello"))
    check("compare_eq (None)", compare_eq(None, "none"))
    check("compare_neq", compare_neq("a", "b"))
    check("compare_gt (numeric)", compare_gt(10, 5))
    check("compare_gt (string)", compare_gt("b", "a"))
    check("compare_gte", compare_gte(5, 5))
    check("compare_lt", compare_lt(3, 5))
    check("compare_lte", compare_lte(5, 5))
    check("compare_in", compare_in("apple", ["apple", "banana"]))
    check("compare_not_in", compare_not_in("cherry", ["apple", "banana"]))
    check("compare_starts_with", compare_starts_with("hello world", "hello"))
    check("compare_ends_with", compare_ends_with("hello world", "world"))
    check("compare_contains", compare_contains("hello world", "lo wo"))
    check("compare_regex", compare_regex("abc123", r"[a-z]+\d+"))
    check("compare_regex (no match)", not compare_regex("abc", r"^\d+$"))


async def test_parser():
    print("\n=== 2. Parser Tests ===")

    parser = RuleParser()

    # Simple condition
    node = parser.parse("account == '001'")
    check("Parse simple ==", isinstance(node, ConditionNode))
    check("Simple attr", node.attribute == "account")
    check("Simple op", node.operator == Operator.EQ)
    check("Simple value", node.value == "001")

    # AND expression
    node = parser.parse("account == '001' AND exchange == 'NASDAQ'")
    check("Parse AND", isinstance(node, AndNode))
    check("AND children count", len(node.children) == 2)

    # OR expression
    node = parser.parse("exchange == 'NYSE' OR exchange == 'NASDAQ'")
    check("Parse OR", isinstance(node, OrNode))

    # NOT expression
    node = parser.parse("NOT account == '001'")
    check("Parse NOT", isinstance(node, NotNode))

    # Nested groups
    node = parser.parse(
        "(account == '001') AND (exchange == 'NASDAQ' OR exchange == 'NYSE')"
    )
    check("Parse nested groups", isinstance(node, AndNode))

    # IN operator
    node = parser.parse("exchange IN ('NYSE', 'NASDAQ', 'AMEX')")
    check("Parse IN operator", isinstance(node, ConditionNode))
    check("IN attribute", node.attribute == "exchange")
    check("IN values", isinstance(node.value, list))
    check("IN value count", len(node.value) == 3)

    # Numeric value
    node = parser.parse("value > 100")
    check("Parse numeric value", isinstance(node.value, int))
    check("Numeric comparison", node.operator == Operator.GT)

    # parse_expression convenience
    node = parse_expression("broker == 'IBKR'")
    check("parse_expression", isinstance(node, ConditionNode))


async def test_compiler():
    print("\n=== 3. Compiler Tests ===")

    parser = RuleParser()
    compiler = RuleCompiler()

    # Compile simple condition
    node = parser.parse("account == '001'")
    matcher = compiler.compile(node, cache_key="test-simple")
    check("Compile simple", callable(matcher))

    # Test compiled matcher - use attribute matching the expression
    ctx = TargetContext(attributes={"account": "001"})
    check("Match compiled simple", matcher(ctx))

    ctx2 = TargetContext(attributes={"account": "002"})
    check("No match compiled simple", not matcher(ctx2))

    # Same cache key - should get cache hit
    node2 = parser.parse("account == '001'")
    matcher2 = compiler.compile(node2, cache_key="test-simple")
    check("Cache hit on recompile", matcher2 is matcher)

    # Compile AND
    node = parser.parse("account == '001' AND broker == 'IBKR'")
    matcher = compiler.compile(node, cache_key="test-and")
    check("Compile AND", callable(matcher))

    ctx_match = TargetContext(attributes={"account": "001", "broker": "IBKR"})
    check("Match AND", matcher(ctx_match))

    ctx_partial = TargetContext(attributes={"account": "001", "broker": "OANDA"})
    check("No match AND (partial)", not matcher(ctx_partial))

    # Compile OR
    node = parser.parse("exchange == 'NYSE' OR exchange == 'NASDAQ'")
    matcher = compiler.compile(node, cache_key="test-or")
    ctx_nyse = TargetContext(exchange="NYSE")
    ctx_nasdaq = TargetContext(exchange="NASDAQ")
    ctx_amex = TargetContext(exchange="AMEX")
    check("Match OR (NYSE)", matcher(ctx_nyse))
    check("Match OR (NASDAQ)", matcher(ctx_nasdaq))
    check("No match OR (AMEX)", not matcher(ctx_amex))

    # Compile NOT
    node = parser.parse("NOT account == '001'")
    matcher = compiler.compile(node, cache_key="test-not")
    check("Match NOT (002)", matcher(TargetContext(attributes={"account": "002"})))
    check("No match NOT (001)", not matcher(TargetContext(attributes={"account": "001"})))

    # Test cache
    stats = compiler.get_stats()
    check("Compile cache hits", stats["cache_hits"] > 0)


async def test_matcher():
    print("\n=== 4. Matcher Tests ===")

    matcher = RuleMatcher()

    rule = TargetRule(
        rule_id="test-rule-001",
        priority=10,
        expression="environment == 'production' AND broker == 'IBKR'",
        value=True,
    )

    ctx = TargetContext(environment="production", broker="IBKR")
    result = await matcher.match(rule, ctx)
    check("Rule match", result.matched)
    check("Match value", result.value is True)

    ctx_no = TargetContext(environment="development", broker="IBKR")
    result = await matcher.match(rule, ctx_no)
    check("Rule no match", not result.matched)

    # Disabled rule
    disabled_rule = TargetRule(
        rule_id="disabled-rule",
        priority=5,
        expression="environment == 'production'",
        value=True,
        enabled=False,
    )
    result = await matcher.match(disabled_rule, ctx)
    check("Disabled rule no match", not result.matched)

    # Match all (multi-rule)
    rules = [
        TargetRule(rule_id="r1", priority=100, expression="account_id == '001'", value="low"),
        TargetRule(rule_id="r2", priority=50, expression="account_id == '001' AND broker == 'IBKR'", value="high"),
    ]
    ctx_both = TargetContext(account_id="001", broker="IBKR")
    results = await matcher.match_all(rules, ctx_both, stop_on_first_match=True)
    check("Multi-rule match count", len(results) >= 1)


async def test_targeting_engine():
    print("\n=== 5. Targeting Engine Tests ===")

    engine = TargetingEngine()

    # Create feature context
    ctx = FeatureContext(
        target_id="acc_001",
        target_type="account",
        environment="production",
        attributes={
            "account_id": "001",
            "broker": "IBKR",
            "exchange": "NASDAQ",
            "strategy_id": "alpha101",
        },
    )

    # Simple targeting rule
    rules = [
        TargetRule(
            rule_id="prod-canary",
            priority=10,
            expression="environment == 'production' AND broker == 'IBKR'",
            value=True,
        ),
    ]

    result = await engine.evaluate(rules, ctx, default_value=False)
    check("Engine match", result.matched)
    check("Engine value", result.value is True)

    # Non-matching context
    ctx_dev = FeatureContext(
        target_id="acc_002",
        target_type="account",
        environment="development",
        attributes={"account_id": "002", "broker": "OANDA"},
    )
    result = await engine.evaluate(rules, ctx_dev, default_value=False)
    check("Engine no match", not result.matched)

    # Nested complex rule
    complex_rules = [
        TargetRule(
            rule_id="complex-001",
            priority=5,
            expression=(
                "environment == 'production' AND "
                "broker == 'IBKR' AND "
                "(exchange == 'NASDAQ' OR exchange == 'NYSE')"
            ),
            value=True,
        ),
    ]

    ctx_complex = FeatureContext(
        target_id="acc_003",
        target_type="account",
        environment="production",
        attributes={
            "account_id": "003",
            "broker": "IBKR",
            "exchange": "NASDAQ",
        },
    )
    result = await engine.evaluate(complex_rules, ctx_complex, default_value=False)
    check("Complex rule match", result.matched)

    # Multi-rule with priority
    multi_rules = [
        TargetRule(
            rule_id="low-priority",
            priority=100,
            expression="environment == 'production'",
            value="low-tier",
        ),
        TargetRule(
            rule_id="high-priority",
            priority=10,
            expression="environment == 'production' AND broker == 'IBKR'",
            value="high-tier",
        ),
    ]

    ctx_multi = FeatureContext(
        target_id="acc_004",
        environment="production",
        attributes={"broker": "IBKR"},
    )
    result = await engine.evaluate(multi_rules, ctx_multi, default_value="default")
    check("Multi-rule high priority matched", result.matched)
    check("Multi-rule correct value", result.value == "high-tier")

    # Engine stats
    stats = engine.get_stats()
    check("Engine has evalutions", stats["evaluations"] > 0)

    # Clear caches
    await engine.clear_caches()


async def test_validator():
    print("\n=== 6. Validator Tests ===")

    validator = RuleValidator()

    valid_rule = TargetRule(
        rule_id="valid-rule",
        priority=10,
        expression="account == '001' AND broker == 'IBKR'",
        value=True,
    )
    errors = validator.validate_rule(valid_rule)
    check("Valid rule no errors", len(errors) == 0, str(errors))

    invalid_rule = TargetRule(
        rule_id="",
        priority=-1,
        expression="",
        value=None,
    )
    errors = validator.validate_rule(invalid_rule)
    check("Invalid rule has errors", len(errors) > 0)

    # Syntax validation
    errors = validator.validate_expression_syntax("(a == 'b' AND c == 'd')")
    check("Syntax valid (balanced parens)", len(errors) == 0)

    errors = validator.validate_expression_syntax("(a == 'b' AND c == 'd'")
    check("Syntax invalid (unbalanced parens)", len(errors) > 0)

    errors = validator.validate_expression_syntax("a == 'b' AND AND c == 'd'")
    check("Syntax invalid (double AND)", len(errors) > 0)


async def test_priority():
    print("\n=== 7. Priority Tests ===")

    resolver = PriorityResolver()

    rule_low = TargetRule(rule_id="low", priority=100, expression="a == '1'", value="low")
    rule_high = TargetRule(rule_id="high", priority=10, expression="a == '1'", value="high")

    from infrastructure.feature_flags.targeting.rules import RuleEvaluation

    evals = [
        RuleEvaluation(rule_id="low", matched=True, value="low", duration_ms=0.1),
        RuleEvaluation(rule_id="high", matched=True, value="high", duration_ms=0.2),
    ]

    result = resolver.resolve([rule_low, rule_high], evals)
    check("Priority selects higher (lower number)", result.has_match)
    check("Priority correct rule", result.matched_rule.rule_id == "high")


async def test_cache():
    print("\n=== 8. Cache Tests ===")

    comp_cache = CompiledRuleCache(max_size=100, ttl_seconds=3600)
    ctx = TargetContext(account_id="001")

    # Put and get
    await comp_cache.put("rule-1", lambda c: True, version=1)
    result = await comp_cache.get("rule-1")
    check("Compiled cache hit", result is not None)

    # Miss
    result = await comp_cache.get("nonexistent")
    check("Compiled cache miss", result is None)

    # Invalidate
    await comp_cache.invalidate("rule-1")
    result = await comp_cache.get("rule-1")
    check("Cache invalidation works", result is None)

    # Evaluation cache
    eval_cache = EvaluationCache(max_size=50, ttl_seconds=60)
    from infrastructure.feature_flags.targeting.rules import RuleEvaluation
    eval_result = RuleEvaluation(rule_id="r1", matched=True, value=True)
    await eval_cache.put("r1", ctx, eval_result)

    cached = await eval_cache.get("r1", ctx)
    check("Eval cache hit", cached is not None and cached.matched)


async def test_metrics():
    print("\n=== 9. Metrics Tests ===")

    metrics = RuleMetrics()

    metrics.record_eval("rule-1", True, 1.5)
    metrics.record_eval("rule-1", False, 2.0)
    metrics.record_cache_hit("rule-1")
    metrics.record_compile("rule-1")

    rule_metrics = metrics.get_rule_metrics("rule-1")
    check("Metrics evalutions", rule_metrics["evaluations"] == 2)
    check("Metrics matches", rule_metrics["matches"] == 1)
    check("Metrics cache hits", rule_metrics["cache_hits"] == 1)
    check("Metrics compiles", rule_metrics["compilations"] == 1)

    snapshot = metrics.snapshot()
    check("Snapshot has total", "total" in snapshot)
    check("Snapshot has rules", "rules" in snapshot)


async def test_diagnostics():
    print("\n=== 10. Diagnostics Tests ===")

    diag = RuleDiagnostics()

    rules = [
        TargetRule(
            rule_id="diag-rule",
            priority=10,
            expression="environment == 'production' AND broker == 'IBKR'",
            value=True,
        ),
    ]

    ctx = FeatureContext(
        target_id="diag-001",
        environment="production",
        attributes={"broker": "IBKR"},
    )

    trace = await diag.trace_evaluation(rules, "test.feature", ctx)
    check("Diagnostics trace created", trace is not None)
    check("Diagnostics trace has steps", len(trace.steps) > 0)
    check("Diagnostics trace has final result", trace.final_result is not None)

    summary = trace.summary()
    check("Summary not empty", len(summary) > 0)

    # AST visualization
    ast_viz = diag.visualize_ast("account == '001' AND broker == 'IBKR'")
    check("AST visualization", "AND" in ast_viz)

    trace_dict = trace.to_dict()
    check("Trace dict serializable", isinstance(trace_dict, dict))


async def test_evaluator_integration():
    print("\n=== 11. Evaluator Integration Tests ===")

    evaluator = FeatureEvaluator()

    # Create a flag with rule-based strategy
    from infrastructure.feature_flags.constants import EvaluationStrategy, FeatureFlagType
    from infrastructure.feature_flags.models import FeatureRule

    flag = FeatureFlag(
        key="test.targeting_flag",
        enabled=True,
        description="Test targeting flag",
        flag_type=FeatureFlagType.BOOLEAN,
        strategy=EvaluationStrategy.RULE_BASED,
        default_value=False,
        rules=[
            FeatureRule(
                rule_id="rule-1",
                priority=10,
                condition="account_id == 'acc_001' AND broker == 'IBKR'",
                value=True,
                enabled=True,
            )
        ],
    )

    ctx = FeatureContext(
        target_id="acc_001",
        target_type="account",
        attributes={"account_id": "acc_001", "broker": "IBKR"},
    )

    result = await evaluator.evaluate(flag, ctx)
    check("Evaluator rule-based match", result.result.value == "hit")


async def main():
    global PASSED, FAILED

    print("=" * 60)
    print("Feature Flag Targeting Rules Engine - Validation")
    print("=" * 60)

    await test_operators()
    await test_parser()
    await test_compiler()
    await test_matcher()
    await test_targeting_engine()
    await test_validator()
    await test_priority()
    await test_cache()
    await test_metrics()
    await test_diagnostics()
    await test_evaluator_integration()

    print("\n" + "=" * 60)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print("=" * 60)

    if FAILED > 0:
        sys.exit(1)
    else:
        print("\n=== ALL TESTS PASSED ===")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())