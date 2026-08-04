"""
Targeting rule compiler.

Compiles parsed AST nodes into optimized
callable matchers that can evaluate rule
conditions against a TargetContext.

The compiler performs:
    - Expression tree optimization
    - Matcher function generation
    - Compilation caching
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .conditions import (
    AndNode,
    ConditionNode,
    OrNode,
    RuleNode,
)
from .context import TargetContext
from .operators import Operator, get_compare_fn

logger = logging.getLogger(__name__)

# Type alias for compiled matcher functions
MatcherFn = Callable[[TargetContext], bool]


class RuleCompiler:
    """
    Compiles rule AST nodes into matcher functions.

    Transforms a parsed AST into an optimized callable
    that can evaluate rule conditions against a
    TargetContext. Supports compilation caching for
    repeated evaluations.

    Usage:
        compiler = RuleCompiler()
        matcher = compiler.compile(ast_node)
        result = matcher(context)
    """

    def __init__(self) -> None:
        self._compile_cache: Dict[str, MatcherFn] = {}
        self._compilation_count = 0
        self._cache_hits = 0

    def compile(
        self,
        node: RuleNode,
        cache_key: Optional[str] = None,
    ) -> MatcherFn:
        """
        Compile an AST node into a matcher function.

        Args:
            node: AST node to compile.
            cache_key: Optional cache key for caching.

        Returns:
            Matcher function that evaluates the rule.
        """
        self._compilation_count += 1

        # Check cache
        if cache_key and cache_key in self._compile_cache:
            self._cache_hits += 1
            return self._compile_cache[cache_key]

        # Compile the node tree
        matcher = self._compile_node(node)

        # Cache if key provided
        if cache_key:
            self._compile_cache[cache_key] = matcher

        return matcher

    def clear_cache(self) -> None:
        """Clear the compilation cache."""
        self._compile_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get compiler statistics."""
        return {
            "compilations": self._compilation_count,
            "cache_hits": self._cache_hits,
            "cache_size": len(self._compile_cache),
        }

    def _compile_node(self, node: RuleNode) -> MatcherFn:
        """Compile a node based on its type."""
        if isinstance(node, ConditionNode):
            return self._compile_condition(node)
        elif isinstance(node, AndNode):
            return self._compile_and(node)
        elif isinstance(node, OrNode):
            return self._compile_or(node)
        else:
            from .conditions import NotNode
            if isinstance(node, NotNode):
                return self._compile_not(node)
            # Fallback: always True
            return lambda ctx: True

    def _compile_condition(self, node: ConditionNode) -> MatcherFn:
        """Compile a leaf condition node into a matcher."""
        attribute = node.attribute
        operator = node.operator
        expected = node.value
        compare_fn = get_compare_fn(operator)

        # Special case: "true" condition always matches
        if attribute == "true":
            return lambda ctx: True

        # Special case: "false" condition never matches
        if attribute == "false":
            return lambda ctx: False

        def matcher(ctx: TargetContext) -> bool:
            actual = ctx.get_attribute(attribute)
            return compare_fn(actual, expected)

        return matcher

    def _compile_and(self, node: AndNode) -> MatcherFn:
        """Compile an AND node into a matcher."""
        child_matchers = [
            self._compile_node(child)
            for child in node.children
        ]

        if len(child_matchers) == 0:
            return lambda ctx: True

        if len(child_matchers) == 1:
            return child_matchers[0]

        def matcher(ctx: TargetContext) -> bool:
            return all(m(ctx) for m in child_matchers)

        return matcher

    def _compile_or(self, node: OrNode) -> MatcherFn:
        """Compile an OR node into a matcher."""
        child_matchers = [
            self._compile_node(child)
            for child in node.children
        ]

        if len(child_matchers) == 0:
            return lambda ctx: False

        if len(child_matchers) == 1:
            return child_matchers[0]

        def matcher(ctx: TargetContext) -> bool:
            return any(m(ctx) for m in child_matchers)

        return matcher

    def _compile_not(self, node) -> MatcherFn:
        """Compile a NOT node into a matcher."""
        child_matcher = self._compile_node(node.child) if node.child else lambda ctx: True

        def matcher(ctx: TargetContext) -> bool:
            return not child_matcher(ctx)

        return matcher


class OptimizedRuleCompiler(RuleCompiler):
    """
    Extended compiler with optimization strategies.

    Implements additional optimizations:
        - Short-circuit evaluation for AND/OR
        - Attribute lookup caching
        - Batch pre-compilation
    """

    def compile_batch(
        self,
        nodes: List[RuleNode],
        cache_prefix: str = "",
    ) -> List[MatcherFn]:
        """
        Compile multiple nodes at once.

        Args:
            nodes: List of AST nodes.
            cache_prefix: Prefix for cache keys.

        Returns:
            List of matcher functions.
        """
        matchers: List[MatcherFn] = []
        for i, node in enumerate(nodes):
            key = f"{cache_prefix}_{i}" if cache_prefix else None
            matchers.append(self.compile(node, cache_key=key))
        return matchers