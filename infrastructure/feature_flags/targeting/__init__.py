"""
Feature flag targeting rules package.

Provides the targeting rules engine for
context-aware feature flag evaluation.
Supports complex rule expressions with
AND/OR/NOT logic, multiple comparison
operators, and priority-based resolution.

Usage:
    from infrastructure.feature_flags.targeting import (
        TargetingEngine,
        TargetContext,
        TargetRule,
        RuleSet,
    )

    engine = TargetingEngine()
    rules = [
        TargetRule(
            rule_id="prod-canary",
            priority=10,
            expression="environment == 'production' AND broker == 'IBKR'",
            value=True,
        ),
    ]
    result = await engine.evaluate(rules, feature_context)
"""

from __future__ import annotations

from .cache import CompiledRuleCache, EvaluationCache
from .compiler import MatcherFn, OptimizedRuleCompiler, RuleCompiler
from .conditions import (
    AndNode,
    ConditionNode,
    LogicNode,
    NotNode,
    OrNode,
    RuleNode,
    flatten_conditions,
    node_count,
    node_depth,
)
from .context import TargetContext
from .engine import TargetingEngine
from .matcher import RuleMatcher
from .metrics import RuleMetrics
from .operators import (
    OPERATOR_ORDER,
    OPERATOR_SYMBOLS,
    Operator,
    compare_eq,
    compare_neq,
    compare_gt,
    compare_gte,
    compare_lt,
    compare_lte,
    compare_in,
    compare_not_in,
    compare_starts_with,
    compare_ends_with,
    compare_contains,
    compare_regex,
    get_compare_fn,
)
from .parser import ParseError, RuleParser, parse_expression
from .priority import PriorityLevel, PriorityResolver, PriorityResult
from .rules import RuleEvaluation, RuleSet, TargetRule
from .validator import RuleValidator

__all__ = [
    # Engine
    "TargetingEngine",
    "RuleMatcher",
    "RuleCompiler",
    "OptimizedRuleCompiler",
    "RuleParser",
    "RuleValidator",
    "PriorityResolver",
    # Models
    "TargetContext",
    "TargetRule",
    "RuleSet",
    "RuleEvaluation",
    # AST Nodes
    "RuleNode",
    "LogicNode",
    "ConditionNode",
    "AndNode",
    "OrNode",
    "NotNode",
    # Operators
    "Operator",
    "OPERATOR_ORDER",
    "OPERATOR_SYMBOLS",
    # Comparison functions
    "compare_eq",
    "compare_neq",
    "compare_gt",
    "compare_gte",
    "compare_lt",
    "compare_lte",
    "compare_in",
    "compare_not_in",
    "compare_starts_with",
    "compare_ends_with",
    "compare_contains",
    "compare_regex",
    "get_compare_fn",
    # Cache
    "CompiledRuleCache",
    "EvaluationCache",
    # Metrics
    "RuleMetrics",
    # Priority
    "PriorityLevel",
    "PriorityResult",
    # Utilities
    "MatcherFn",
    "ParseError",
    "parse_expression",
    "flatten_conditions",
    "node_count",
    "node_depth",
]