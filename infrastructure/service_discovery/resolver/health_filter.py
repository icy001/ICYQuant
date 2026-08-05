"""Health-based filtering for service discovery.

Provides ``HealthFilter`` which removes unhealthy, lease-expired,
restarting, and quarantined instances from the candidate pool.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class HealthFilter:
    """Filters instances based on health status.

    Removes instances that are unhealthy, have expired leases,
    are restarting, or have been quarantined.

    Usage::

        hf = HealthFilter()
        filtered = hf.filter(instances, context)
    """

    def __init__(
        self,
        health_monitor: Any = None,
        quarantine_manager: Any = None,
    ) -> None:
        self._lock = threading.RLock()
        self._health_monitor = health_monitor
        self._quarantine_manager = quarantine_manager
        self._health_callback: Optional[Callable] = None
        self._filter_count = 0
        self._removed_count = 0
        self._removed_reasons: Dict[str, int] = {
            "unhealthy": 0,
            "lease_expired": 0,
            "restarting": 0,
            "quarantined": 0,
        }

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Remove unhealthy and unavailable instances.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of healthy instances.
        """
        if not instances:
            return []

        with self._lock:
            self._filter_count += 1

        result: List[ServiceInstance] = []
        removed = 0

        for instance in instances:
            if self._is_unhealthy(instance):
                removed += 1
                continue
            if self._is_lease_expired(instance):
                with self._lock:
                    self._removed_reasons["lease_expired"] += 1
                removed += 1
                continue
            if self._is_restarting(instance):
                with self._lock:
                    self._removed_reasons["restarting"] += 1
                removed += 1
                continue
            if self._is_quarantined(instance):
                with self._lock:
                    self._removed_reasons["quarantined"] += 1
                removed += 1
                continue
            result.append(instance)

        with self._lock:
            self._removed_count += removed

        if removed > 0:
            logger.debug(
                "Health filter removed %d of %d instances.",
                removed,
                len(instances),
            )

        return result

    def is_healthy(self, instance: ServiceInstance) -> bool:
        """Check whether a single instance is healthy.

        Args:
            instance: The instance to check.

        Returns:
            True if the instance is healthy and available.
        """
        if instance is None:
            return False
        if self._is_unhealthy(instance):
            return False
        if self._is_lease_expired(instance):
            return False
        if self._is_restarting(instance):
            return False
        if self._is_quarantined(instance):
            return False
        return True

    def set_health_callback(self, callback: Callable) -> None:
        """Set a callback for health status changes.

        Args:
            callback: A callable invoked with
                ``(instance_id, healthy: bool)``.
        """
        if not callable(callback):
            raise TypeError("callback must be callable.")
        with self._lock:
            self._health_callback = callback

    def _is_unhealthy(self, instance: ServiceInstance) -> bool:
        if not instance.healthy:
            with self._lock:
                self._removed_reasons["unhealthy"] += 1
            return True
        if not instance.is_healthy():
            with self._lock:
                self._removed_reasons["unhealthy"] += 1
            return True
        return False

    @staticmethod
    def _is_lease_expired(instance: ServiceInstance) -> bool:
        if not isinstance(instance.metadata, dict):
            return False
        lease_expired = bool(instance.metadata.get("lease_expired", False))
        return lease_expired

    @staticmethod
    def _is_restarting(instance: ServiceInstance) -> bool:
        if not isinstance(instance.metadata, dict):
            return False
        restarting = bool(instance.metadata.get("restarting", False))
        return restarting

    def _is_quarantined(self, instance: ServiceInstance) -> bool:
        if self._quarantine_manager is not None:
            try:
                if hasattr(self._quarantine_manager, "is_quarantined"):
                    return bool(
                        self._quarantine_manager.is_quarantined(
                            instance.instance_id
                        )
                    )
            except Exception:
                logger.warning(
                    "Error checking quarantine for '%s'.",
                    instance.instance_id,
                )
        if not isinstance(instance.metadata, dict):
            return False
        return bool(instance.metadata.get("quarantined", False))

    def get_stats(self) -> Dict[str, Any]:
        """Return health filter statistics.

        Returns:
            A dictionary with filter counts and removal reasons.
        """
        with self._lock:
            return {
                "filter": "HealthFilter",
                "filter_count": self._filter_count,
                "removed_count": self._removed_count,
                "removed_reasons": dict(self._removed_reasons),
                "has_health_monitor": self._health_monitor is not None,
                "has_quarantine_manager": self._quarantine_manager
                is not None,
                "has_callback": self._health_callback is not None,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HealthFilter(filtered={self._filter_count}, "
                f"removed={self._removed_count})"
            )