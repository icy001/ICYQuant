"""Canary routing for service discovery.

Provides ``CanaryRouter`` which supports percentage-based canary
deployment with user and region whitelist support for safe
progressive rollouts.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class CanaryRouter:
    """Routes a percentage of traffic to canary instances.

    Supports percentage-based canary routing with user and
    region whitelists for targeted testing.

    Usage::

        router = CanaryRouter()
        router.configure("payment-service", percentage=10.0)
        filtered = router.filter(instances, context)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._route_count = 0
        self._canary_count = 0
        self._normal_count = 0
        self._last_canary_check: Dict[str, float] = {}

    def configure(
        self,
        service_name: str,
        percentage: float = 0.0,
        target_versions: Optional[List[str]] = None,
        user_whitelist: Optional[List[str]] = None,
        region_whitelist: Optional[List[str]] = None,
    ) -> None:
        """Configure canary routing for a service.

        Args:
            service_name: The logical service name.
            percentage: Percentage of traffic to route to canary
                (0.0 to 100.0).
            target_versions: Specific versions to treat as canary.
            user_whitelist: Users always routed to canary.
            region_whitelist: Regions always routed to canary.
        """
        with self._lock:
            self._configs[service_name] = {
                "percentage": max(0.0, min(100.0, float(percentage))),
                "target_versions": list(target_versions) if target_versions else [],
                "user_whitelist": list(user_whitelist) if user_whitelist else [],
                "region_whitelist": list(region_whitelist) if region_whitelist else [],
            }
            logger.info(
                "Canary configured for '%s': %.1f%%, versions=%s, "
                "users=%s, regions=%s",
                service_name,
                percentage,
                target_versions,
                user_whitelist,
                region_whitelist,
            )

    def is_canary(
        self,
        service_name: str,
        context: Optional[ResolveContext] = None,
    ) -> bool:
        """Determine whether a request should go to canary.

        Checks user whitelist, region whitelist, and then
        applies percentage-based probabilistic routing.

        Args:
            service_name: The logical service name.
            context: The resolution context.

        Returns:
            True if the request should be routed to canary.
        """
        with self._lock:
            config = self._configs.get(service_name)

        if config is None:
            if context is not None:
                return bool(context.canary)
            return False

        if context is not None:
            user_id = context.user_id
            if user_id and user_id in config["user_whitelist"]:
                return True

            region = context.region
            if region and region in config["region_whitelist"]:
                return True

        percentage = config["percentage"]
        if percentage <= 0.0:
            return False
        if percentage >= 100.0:
            return True

        import hashlib

        key = f"{service_name}:{context.user_id if context else 'anon'}:{time.time()}"
        hash_int = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return (hash_int % 10000) < (percentage * 100)

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Filter instances based on canary routing decision.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of instances (canary or stable).
        """
        if not instances:
            return []

        service_name = ""
        if instances:
            service_name = instances[0].service_name
        if context is not None:
            service_name = service_name or context.namespace

        with self._lock:
            config = self._configs.get(service_name)
            self._route_count += 1

        if config is None:
            with self._lock:
                self._normal_count += 1
            return list(instances)

        go_canary = self.is_canary(service_name, context)

        if go_canary:
            target_versions = config["target_versions"]
            canary_instances = self._filter_canary(instances, target_versions)
            if canary_instances:
                with self._lock:
                    self._canary_count += 1
                return canary_instances
            with self._lock:
                self._normal_count += 1
            return list(instances)
        else:
            with self._lock:
                self._normal_count += 1
            target_versions = config["target_versions"]
            if target_versions:
                normal_instances = [
                    i for i in instances if i.version not in target_versions
                ]
                if normal_instances:
                    return normal_instances
            return list(instances)

    @staticmethod
    def _filter_canary(
        instances: List[ServiceInstance],
        target_versions: List[str],
    ) -> List[ServiceInstance]:
        result: List[ServiceInstance] = []
        for instance in instances:
            is_canary = False
            if isinstance(instance.metadata, dict):
                is_canary = bool(instance.metadata.get("canary", False))
            if target_versions:
                if instance.version in target_versions or is_canary:
                    result.append(instance)
            elif is_canary:
                result.append(instance)
        return result

    def get_canary_config(
        self, service_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get the canary configuration for a service.

        Args:
            service_name: The logical service name.

        Returns:
            Configuration dictionary or None.
        """
        with self._lock:
            config = self._configs.get(service_name)
            if config is None:
                return None
            return {
                "percentage": config["percentage"],
                "target_versions": list(config["target_versions"]),
                "user_whitelist": list(config["user_whitelist"]),
                "region_whitelist": list(config["region_whitelist"]),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return canary router statistics.

        Returns:
            A dictionary with routing counts and configurations.
        """
        with self._lock:
            total = self._canary_count + self._normal_count
            return {
                "router": "CanaryRouter",
                "route_count": self._route_count,
                "canary_count": self._canary_count,
                "normal_count": self._normal_count,
                "canary_rate": (
                    self._canary_count / total if total else 0.0
                ),
                "configured_services": sorted(self._configs),
                "configs": {
                    k: {
                        "percentage": v["percentage"],
                        "target_versions": v["target_versions"],
                        "user_whitelist_count": len(v["user_whitelist"]),
                        "region_whitelist_count": len(v["region_whitelist"]),
                    }
                    for k, v in self._configs.items()
                },
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"CanaryRouter(services={len(self._configs)}, "
                f"routes={self._route_count})"
            )