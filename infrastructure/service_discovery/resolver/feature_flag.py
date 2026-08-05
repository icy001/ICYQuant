"""Feature-flag-based routing for service discovery.

Provides ``FeatureFlagRouter`` which enables dynamic routing
decisions through registered feature flag rule functions,
supporting A/B testing and progressive rollouts.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class FeatureFlagRouter:
    """Routes service instances based on feature flags.

    Supports dynamic registration of feature flag rules that
    determine whether an instance set should be filtered based
    on the current resolution context.

    Usage::

        router = FeatureFlagRouter()
        router.register_flag("dark_launch", lambda ctx: ctx.user_id in whitelist)
        filtered = router.filter(instances, context)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._flags: Dict[str, Dict[str, Any]] = {}
        self._route_count = 0
        self._flag_hits: Dict[str, int] = {}

    def register_flag(
        self,
        flag_name: str,
        rule_fn: Callable[[ResolveContext], bool],
    ) -> None:
        """Register a feature flag with its rule function.

        Args:
            flag_name: The feature flag identifier.
            rule_fn: A callable that receives a ``ResolveContext``
                and returns whether the flag is enabled.
        """
        if not flag_name:
            raise ValueError("Flag name cannot be empty.")
        if not callable(rule_fn):
            raise TypeError("rule_fn must be callable.")
        with self._lock:
            self._flags[flag_name] = {
                "rule_fn": rule_fn,
                "enabled": True,
            }
            logger.debug("Feature flag registered: '%s'", flag_name)

    def unregister_flag(self, flag_name: str) -> None:
        """Unregister a feature flag.

        Args:
            flag_name: The feature flag identifier.
        """
        with self._lock:
            if flag_name in self._flags:
                del self._flags[flag_name]
                logger.debug("Feature flag unregistered: '%s'", flag_name)
            else:
                logger.warning(
                    "Feature flag '%s' not found for unregistration.",
                    flag_name,
                )

    def is_enabled(
        self,
        flag_name: str,
        context: Optional[ResolveContext] = None,
    ) -> bool:
        """Check whether a feature flag is enabled for the context.

        Args:
            flag_name: The feature flag identifier.
            context: The resolution context.

        Returns:
            True if the flag is enabled, False otherwise.
        """
        with self._lock:
            flag = self._flags.get(flag_name)
            if flag is None:
                return False
            if not flag["enabled"]:
                return False
            rule_fn = flag["rule_fn"]

        if context is None:
            return False
        try:
            return bool(rule_fn(context))
        except Exception as e:
            logger.warning(
                "Error evaluating feature flag '%s': %s", flag_name, e
            )
            return False

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Filter instances based on active feature flags.

        Each registered flag is evaluated; if enabled, only
        instances matching the flag's metadata pass through.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of instances matching active flags.
        """
        if not instances:
            return []

        with self._lock:
            self._route_count += 1
            flag_names = list(self._flags.keys())

        if not flag_names or context is None:
            return list(instances)

        active_flags: List[str] = []
        for flag_name in flag_names:
            if self.is_enabled(flag_name, context):
                active_flags.append(flag_name)

        if not active_flags:
            return list(instances)

        with self._lock:
            for flag_name in active_flags:
                self._flag_hits[flag_name] = (
                    self._flag_hits.get(flag_name, 0) + 1
                )

        result: List[ServiceInstance] = []
        for instance in instances:
            instance_features = {}
            if isinstance(instance.metadata, dict):
                instance_features = dict(
                    instance.metadata.get("features", {}) or {}
                )
            match = True
            for flag_name in active_flags:
                if not instance_features.get(flag_name, False):
                    match = False
                    break
            if match:
                result.append(instance)

        return result

    def get_flags(self) -> Dict[str, Dict[str, Any]]:
        """Return all registered flags and their state.

        Returns:
            A dictionary of flag names to their configuration.
        """
        with self._lock:
            return {
                name: {
                    "enabled": info["enabled"],
                }
                for name, info in self._flags.items()
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return feature flag router statistics.

        Returns:
            A dictionary with routing counts and flag usage.
        """
        with self._lock:
            return {
                "router": "FeatureFlagRouter",
                "route_count": self._route_count,
                "registered_flags": len(self._flags),
                "flag_hits": dict(self._flag_hits),
                "flags": self.get_flags(),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"FeatureFlagRouter(flags={len(self._flags)}, "
                f"routes={self._route_count})"
            )