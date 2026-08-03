"""
Alert rule definitions.

Defines AlertRule dataclass and
AlertRuleSet for managing collections
of alert rules with matching and
filtering capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..alert_models import AlertLevel


@dataclass
class AlertRule:
    """
    Alert rule definition.

    Defines a threshold-based alert
    rule that triggers when a metric
    breaches a configured threshold
    for a specified duration.

    Attributes:
        name: Unique rule name.
        metric: Metric name to monitor.
        operator: Comparison operator (>, <, >=, <=, ==, !=).
        threshold: Threshold value.
        duration: Sustained duration in seconds before firing.
        enabled: Whether the rule is active.
        level: Alert severity level.
        message: Custom alert message.
        labels: Additional labels for matching.
        cooldown: Minimum seconds between repeated alerts.
    """

    name: str
    metric: str
    operator: str = ">"
    threshold: float = 0.0
    duration: int = 0
    enabled: bool = True
    level: AlertLevel = AlertLevel.WARNING
    message: str = ""
    labels: Dict[str, str] = field(
        default_factory=dict
    )
    cooldown: int = 60

    def matches_metric(
        self,
        metric_name: str,
    ) -> bool:
        """
        Check if this rule applies to a metric.

        Supports prefix matching with wildcard '*'.

        Args:
            metric_name: Metric name to check.

        Returns:
            True if the rule matches.
        """

        if self.metric.endswith("*"):
            prefix = self.metric[:-1]
            return metric_name.startswith(prefix)
        return metric_name == self.metric

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "name": self.name,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "duration": self.duration,
            "enabled": self.enabled,
            "level": self.level.value,
            "message": self.message,
            "labels": self.labels,
            "cooldown": self.cooldown,
        }


class AlertRuleSet:
    """
    Collection of alert rules.

    Provides management and lookup
    capabilities for multiple alert
    rules, including filtering by
    metric name and enabled state.

    Usage:
        rules = AlertRuleSet()
        rules.add(AlertRule(
            name="high_cpu",
            metric="icyquant_cpu_usage_percent",
            operator=">",
            threshold=90.0,
            level=AlertLevel.CRITICAL,
        ))
        matching = rules.find_for_metric("icyquant_cpu_usage_percent")
    """

    def __init__(
        self,
    ) -> None:
        """Initialize empty rule set."""

        self._rules: Dict[str, AlertRule] = {}

    def add(
        self,
        rule: AlertRule,
    ) -> None:
        """
        Add a rule to the set.

        Args:
            rule: AlertRule to add.
        """

        self._rules[rule.name] = rule

    def remove(
        self,
        name: str,
    ) -> None:
        """
        Remove a rule by name.

        Args:
            name: Rule name to remove.
        """

        self._rules.pop(name, None)

    def get(
        self,
        name: str,
    ) -> Optional[AlertRule]:
        """
        Get a rule by name.

        Args:
            name: Rule name.

        Returns:
            AlertRule or None.
        """

        return self._rules.get(name)

    def find_for_metric(
        self,
        metric_name: str,
    ) -> List[AlertRule]:
        """
        Find all rules matching a metric.

        Args:
            metric_name: Metric name to match.

        Returns:
            List of matching enabled rules.
        """

        return [
            rule
            for rule in self._rules.values()
            if rule.enabled
            and rule.matches_metric(metric_name)
        ]

    @property
    def rules(
        self,
    ) -> List[AlertRule]:
        """Get all rules."""
        return list(self._rules.values())

    @property
    def enabled_rules(
        self,
    ) -> List[AlertRule]:
        """Get enabled rules only."""
        return [
            r for r in self._rules.values() if r.enabled
        ]

    @property
    def count(
        self,
    ) -> int:
        """Get total rule count."""
        return len(self._rules)

    def to_list(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Convert to list of dictionaries.

        Returns:
            List of rule dictionaries.
        """

        return [r.to_dict() for r in self._rules.values()]
