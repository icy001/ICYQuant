"""
Targeting rule matcher.

Provides the rule matching engine that evaluates
compiled rules against a TargetContext. Supports
attribute matching, tag matching, range matching,
and regex matching.

Flow:
    Rule → Matcher → Result

Usage:
    matcher = RuleMatcher()
    result = await matcher.match(rule, context)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .compiler import MatcherFn, RuleCompiler
from .conditions import RuleNode
from .context import TargetContext
from .parser import RuleParser
from .rules import RuleEvaluation, TargetRule

logger = logging.getLogger(__name__)


class RuleMatcher:
    """
    Rule matching engine for targeting evaluation.

    Combines the parser, compiler, and context
    adapter to evaluate rules against a given
    context. Supports multiple match strategies
    including attribute, tag, range, and regex.

    Usage:
        matcher = RuleMatcher()
        result = await matcher.match(rule, context)
    """

    def __init__(
        self,
        parser: Optional[RuleParser] = None,
        compiler: Optional[RuleCompiler] = None,
    ) -> None:
        self._parser = parser or RuleParser()
        self._compiler = compiler or RuleCompiler()
        self._eval_count = 0
        self._match_count = 0
        self._total_duration_ms = 0.0
        self._lock = asyncio.Lock()

    async def match(
        self,
        rule: TargetRule,
        context: Optional[TargetContext],
    ) -> RuleEvaluation:
        """
        Evaluate a rule against a context.

        Args:
            rule: Target rule to evaluate.
            context: Target context for evaluation.

        Returns:
            RuleEvaluation result with match status.
        """
        start = time.perf_counter()
        self._eval_count += 1

        # Default: no match
        result = RuleEvaluation(
            rule_id=rule.rule_id,
            matched=False,
            value=rule.default_value if hasattr(rule, 'default_value') else None,
            duration_ms=0.0,
            trace=[],
        )

        # Skip if rule is disabled
        if not rule.enabled:
            duration_ms = (time.perf_counter() - start) * 1000
            result.duration_ms = duration_ms
            result.trace.append("rule_disabled")
            return result

        # Skip if no expression
        if not rule.expression:
            duration_ms = (time.perf_counter() - start) * 1000
            result.duration_ms = duration_ms
            result.trace.append("no_expression")
            return result

        # Use empty context if None
        if context is None:
            context = TargetContext()

        try:
            # Parse or use cached AST
            if rule.compiled_node is None:
                node = self._parser.parse(rule.expression)
                rule.compiled_node = node
            else:
                node = rule.compiled_node

            # Compile or use cached matcher
            cache_key = rule.rule_id
            matcher_fn = self._compiler.compile(node, cache_key=cache_key)

            # Evaluate
            matched = matcher_fn(context)

            duration_ms = (time.perf_counter() - start) * 1000
            result.matched = matched
            result.value = rule.value if matched else None
            result.duration_ms = duration_ms
            result.trace.append(f"expression_eval: {'matched' if matched else 'not_matched'}")

            if matched:
                self._match_count += 1

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            result.duration_ms = duration_ms
            result.trace.append(f"error: {e}")
            logger.error(
                "Rule evaluation failed for %s: %s",
                rule.rule_id, e,
            )

        self._total_duration_ms += result.duration_ms
        return result

    async def match_all(
        self,
        rules: List[TargetRule],
        context: Optional[TargetContext],
        stop_on_first_match: bool = True,
    ) -> List[RuleEvaluation]:
        """
        Evaluate multiple rules against a context.

        Args:
            rules: List of rules to evaluate.
            context: Target context for evaluation.
            stop_on_first_match: Stop after first match.

        Returns:
            List of rule evaluations.
        """
        results: List[RuleEvaluation] = []

        # Sort by priority
        sorted_rules = sorted(rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            evaluation = await self.match(rule, context)
            results.append(evaluation)

            if stop_on_first_match and evaluation.matched:
                break

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get matcher statistics."""
        total = self._eval_count
        return {
            "evaluations": self._eval_count,
            "matches": self._match_count,
            "match_rate": (self._match_count / total) if total > 0 else 0.0,
            "avg_duration_ms": (self._total_duration_ms / total) if total > 0 else 0.0,
            "parser_cache_size": len(self._parser._cache),
            "compiler_cache_size": len(self._compiler._compile_cache),
        }

    def reset_stats(self) -> None:
        """Reset all matcher statistics."""
        self._eval_count = 0
        self._match_count = 0
        self._total_duration_ms = 0.0