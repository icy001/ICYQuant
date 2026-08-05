"""Service router for advanced instance filtering.

Provides ``ServiceRouter`` which applies routing rules to filter
candidate instances before load balancing. Supports version, canary,
namespace, zone, region, and feature-flag-based routing.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class ServiceRouter:
    """Routes service instances through configurable rules.

    Supports multiple rule types that are applied sequentially.
    Each rule filters the candidate list, passing only matching
    instances to the next rule.

    Supported rule types:
    - ``version``: Filter by version constraint.
    - ``canary``: Prefer or exclude canary instances.
    - ``namespace``: Filter by namespace.
    - ``zone``: Filter by availability zone.
    - ``region``: Filter by geographic region.
    - ``feature_flag``: Filter by feature flag metadata.

    Usage::

        router = ServiceRouter()
        router.add_rule("version", version="2.0.0")
        router.add_rule("canary", enabled=True)
        result = await router.route(instances, context)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: List[Dict[str, Any]] = []
        self._route_count = 0
        self._filtered_count = 0

    def add_rule(self, rule_type: str, **kwargs: Any) -> None:
        """Add a routing rule.

        Args:
            rule_type: One of ``version``, ``canary``, ``namespace``,
                ``zone``, ``region``, or ``feature_flag``.
            **kwargs: Rule parameters specific to the rule type.
        """
        with self._lock:
            rule: Dict[str, Any] = {"type": rule_type, "params": dict(kwargs)}
            self._rules.append(rule)
            logger.debug("Added routing rule: %s", rule)

    def clear_rules(self) -> None:
        """Remove all routing rules."""
        with self._lock:
            self._rules.clear()
            logger.debug("All routing rules cleared.")

    def get_rules(self) -> List[Dict[str, Any]]:
        """Return the current list of routing rules.

        Returns:
            A list of rule dictionaries.
        """
        with self._lock:
            return [dict(rule) for rule in self._rules]

    async def route(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Filter instances through all routing rules.

        Rules are applied sequentially. Instances that do not
        match a rule are excluded from subsequent rules.

        Args:
            instances: Candidate instances.
            context: Optional resolution context used for
                context-aware rule parameters.

        Returns:
            A filtered list of instances matching all rules.
        """
        if not instances:
            return []
        with self._lock:
            rules = list(self._rules)
            self._route_count += 1
        candidates = list(instances)
        for rule in rules:
            rule_type = rule.get("type", "")
            params = rule.get("params", {})
            candidates = self._apply_rule(candidates, rule_type, params, context)
            if not candidates:
                logger.debug(
                    "All instances filtered out by rule '%s'.",
                    rule_type,
                )
                break
        with self._lock:
            self._filtered_count += len(instances) - len(candidates)
        return candidates

    def _apply_rule(
        self,
        instances: List[ServiceInstance],
        rule_type: str,
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        """Apply a single routing rule to instances.

        Args:
            instances: Current candidate list.
            rule_type: The rule type identifier.
            params: Rule parameters.
            context: Optional resolution context.

        Returns:
            Filtered list of instances.
        """
        if rule_type == "version":
            return self._filter_by_version(instances, params, context)
        if rule_type == "canary":
            return self._filter_by_canary(instances, params, context)
        if rule_type == "namespace":
            return self._filter_by_namespace(instances, params, context)
        if rule_type == "zone":
            return self._filter_by_zone(instances, params, context)
        if rule_type == "region":
            return self._filter_by_region(instances, params, context)
        if rule_type == "feature_flag":
            return self._filter_by_feature_flag(instances, params, context)
        logger.warning("Unknown rule type: '%s'", rule_type)
        return instances

    @staticmethod
    def _filter_by_version(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        version = params.get("version")
        if version is None and context is not None:
            version = context.version
        if version is None:
            return instances
        return [i for i in instances if i.version == version]

    @staticmethod
    def _filter_by_canary(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        enabled = params.get("enabled")
        if enabled is None and context is not None:
            enabled = context.canary
        if enabled is None:
            return instances
        canary_instances: List[ServiceInstance] = []
        for instance in instances:
            is_canary = False
            if isinstance(instance.metadata, dict):
                is_canary = bool(instance.metadata.get("canary", False))
            if is_canary == bool(enabled):
                canary_instances.append(instance)
        return canary_instances

    @staticmethod
    def _filter_by_namespace(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        namespace = params.get("namespace")
        if namespace is None and context is not None:
            namespace = context.namespace
        if namespace is None:
            return instances
        return [i for i in instances if i.namespace == namespace]

    @staticmethod
    def _filter_by_zone(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        zone = params.get("zone")
        if zone is None and context is not None:
            zone = context.zone
        if zone is None:
            return instances
        result: List[ServiceInstance] = []
        for instance in instances:
            instance_zone = ""
            if isinstance(instance.metadata, dict):
                instance_zone = str(instance.metadata.get("zone", ""))
            if instance_zone == zone:
                result.append(instance)
        return result

    @staticmethod
    def _filter_by_region(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        region = params.get("region")
        if region is None and context is not None:
            region = context.region
        if region is None:
            return instances
        result: List[ServiceInstance] = []
        for instance in instances:
            instance_region = ""
            if isinstance(instance.metadata, dict):
                instance_region = str(instance.metadata.get("region", ""))
            if instance_region == region:
                result.append(instance)
        return result

    @staticmethod
    def _filter_by_feature_flag(
        instances: List[ServiceInstance],
        params: Dict[str, Any],
        context: Optional[ResolveContext],
    ) -> List[ServiceInstance]:
        features = params.get("features")
        if features is None and context is not None:
            features = context.features
        if not features:
            return instances
        result: List[ServiceInstance] = []
        for instance in instances:
            instance_features = {}
            if isinstance(instance.metadata, dict):
                instance_features = dict(
                    instance.metadata.get("features", {}) or {}
                )
            match = True
            for flag_name, flag_value in features.items():
                if instance_features.get(flag_name) != flag_value:
                    match = False
                    break
            if match:
                result.append(instance)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return router statistics.

        Returns:
            A dictionary with rule count and routing counts.
        """
        with self._lock:
            return {
                "router": "ServiceRouter",
                "rule_count": len(self._rules),
                "rules": [dict(r) for r in self._rules],
                "route_count": self._route_count,
                "filtered_count": self._filtered_count,
            }

    def __repr__(self) -> str:
        return (
            f"ServiceRouter(rules={len(self._rules)}, "
            f"routes={self._route_count})"
        )