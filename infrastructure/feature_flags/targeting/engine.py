"""
Targeting rule engine.

Unified entry point for the targeting rules
evaluation pipeline. Orchestrates parsing,
compilation, matching, and priority resolution
to determine the final feature flag value.

Flow:
    Feature → TargetingEngine → Parser → Compiler → Matcher → Result
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from ..models import FeatureContext
from .cache import CompiledRuleCache, EvaluationCache
from .compiler import RuleCompiler
from .context import TargetContext
from .matcher import RuleMatcher
from .parser import RuleParser
from .priority import PriorityResult, PriorityResolver
from .rules import RuleEvaluation, RuleSet, TargetRule

logger = logging.getLogger(__name__)


class TargetingEngine:
    """
    Unified targeting rules evaluation engine.

    Provides the main entry point for rule-based
    feature flag evaluation. Coordinates parsing,
    compilation, matching, and priority resolution
    to produce a final evaluation result.

    Usage:
        engine = TargetingEngine()
        result = await engine.evaluate(flag_rules, feature_context)
    """

    def __init__(
        self,
        parser: Optional[RuleParser] = None,
        compiler: Optional[RuleCompiler] = None,
        matcher: Optional[RuleMatcher] = None,
        priority_resolver: Optional[PriorityResolver] = None,
        compiled_cache: Optional[CompiledRuleCache] = None,
        eval_cache: Optional[EvaluationCache] = None,
    ) -> None:
        self._parser = parser or RuleParser()
        self._compiler = compiler or RuleCompiler()
        self._matcher = matcher or RuleMatcher(self._parser, self._compiler)
        self._resolver = priority_resolver or PriorityResolver()
        self._compiled_cache = compiled_cache or CompiledRuleCache()
        self._eval_cache = eval_cache or EvaluationCache()

        self._evaluation_count = 0
        self._rule_match_count = 0
        self._total_duration_ms = 0.0
        self._lock = asyncio.Lock()

    async def evaluate(
        self,
        rules: List[TargetRule],
        feature_context: Optional[FeatureContext] = None,
        default_value: Any = False,
        use_cache: bool = True,
    ) -> RuleEvaluation:
        """
        Evaluate targeting rules against a feature context.

        Args:
            rules: List of targeting rules to evaluate.
            feature_context: Feature context for evaluation.
            default_value: Default value if no rule matches.
            use_cache: Whether to use evaluation caching.

        Returns:
            RuleEvaluation result with match status and value.
        """
        start = time.perf_counter()
        self._evaluation_count += 1

        # Adapt context
        target_ctx = TargetContext.from_feature_context(feature_context)

        if not rules:
            duration_ms = (time.perf_counter() - start) * 1000
            return RuleEvaluation(
                rule_id="",
                matched=False,
                value=default_value,
                duration_ms=duration_ms,
                trace=["no_rules"],
            )

        # Check evaluation cache
        if use_cache:
            for rule in rules:
                cached = await self._eval_cache.get(rule.rule_id, target_ctx)
                if cached:
                    self._rule_match_count += 1
                    cached.trace.append("eval_cache_hit")
                    return cached

        # Evaluate all rules
        sorted_rules = sorted(rules, key=lambda r: r.priority)
        evaluations = await self._matcher.match_all(
            sorted_rules, target_ctx, stop_on_first_match=False,
        )

        # Resolve priority
        result = self._resolver.resolve_with_default(
            sorted_rules, evaluations, default_value,
        )

        duration_ms = (time.perf_counter() - start) * 1000
        self._total_duration_ms += duration_ms

        if result.has_match:
            self._rule_match_count += 1

        # Build final evaluation
        final_eval = RuleEvaluation(
            rule_id=result.matched_rule.rule_id if result.matched_rule else "",
            matched=result.has_match,
            value=result.value,
            duration_ms=duration_ms,
            trace=self._build_trace(result),
        )

        # Cache the result
        if use_cache and result.has_match:
            await self._eval_cache.put(
                final_eval.rule_id, target_ctx, final_eval,
            )

        return final_eval

    async def evaluate_rule_set(
        self,
        rule_set: RuleSet,
        feature_context: Optional[FeatureContext] = None,
        use_cache: bool = True,
    ) -> RuleEvaluation:
        """
        Evaluate a complete rule set.

        Args:
            rule_set: Rule set to evaluate.
            feature_context: Feature context.
            use_cache: Whether to use caching.

        Returns:
            RuleEvaluation result.
        """
        return await self.evaluate(
            rules=rule_set.get_enabled_rules(),
            feature_context=feature_context,
            default_value=rule_set.default_value,
            use_cache=use_cache,
        )

    def _build_trace(self, result: PriorityResult) -> List[str]:
        """Build a diagnostic trace from the resolution result."""
        trace: List[str] = []

        if result.has_match:
            trace.append(f"matched_rule:{result.matched_rule.rule_id}")
            trace.append(f"priority:{result.matched_rule.priority}")
            trace.append(f"value:{result.value}")
        else:
            trace.append("no_rule_matched")

        for eval_result in (result.all_evaluations or []):
            status = "matched" if eval_result.matched else "skipped"
            trace.append(f"  {eval_result.rule_id}: {status} ({eval_result.duration_ms:.3f}ms)")

        return trace

    async def invalidate_rule(self, rule_id: str) -> None:
        """Invalidate caches for a specific rule."""
        await self._compiled_cache.invalidate(rule_id)
        await self._eval_cache.invalidate_for_rule(rule_id)

    async def clear_caches(self) -> None:
        """Clear all caches."""
        await self._compiled_cache.clear()
        await self._eval_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        total = self._evaluation_count
        return {
            "evaluations": self._evaluation_count,
            "rule_matches": self._rule_match_count,
            "match_rate": (self._rule_match_count / total) if total > 0 else 0.0,
            "avg_duration_ms": (self._total_duration_ms / total) if total > 0 else 0.0,
            "parser": {
                "cache_size": len(self._parser._cache),
            },
            "compiler": self._compiler.get_stats(),
            "matcher": self._matcher.get_stats(),
            "resolver": self._resolver.get_stats(),
            "compiled_cache": self._compiled_cache.get_stats(),
            "eval_cache": self._eval_cache.get_stats(),
        }