"""
Alert rule evaluator.

Evaluates metric values against
alert rules to detect threshold
breaches and generate AlertEvents.

Supports multiple comparison
operators and duration-based
sustained condition tracking.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..alert_models import AlertEvent, AlertLevel
from ..models import MetricPoint
from .rule import AlertRule


class RuleEvaluator:
    """
    Alert rule evaluator.

    Evaluates MetricPoint values
    against AlertRule thresholds
    to detect breaches.

    Supports operators:
    - >  : greater than
    - <  : less than
    - >= : greater than or equal
    - <= : less than or equal
    - == : equal
    - != : not equal

    Also tracks sustained condition
    duration to support rules that
    require a metric to breach for
    a minimum duration before firing.

    Usage:
        evaluator = RuleEvaluator()

        for metric in metrics:
            for rule in rules:
                event = await evaluator.evaluate(metric, rule)
                if event:
                    # Alert fired
    """

    # Operator mapping
    _OPERATORS = {
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    def __init__(
        self,
    ) -> None:
        """Initialize evaluator with empty state."""

        self._breach_start: Dict[str, float] = {}

    async def evaluate(
        self,
        metric: MetricPoint,
        rule: AlertRule,
    ) -> Optional[AlertEvent]:
        """
        Evaluate a metric against a rule.

        Args:
            metric: MetricPoint to evaluate.
            rule: AlertRule to check against.

        Returns:
            AlertEvent if rule breached, None otherwise.
        """

        if not rule.enabled:
            return None

        if not rule.matches_metric(metric.name):
            return None

        operator_fn = self._OPERATORS.get(
            rule.operator
        )
        if operator_fn is None:
            return None

        breached = operator_fn(
            metric.value, rule.threshold
        )

        if not breached:
            self._breach_start.pop(
                rule.name, None
            )
            return None

        # Check sustained duration
        if rule.duration > 0:
            now = time.time()
            start = self._breach_start.get(rule.name)

            if start is None:
                self._breach_start[rule.name] = now
                return None

            elapsed = now - start
            if elapsed < rule.duration:
                return None

        # Build alert event
        return AlertEvent(
            rule=rule.name,
            level=rule.level,
            metric=metric.name,
            value=metric.value,
            threshold=rule.threshold,
            labels={
                **metric.labels,
                **rule.labels,
            },
            message=rule.message or (
                f"Alert '{rule.name}': "
                f"metric '{metric.name}' "
                f"value {metric.value} "
                f"{rule.operator} "
                f"{rule.threshold}"
            ),
        )

    def reset(
        self,
        rule_name: Optional[str] = None,
    ) -> None:
        """
        Reset breach tracking state.

        Args:
            rule_name: Specific rule to reset,
                      or None for all.
        """

        if rule_name:
            self._breach_start.pop(
                rule_name, None
            )
        else:
            self._breach_start.clear()

    def get_breach_duration(
        self,
        rule_name: str,
    ) -> float:
        """
        Get current breach duration for a rule.

        Args:
            rule_name: Rule name.

        Returns:
            Seconds since breach started, 0 if not breaching.
        """

        start = self._breach_start.get(rule_name)
        if start is None:
            return 0.0
        return time.time() - start
