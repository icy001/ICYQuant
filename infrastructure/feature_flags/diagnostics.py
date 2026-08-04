"""
Feature flag diagnostics.

Provides diagnostics and troubleshooting
utilities for the feature flag platform.
Includes rule evaluation tracing, AST
visualization, and system health
diagnostics.

Usage:
    from infrastructure.feature_flags.diagnostics import (
        RuleDiagnostics,
        trace_rule_evaluation,
        visualize_ast,
    )

    diagnostics = RuleDiagnostics()
    trace = await diagnostics.trace_evaluation(rule, context)
    print(trace.summary())
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import FeatureContext
from .targeting.context import TargetContext
from .targeting.engine import TargetingEngine
from .targeting.matcher import RuleMatcher
from .targeting.parser import RuleParser
from .targeting.rules import RuleEvaluation, TargetRule

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """A single step in an evaluation trace."""

    step: int = 0
    rule_id: str = ""
    expression: str = ""
    matched: bool = False
    value: Any = None
    duration_ms: float = 0.0
    details: str = ""


@dataclass
class EvaluationTrace:
    """
    Complete trace of a rule evaluation.

    Records each step of the evaluation
    pipeline for debugging and auditing.
    """

    flag_key: str = ""
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    steps: List[TraceStep] = field(default_factory=list)
    final_result: Optional[RuleEvaluation] = None
    total_duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"=== Evaluation Trace for '{self.flag_key}' ===",
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Total duration: {self.total_duration_ms:.3f}ms",
            f"Context: {json.dumps(self.context_snapshot, indent=2, default=str)}",
            "",
        ]

        for step in self.steps:
            status = "✓ MATCH" if step.matched else "✗ NO MATCH"
            lines.append(
                f"  [{step.step}] {step.rule_id}: {status} "
                f"({step.duration_ms:.3f}ms) - {step.details}"
            )

        if self.final_result:
            lines.append("")
            lines.append(f"Final result: matched={self.final_result.matched}, "
                         f"value={self.final_result.value}")

        if self.error:
            lines.append(f"\nERROR: {self.error}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trace to dictionary."""
        return {
            "flag_key": self.flag_key,
            "context": self.context_snapshot,
            "steps": [
                {
                    "step": s.step,
                    "rule_id": s.rule_id,
                    "expression": s.expression,
                    "matched": s.matched,
                    "value": str(s.value),
                    "duration_ms": s.duration_ms,
                    "details": s.details,
                }
                for s in self.steps
            ],
            "final_result": {
                "matched": self.final_result.matched if self.final_result else False,
                "value": str(self.final_result.value) if self.final_result else None,
            },
            "total_duration_ms": self.total_duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }


class RuleDiagnostics:
    """
    Diagnostic tools for rule evaluation.

    Provides tracing, AST visualization, and
    performance analysis for targeting rules.

    Usage:
        diag = RuleDiagnostics()
        trace = await diag.trace_evaluation(rules, context)
        print(trace.summary())
    """

    def __init__(self) -> None:
        self._traces: List[EvaluationTrace] = []
        self._lock = asyncio.Lock()

    async def trace_evaluation(
        self,
        rules: List[TargetRule],
        flag_key: str,
        feature_context: Optional[FeatureContext] = None,
    ) -> EvaluationTrace:
        """
        Trace the full evaluation of rules against a context.

        Records each step of the evaluation pipeline
        for debugging and compliance purposes.

        Args:
            rules: Rules to evaluate.
            flag_key: Associated flag key.
            feature_context: Evaluation context.

        Returns:
            Complete evaluation trace.
        """
        trace = EvaluationTrace(flag_key=flag_key)
        start = time.perf_counter()

        # Adapt context
        target_ctx = TargetContext.from_feature_context(feature_context)
        trace.context_snapshot = target_ctx.to_dict()

        try:
            # Parse and log each rule
            parser = RuleParser()
            matcher = RuleMatcher()

            sorted_rules = sorted(rules, key=lambda r: r.priority)

            for i, rule in enumerate(sorted_rules):
                step_start = time.perf_counter()

                step = TraceStep(
                    step=i + 1,
                    rule_id=rule.rule_id,
                    expression=rule.expression,
                )

                if not rule.enabled:
                    step.details = "rule disabled"
                    step.matched = False
                elif not rule.expression:
                    step.details = "no expression"
                    step.matched = False
                else:
                    # Try parse
                    try:
                        node = parser.parse(rule.expression)
                        step.details = f"AST depth={_get_depth(node)}, "
                        f"conditions={_get_count(node)}"

                        # Evaluate
                        eval_result = await matcher.match(rule, target_ctx)
                        step.matched = eval_result.matched
                        step.value = eval_result.value
                        step.details += f", matched={eval_result.matched}"

                    except Exception as e:
                        step.details = f"parse error: {e}"
                        step.matched = False

                step.duration_ms = (time.perf_counter() - step_start) * 1000
                trace.steps.append(step)

            # Final evaluation via engine
            engine = TargetingEngine()
            final_result = await engine.evaluate(
                rules=rules,
                feature_context=feature_context,
                use_cache=False,
            )
            trace.final_result = final_result
            trace.total_duration_ms = (time.perf_counter() - start) * 1000

        except Exception as e:
            trace.error = str(e)
            trace.total_duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Trace evaluation failed: %s", e)

        async with self._lock:
            self._traces.append(trace)

        return trace

    def visualize_ast(self, expression: str) -> str:
        """
        Generate a text visualization of an expression's AST.

        Args:
            expression: Rule expression string.

        Returns:
            ASCII visualization of the AST.
        """
        parser = RuleParser()
        try:
            node = parser.parse(expression)
            return _visualize_node(node, prefix="", is_root=True)
        except Exception as e:
            return f"Error parsing expression: {e}"

    async def get_recent_traces(
        self,
        limit: int = 20,
        flag_key: Optional[str] = None,
    ) -> List[EvaluationTrace]:
        """Get recent evaluation traces."""
        async with self._lock:
            traces = list(reversed(self._traces))
            if flag_key:
                traces = [t for t in traces if t.flag_key == flag_key]
            return traces[:limit]

    def clear_traces(self) -> None:
        """Clear all stored traces."""
        self._traces.clear()


def _visualize_node(node, prefix: str = "", is_root: bool = True) -> str:
    """Generate ASCII visualization of an AST node."""
    from .targeting.conditions import AndNode, ConditionNode, NotNode, OrNode

    lines = []
    if is_root:
        lines.append("AST Root:")

    if isinstance(node, ConditionNode):
        op_str = node.operator.value if hasattr(node.operator, 'value') else str(node.operator)
        lines.append(f"{prefix}├── [{node.attribute} {op_str} {node.value}]")
    elif isinstance(node, AndNode):
        lines.append(f"{prefix}├── AND ({len(node.children)} children)")
        for i, child in enumerate(node.children):
            connector = "└── " if i == len(node.children) - 1 else "├── "
            lines.append(f"{prefix}{connector}")
            lines.append(_visualize_node(child, prefix + "    ", False))
    elif isinstance(node, OrNode):
        lines.append(f"{prefix}├── OR ({len(node.children)} children)")
        for i, child in enumerate(node.children):
            connector = "└── " if i == len(node.children) - 1 else "├── "
            lines.append(f"{prefix}{connector}")
            lines.append(_visualize_node(child, prefix + "    ", False))
    elif isinstance(node, NotNode):
        lines.append(f"{prefix}├── NOT")
        if node.child:
            lines.append(_visualize_node(node.child, prefix + "    ", False))

    return "\n".join(lines)


def _get_depth(node) -> int:
    """Get the depth of an AST node."""
    from .targeting.conditions import node_depth
    return node_depth(node)


def _get_count(node) -> int:
    """Get the condition count of an AST node."""
    from .targeting.conditions import node_count
    return node_count(node)