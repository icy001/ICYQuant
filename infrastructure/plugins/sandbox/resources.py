"""Resource quota management.

Provides :class:`ResourceQuota` dataclass for defining resource
limits and :class:`ResourceQuotaManager` for enforcing those
limits per plugin, with usage tracking and violation detection.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..exceptions import PluginResourceLimitError

logger = logging.getLogger(__name__)


@dataclass
class ResourceQuota:
    """Resource quota configuration for a sandboxed plugin.

    Defines the maximum resource usage allowed per plugin.

    Attributes:
        memory_bytes: Maximum memory in bytes (default: 256 MB).
        cpu_percent: Maximum CPU usage as a percentage (default: 50%).
        max_threads: Maximum number of threads (default: 10).
        max_file_descriptors: Maximum open file descriptors (default: 100).
        max_network_connections: Maximum concurrent network connections
            (default: 50).
        max_disk_write_bytes: Maximum disk write bytes allowed
            (default: 100 MB).
    """

    memory_bytes: int = 256 * 1024 * 1024
    cpu_percent: float = 50.0
    max_threads: int = 10
    max_file_descriptors: int = 100
    max_network_connections: int = 50
    max_disk_write_bytes: int = 100 * 1024 * 1024

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the quota to a dictionary.

        Returns:
            A dictionary representation of all quota fields.
        """
        return {
            "memory_bytes": self.memory_bytes,
            "cpu_percent": self.cpu_percent,
            "max_threads": self.max_threads,
            "max_file_descriptors": self.max_file_descriptors,
            "max_network_connections": self.max_network_connections,
            "max_disk_write_bytes": self.max_disk_write_bytes,
        }


class ResourceQuotaManager:
    """Manages and enforces resource quotas for sandboxed plugins.

    Tracks resource usage per plugin and detects quota violations.

    Attributes:
        _quotas: Maps plugin_id to its ResourceQuota.
        _usage: Maps plugin_id to current resource usage counters.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._quotas: Dict[str, ResourceQuota] = {}
        self._usage: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()

    def set_quota(self, plugin_id: str, quota: ResourceQuota) -> None:
        """Set the resource quota for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            quota: The resource quota to apply.
        """
        with self._lock:
            self._quotas[plugin_id] = quota
            if plugin_id not in self._usage:
                self._usage[plugin_id] = self._empty_usage()
            logger.info(
                "Set quota for plugin %s: memory=%dMB, cpu=%.1f%%",
                plugin_id,
                quota.memory_bytes // (1024 * 1024),
                quota.cpu_percent,
            )

    def get_quota(self, plugin_id: str) -> ResourceQuota:
        """Get the resource quota for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            The plugin's ResourceQuota, or a default quota if none
            has been explicitly set.
        """
        with self._lock:
            return self._quotas.get(plugin_id, ResourceQuota())

    def check_quota(self, plugin_id: str) -> Dict[str, Any]:
        """Check the current resource usage for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A dictionary with ``quota``, ``usage``, and ``violations``
            listing any resources that exceed their limits.
        """
        with self._lock:
            quota = self.get_quota(plugin_id)
            usage = self._usage.get(plugin_id, self._empty_usage())
            violations: List[str] = []

            if usage.get("memory_used", 0) > quota.memory_bytes:
                violations.append("memory_bytes")
            if usage.get("cpu_percent", 0) > quota.cpu_percent:
                violations.append("cpu_percent")
            if usage.get("threads", 0) > quota.max_threads:
                violations.append("max_threads")
            if usage.get("file_descriptors", 0) > quota.max_file_descriptors:
                violations.append("max_file_descriptors")
            if usage.get("network_connections", 0) > quota.max_network_connections:
                violations.append("max_network_connections")
            if usage.get("disk_write_bytes", 0) > quota.max_disk_write_bytes:
                violations.append("max_disk_write_bytes")

            return {
                "plugin_id": plugin_id,
                "quota": quota.to_dict(),
                "usage": dict(usage),
                "violations": violations,
                "within_limits": len(violations) == 0,
            }

    def enforce_quota(self, plugin_id: str) -> None:
        """Enforce the resource quota, raising on violations.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginResourceLimitError: If any resource usage exceeds
                the configured limit.
        """
        result = self.check_quota(plugin_id)
        if not result["within_limits"]:
            violations = ", ".join(result["violations"])
            raise PluginResourceLimitError(
                f"Plugin '{plugin_id}' exceeded resource limits: {violations}"
            )

    def record_usage(
        self, plugin_id: str, resource_type: str, amount: float
    ) -> None:
        """Record resource usage for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            resource_type: One of ``memory_used``, ``cpu_percent``,
                ``threads``, ``file_descriptors``,
                ``network_connections``, or ``disk_write_bytes``.
            amount: The amount of resource used (additive).
        """
        with self._lock:
            if plugin_id not in self._usage:
                self._usage[plugin_id] = self._empty_usage()
            self._usage[plugin_id][resource_type] = (
                self._usage[plugin_id].get(resource_type, 0) + amount
            )

    def reset_usage(self, plugin_id: str) -> None:
        """Reset resource usage counters for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._usage[plugin_id] = self._empty_usage()

    @staticmethod
    def _empty_usage() -> Dict[str, float]:
        """Return a zeroed usage dictionary.

        Returns:
            A dictionary with all resource types set to 0.
        """
        return {
            "memory_used": 0.0,
            "cpu_percent": 0.0,
            "threads": 0.0,
            "file_descriptors": 0.0,
            "network_connections": 0.0,
            "disk_write_bytes": 0.0,
            "last_updated": time.time(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get quota manager statistics.

        Returns:
            A dictionary with ``total_quotas``, ``plugins`` (per-plugin
            summary with current usage), and ``violations`` count.
        """
        with self._lock:
            plugins = []
            total_violations = 0
            for pid in self._quotas:
                check = self.check_quota(pid)
                plugins.append({
                    "plugin_id": pid,
                    "quota": check["quota"],
                    "usage": check["usage"],
                    "violations": check["violations"],
                })
                total_violations += len(check["violations"])

            return {
                "total_quotas": len(self._quotas),
                "plugins": plugins,
                "total_violations": total_violations,
            }