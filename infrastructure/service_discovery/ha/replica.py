"""Replica manager for ICYQuant service discovery HA.

Provides ``ReplicaManager`` for managing service replicas with
priority-based, health-based, and zone-aware selection strategies.

Strategies: priority, health-based, zone-aware
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class ReplicaManager:
    """Manages service replicas and their selection.

    Maintains a per-service replica list with priorities and
    supports multiple selection strategies for determining
    the best replica to use.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._replicas: Dict[str, List[Dict[str, Any]]] = {}
        self._add_count = 0
        self._remove_count = 0
        self._promote_count = 0
        self._select_count = 0

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Public API ──

    def add_replica(
        self,
        service_name: str,
        instance: ServiceInstance,
        priority: int = 0,
    ) -> None:
        """Add a replica to a service.

        Args:
            service_name: The logical service name.
            instance: The ``ServiceInstance`` to add as a replica.
            priority: Replica priority (lower is higher priority).
        """
        if instance is None:
            raise ValueError("instance cannot be None.")

        with self._lock:
            replicas = self._replicas.setdefault(service_name, [])
            for rep in replicas:
                if rep["instance"].instance_id == instance.instance_id:
                    logger.debug(
                        "Replica '%s/%s' already exists; updating priority.",
                        service_name,
                        instance.instance_id,
                    )
                    rep["priority"] = priority
                    rep["updated_at"] = time.time()
                    return

            replicas.append(
                {
                    "instance": instance,
                    "priority": priority,
                    "added_at": time.time(),
                    "updated_at": time.time(),
                }
            )
            self._add_count += 1

        logger.info(
            "Added replica '%s/%s' with priority %d.",
            service_name,
            instance.instance_id,
            priority,
        )

    def remove_replica(
        self, service_name: str, instance_id: str
    ) -> None:
        """Remove a replica from a service.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier to remove.
        """
        with self._lock:
            replicas = self._replicas.get(service_name)
            if replicas is None:
                logger.debug(
                    "No replicas for '%s'; nothing to remove.",
                    service_name,
                )
                return
            original_len = len(replicas)
            self._replicas[service_name] = [
                r
                for r in replicas
                if r["instance"].instance_id != instance_id
            ]
            removed = original_len - len(self._replicas[service_name])
            self._remove_count += removed

        if removed > 0:
            logger.info(
                "Removed replica '%s/%s'.", service_name, instance_id
            )
        else:
            logger.debug(
                "Replica '%s/%s' not found.", service_name, instance_id
            )

    def select_replica(
        self,
        service_name: str,
        strategy: str = "priority",
    ) -> Optional[ServiceInstance]:
        """Select the best replica using the given strategy.

        Args:
            service_name: The logical service name.
            strategy: Selection strategy (priority, health-based,
                zone-aware).

        Returns:
            The selected ``ServiceInstance`` or None.
        """
        with self._lock:
            replicas = self._replicas.get(service_name)
            if not replicas:
                return None
            self._select_count += 1

        strategy = (strategy or "priority").lower()

        if strategy == "priority":
            return self._select_by_priority(replicas)
        elif strategy == "health-based":
            return self._select_by_health(replicas)
        elif strategy == "zone-aware":
            return self._select_by_zone(replicas)
        else:
            logger.warning(
                "Unknown strategy '%s'; falling back to priority.",
                strategy,
            )
            return self._select_by_priority(replicas)

    def promote(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Promote a replica to primary.

        Sets the specified instance to the highest priority
        (lowest numeric value, i.e. 0).

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier to promote.

        Returns:
            A dictionary describing the promotion result.
        """
        with self._lock:
            replicas = self._replicas.get(service_name)
            if replicas is None:
                return {
                    "promoted": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "reason": "no_replicas",
                    "timestamp": self._now_iso(),
                }

            target = None
            for rep in replicas:
                if rep["instance"].instance_id == instance_id:
                    target = rep
                    break

            if target is None:
                return {
                    "promoted": False,
                    "service_name": service_name,
                    "instance_id": instance_id,
                    "reason": "not_found",
                    "timestamp": self._now_iso(),
                }

            max_priority = max(r["priority"] for r in replicas)
            old_priority = target["priority"]
            target["priority"] = 0
            target["updated_at"] = time.time()

            for rep in replicas:
                if rep["instance"].instance_id != instance_id:
                    if rep["priority"] <= old_priority:
                        rep["priority"] += 1
                    rep["updated_at"] = time.time()

            self._promote_count += 1

        logger.info(
            "Promoted '%s/%s' to primary.", service_name, instance_id
        )
        return {
            "promoted": True,
            "service_name": service_name,
            "instance_id": instance_id,
            "new_priority": 0,
            "timestamp": self._now_iso(),
        }

    def get_replicas(self, service_name: str) -> List[ServiceInstance]:
        """Return all replicas for a service.

        Args:
            service_name: The logical service name.

        Returns:
            A list of ``ServiceInstance`` replicas.
        """
        with self._lock:
            replicas = self._replicas.get(service_name, [])
            return [r["instance"] for r in replicas]

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the replica manager."""
        with self._lock:
            total_replicas = sum(
                len(reps) for reps in self._replicas.values()
            )
            return {
                "services_with_replicas": len(self._replicas),
                "total_replicas": total_replicas,
                "add_count": self._add_count,
                "remove_count": self._remove_count,
                "promote_count": self._promote_count,
                "select_count": self._select_count,
            }

    # ── Selection strategies ──

    @staticmethod
    def _select_by_priority(
        replicas: List[Dict[str, Any]],
    ) -> Optional[ServiceInstance]:
        sorted_replicas = sorted(replicas, key=lambda r: r["priority"])
        for rep in sorted_replicas:
            instance = rep["instance"]
            if instance.is_healthy():
                return instance
        return sorted_replicas[0]["instance"] if sorted_replicas else None

    @staticmethod
    def _select_by_health(
        replicas: List[Dict[str, Any]],
    ) -> Optional[ServiceInstance]:
        healthy = [
            r for r in replicas if r["instance"].is_healthy()
        ]
        if not healthy:
            return replicas[0]["instance"] if replicas else None
        sorted_healthy = sorted(
            healthy,
            key=lambda r: (
                r["instance"].weight,
                -r["priority"],
            ),
            reverse=True,
        )
        return sorted_healthy[0]["instance"]

    @staticmethod
    def _select_by_zone(
        replicas: List[Dict[str, Any]],
    ) -> Optional[ServiceInstance]:
        zones: Dict[str, List[Dict[str, Any]]] = {}
        for rep in replicas:
            instance = rep["instance"]
            zone = ""
            if isinstance(instance.metadata, dict):
                zone = str(instance.metadata.get("zone", ""))
            zones.setdefault(zone, []).append(rep)

        for zone_replicas in zones.values():
            healthy = [
                r for r in zone_replicas if r["instance"].is_healthy()
            ]
            if healthy:
                sorted_healthy = sorted(
                    healthy, key=lambda r: r["priority"]
                )
                return sorted_healthy[0]["instance"]

        sorted_replicas = sorted(replicas, key=lambda r: r["priority"])
        return sorted_replicas[0]["instance"] if sorted_replicas else None

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ReplicaManager(services={len(self._replicas)}, "
                f"adds={self._add_count})"
            )