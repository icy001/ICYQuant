"""
Targeting rule priority resolution.

Handles rule prioritization and conflict
resolution when multiple rules match the
same context. Priority levels determine
which rule takes precedence.

Priority order (highest first):
    1. Exact match (all attributes match)
    2. Tag match (tags match)
    3. Range match (numeric ranges)
    4. Default rule (catch-all)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from .context import TargetContext
from .rules import RuleEvaluation, TargetRule


class PriorityLevel:
    """Priority level constants for rule matching."""

    EXACT_MATCH = 100
    TAG_MATCH = 80
    RANGE_MATCH = 60
    DEFAULT = 10
    KILL_SWITCH = 200


@dataclass
class PriorityResult:
    """Result of priority-based rule resolution."""

    matched_rule: Optional[TargetRule] = None
    matched_evaluation: Optional[RuleEvaluation] = None
    all_evaluations: List[RuleEvaluation] = None

    @property
    def has_match(self) -> bool:
        return self.matched_rule is not None and self.matched_evaluation is not None

    @property
    def value(self) -> Any:
        if self.matched_rule and self.matched_evaluation:
            return self.matched_rule.value
        return None


class PriorityResolver:
    """
    Resolves rule conflicts based on priority.

    When multiple rules match a context, this
    resolver selects the rule with the highest
    priority. If rules have the same priority,
    the first one in the sorted order wins.

    Usage:
        resolver = PriorityResolver()
        result = resolver.resolve(rules, evaluations)
    """

    def __init__(self) -> None:
        self._resolutions = 0
        self._conflicts_resolved = 0

    def resolve(
        self,
        rules: List[TargetRule],
        evaluations: List[RuleEvaluation],
    ) -> PriorityResult:
        """
        Resolve rule conflicts and select the winning rule.

        Args:
            rules: All evaluated rules.
            evaluations: Corresponding evaluation results.

        Returns:
            PriorityResult with the selected rule.
        """
        self._resolutions += 1

        # Find matching rules
        matches: List[tuple] = []
        for rule, eval_result in zip(rules, evaluations):
            if eval_result.matched:
                matches.append((rule, eval_result))

        if not matches:
            return PriorityResult(
                matched_rule=None,
                matched_evaluation=None,
                all_evaluations=evaluations,
            )

        if len(matches) == 1:
            rule, eval_result = matches[0]
            return PriorityResult(
                matched_rule=rule,
                matched_evaluation=eval_result,
                all_evaluations=evaluations,
            )

        # Multiple matches: resolve by priority
        self._conflicts_resolved += 1
        best_rule, best_eval = matches[0]

        for rule, eval_result in matches[1:]:
            if rule.priority < best_rule.priority:
                # Lower priority number = higher priority
                best_rule = rule
                best_eval = eval_result

        return PriorityResult(
            matched_rule=best_rule,
            matched_evaluation=best_eval,
            all_evaluations=evaluations,
        )

    def resolve_with_default(
        self,
        rules: List[TargetRule],
        evaluations: List[RuleEvaluation],
        default_value: Any = False,
    ) -> PriorityResult:
        """
        Resolve conflicts with a default fallback.

        Args:
            rules: All evaluated rules.
            evaluations: Corresponding evaluation results.
            default_value: Value to use when no rule matches.

        Returns:
            PriorityResult with the selected rule or default.
        """
        result = self.resolve(rules, evaluations)

        if result.has_match:
            return result

        # Find default rule (lowest priority)
        default_rules = [r for r in rules if r.priority >= 999]
        if default_rules:
            default_rule = default_rules[0]
            return PriorityResult(
                matched_rule=default_rule,
                matched_evaluation=RuleEvaluation(
                    rule_id=default_rule.rule_id,
                    matched=True,
                    value=default_value,
                    duration_ms=0.0,
                    trace=["default_rule"],
                ),
                all_evaluations=evaluations,
            )

        return PriorityResult(
            matched_rule=None,
            matched_evaluation=None,
            all_evaluations=evaluations,
        )

    def get_stats(self) -> dict:
        """Get resolver statistics."""
        return {
            "resolutions": self._resolutions,
            "conflicts_resolved": self._conflicts_resolved,
            "avg_conflicts": (
                self._conflicts_resolved / self._resolutions
                if self._resolutions > 0 else 0.0
            ),
        }