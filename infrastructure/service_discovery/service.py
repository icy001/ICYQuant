"""Service aggregate.

Provides the ``Service`` aggregate that groups service instances
belonging to the same logical service, with thread-safe instance
management and statistics.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .instance import ServiceInstance
from .models import ServiceStatus

logger = logging.getLogger(__name__)


class Service:
    """An aggregate of instances for a logical service.

    Args:
        name: Logical name of the service.
        namespace: Namespace the service belongs to.
    """

    def __init__(self, name: str, namespace: str = "default") -> None:
        self.name = name
        self.namespace = namespace or "default"
        self._lock = threading.RLock()
        self._instances: Dict[str, ServiceInstance] = {}

    @property
    def lock(self) -> threading.RLock:
        """Expose the internal lock for coordinated multi-step operations."""
        return self._lock

    def add_instance(self, instance: ServiceInstance) -> None:
        """Add or replace an instance in this service.

        Args:
            instance: The ``ServiceInstance`` to add.
        """
        if instance is None:
            return
        with self._lock:
            self._instances[instance.instance_id] = instance
            logger.debug(
                "Added instance '%s' to service '%s/%s'.",
                instance.instance_id,
                self.namespace,
                self.name,
            )

    def remove_instance(self, instance_id: str) -> None:
        """Remove an instance by identifier.

        Args:
            instance_id: The identifier of the instance to remove.
        """
        with self._lock:
            self._instances.pop(instance_id, None)

    def get_instances(self, healthy_only: bool = True) -> List[ServiceInstance]:
        """Return the instances of this service.

        Args:
            healthy_only: When True, only return healthy instances.

        Returns:
            A list of ``ServiceInstance`` objects.
        """
        with self._lock:
            instances = list(self._instances.values())
        if healthy_only:
            return [i for i in instances if i.is_healthy()]
        return instances

    def get_instance(self, instance_id: str) -> Optional[ServiceInstance]:
        """Return a single instance by identifier.

        Args:
            instance_id: The instance identifier to look up.

        Returns:
            The matching ``ServiceInstance`` or None.
        """
        with self._lock:
            return self._instances.get(instance_id)

    def get_versions(self) -> List[str]:
        """Return all registered versions of this service.

        Returns:
            A sorted list of unique version strings.
        """
        with self._lock:
            versions = {i.version for i in self._instances.values()}
        return sorted(versions)

    def get_instance_count(self) -> int:
        """Return the total number of registered instances."""
        with self._lock:
            return len(self._instances)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the service to a dictionary."""
        with self._lock:
            instances = [i.to_dict() for i in self._instances.values()]
        return {
            "name": self.name,
            "namespace": self.namespace,
            "instance_count": len(instances),
            "instances": instances,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for this service.

        Returns:
            A dictionary with instance counts broken down by health
            and status.
        """
        with self._lock:
            instances = list(self._instances.values())
        total = len(instances)
        healthy = sum(1 for i in instances if i.is_healthy())
        status_counts: Dict[str, int] = {}
        for instance in instances:
            key = instance.status.value
            status_counts[key] = status_counts.get(key, 0) + 1
        return {
            "name": self.name,
            "namespace": self.namespace,
            "total_instances": total,
            "healthy_instances": healthy,
            "unhealthy_instances": total - healthy,
            "versions": sorted({i.version for i in instances}),
            "by_status": status_counts,
        }

    def __repr__(self) -> str:
        return (
            f"Service(name={self.name!r}, namespace={self.namespace!r}, "
            f"instances={self.get_instance_count()})"
        )
