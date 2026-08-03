"""
Alert engine.

Core alert processing engine that
coordinates metric evaluation, alert
firing, and notification routing.

The engine processes collected metrics
against configured alert rules, firing
AlertEvents when thresholds are breached
and routing them through the AlertRouter.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from ..alert_models import AlertEvent, AlertHistory
from ..models import MetricPoint
from .evaluator import RuleEvaluator
from .router import AlertRouter
from .rule import AlertRule, AlertRuleSet


class AlertEngine:
    """
    Alert processing engine.

    Coordinates the evaluation of metrics
    against alert rules and routes fired
    alerts through the notification pipeline.

    Pipeline:
        Metrics → Evaluator → Suppression → Router → Channels

    Usage:
        engine = AlertEngine(
            evaluator=RuleEvaluator(),
            router=AlertRouter(),
        )

        # Add rules
        engine.add_rule(AlertRule(
            name="high_cpu",
            metric="icyquant_cpu_usage_percent",
            operator=">",
            threshold=90.0,
            level=AlertLevel.CRITICAL,
        ))

        # Process metrics
        results = await engine.process(metrics)
    """

    def __init__(
        self,
        evaluator: Optional[RuleEvaluator] = None,
        router: Optional[AlertRouter] = None,
        rules: Optional[AlertRuleSet] = None,
    ) -> None:
        """
        Initialize alert engine.

        Args:
            evaluator: Rule evaluator instance.
            router: Alert router instance.
            rules: Alert rule set.
        """

        self._evaluator = evaluator or RuleEvaluator()
        self._router = router or AlertRouter()
        self._rules = rules or AlertRuleSet()
        self._history = AlertHistory()
        self._processed_count: int = 0

    @property
    def evaluator(
        self,
    ) -> RuleEvaluator:
        """Get evaluator."""
        return self._evaluator

    @property
    def router(
        self,
    ) -> AlertRouter:
        """Get router."""
        return self._router

    @property
    def rules(
        self,
    ) -> AlertRuleSet:
        """Get rules."""
        return self._rules

    @property
    def history(
        self,
    ) -> AlertHistory:
        """Get alert history."""
        return self._history

    @property
    def processed_count(
        self,
    ) -> int:
        """Get total processed metric count."""
        return self._processed_count

    def add_rule(
        self,
        rule: AlertRule,
    ) -> None:
        """
        Add an alert rule.

        Args:
            rule: AlertRule to add.
        """

        self._rules.add(rule)

    def remove_rule(
        self,
        name: str,
    ) -> None:
        """
        Remove an alert rule.

        Args:
            name: Rule name.
        """

        self._rules.remove(name)

    async def process(
        self,
        metrics: List[MetricPoint],
    ) -> List[AlertEvent]:
        """
        Process metrics against all rules.

        Evaluates each metric against matching
        rules and routes any resulting alert
        events through the notification pipeline.

        Args:
            metrics: List of MetricPoint objects.

        Returns:
            List of fired AlertEvents.
        """

        fired_alerts: List[AlertEvent] = []

        for metric in metrics:
            matching_rules = (
                self._rules.find_for_metric(metric.name)
            )

            if not matching_rules:
                continue

            for rule in matching_rules:
                event = await self._evaluator.evaluate(
                    metric, rule
                )

                if event is None:
                    continue

                # Route the alert
                await self._router.route(event)

                # Record in history
                self._history.add(event)
                fired_alerts.append(event)

        self._processed_count += len(metrics)
        return fired_alerts

    async def process_batch(
        self,
        metrics: List[MetricPoint],
    ) -> List[AlertEvent]:
        """
        Process a batch of metrics concurrently.

        Evaluates all metric/rule combinations
        in parallel for improved performance.

        Args:
            metrics: List of MetricPoint objects.

        Returns:
            List of fired AlertEvents.
        """

        tasks: List[Any] = []

        for metric in metrics:
            matching_rules = (
                self._rules.find_for_metric(metric.name)
            )
            for rule in matching_rules:
                tasks.append(
                    self._evaluator.evaluate(
                        metric, rule
                    )
                )

        results = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        fired_alerts: List[AlertEvent] = []

        for result in results:
            if isinstance(result, AlertEvent):
                await self._router.route(result)
                self._history.add(result)
                fired_alerts.append(result)

        self._processed_count += len(metrics)
        return fired_alerts

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get engine status.

        Returns:
            Status dictionary.
        """

        return {
            "rules": self._rules.count,
            "enabled_rules": len(
                self._rules.enabled_rules
            ),
            "processed_count": self._processed_count,
            "history_count": self._history.count,
            "router": self._router.get_status(),
        }

    def reset(
        self,
    ) -> None:
        """Reset engine state."""

        self._evaluator.reset()
        self._history.clear()
        self._processed_count = 0
