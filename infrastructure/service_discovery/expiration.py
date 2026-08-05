"""Lease expiration pipeline for ICYQuant service discovery.

Provides ``LeaseExpiration`` implementing the expiration pipeline:
Heartbeat Timeout -> Lease Expired -> Registry Remove -> Publish Event.
Coordinates with ``AsyncLeaseManager`` and an optional registry/event
bus to gracefully remove stale instances.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .events import ServiceEvent, ServiceEventBus, ServiceEventType
from .lease import LeaseManager

logger = logging.getLogger(__name__)


class LeaseExpiration:
    """Lease expiration pipeline.

    Coordinates the four-stage expiration flow:
        1. Heartbeat Timeout detection
        2. Lease Expired marking
        3. Registry removal
        4. Event publication

    Args:
        lease_manager: The ``LeaseManager`` (or ``AsyncLeaseManager``)
            tracking leases.
        registry: Optional registry exposing ``deregister`` /
            ``remove`` semantics.
        event_bus: Optional ``ServiceEventBus`` for publishing events.
    """

    def __init__(
        self,
        lease_manager: LeaseManager,
        registry: Any = None,
        event_bus: Optional[ServiceEventBus] = None,
    ) -> None:
        self._lease_manager = lease_manager
        self._registry = registry
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._processed: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._check_count = 0
        self._expired_count = 0
        self._last_check_ts: float = 0.0

    # ── Public API ──

    async def check_expirations(self) -> Dict[str, int]:
        """Check all leases for expiration.

        Returns:
            A dictionary with ``total``, ``active``, and ``expired``
            counts.
        """
        with self._lock:
            self._check_count += 1
            self._last_check_ts = time.time()
        stats = self._lease_manager.get_stats()
        return {
            "total": stats.get("total_leases", 0),
            "active": stats.get("active_leases", 0),
            "expired": stats.get("expired_leases", 0),
        }

    async def expire_lease(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Expire a single lease and run the full pipeline.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the expiration result.
        """
        start = time.monotonic()
        result: Dict[str, Any] = {
            "service_name": service_name,
            "instance_id": instance_id,
            "expired": False,
            "registry_removed": False,
            "event_published": False,
            "timestamp": datetime.utcnow().isoformat(),
        }
        # Stage 1 & 2: expire the lease.
        lease = self._lease_manager.get_lease(service_name, instance_id)
        if lease is None:
            result["message"] = "No lease found."
            return result
        await self._expire_lease_async(service_name, instance_id)
        result["expired"] = True
        with self._lock:
            self._expired_count += 1

        # Stage 3: registry removal.
        result["registry_removed"] = await self._remove_from_registry(
            service_name, instance_id
        )

        # Stage 4: publish event.
        result["event_published"] = await self._publish_expired_event(
            service_name, instance_id, lease.to_dict()
        )
        result["latency_ms"] = (time.monotonic() - start) * 1000.0
        self._record_processed(result)
        return result

    async def process_expired(self) -> List[Dict[str, Any]]:
        """Process all expired leases through the pipeline.

        Returns:
            A list of expiration result dictionaries.
        """
        expired_leases = self._lease_manager.get_expired_leases()
        if not expired_leases:
            return []
        results: List[Dict[str, Any]] = []
        for lease in expired_leases:
            try:
                result = await self.expire_lease(
                    lease.service_name, lease.instance_id
                )
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "Failed to expire lease '%s/%s': %s",
                    lease.service_name,
                    lease.instance_id,
                    exc,
                )
                results.append(
                    {
                        "service_name": lease.service_name,
                        "instance_id": lease.instance_id,
                        "expired": False,
                        "error": str(exc),
                    }
                )
        logger.info(
            "Processed %d expired lease(s).", len(results)
        )
        return results

    def get_expiration_stats(self) -> Dict[str, Any]:
        """Return statistics specific to the expiration pipeline."""
        with self._lock:
            return {
                "check_count": self._check_count,
                "expired_count": self._expired_count,
                "last_check_ts": self._last_check_ts,
                "history_size": len(self._processed),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the expiration pipeline."""
        stats = self.get_expiration_stats()
        stats["registry_attached"] = self._registry is not None
        stats["event_bus_attached"] = self._event_bus is not None
        return stats

    # ── Internal helpers ──

    async def _expire_lease_async(
        self, service_name: str, instance_id: str
    ) -> None:
        """Expire the lease, preferring async path when available."""
        expire_method = getattr(self._lease_manager, "expire_lease", None)
        if expire_method is None:
            return
        result = expire_method(service_name, instance_id)
        if asyncio.iscoroutine(result):
            await result

    async def _remove_from_registry(
        self, service_name: str, instance_id: str
    ) -> bool:
        """Remove the instance from the registry, if attached."""
        if self._registry is None:
            return False
        for method_name in ("deregister", "remove", "delete"):
            method = getattr(self._registry, method_name, None)
            if callable(method):
                try:
                    result = method(service_name, instance_id)
                    if asyncio.iscoroutine(result):
                        await result
                    return True
                except Exception as exc:
                    logger.warning(
                        "Registry %s failed for '%s/%s': %s",
                        method_name,
                        service_name,
                        instance_id,
                        exc,
                    )
                    return False
        return False

    async def _publish_expired_event(
        self,
        service_name: str,
        instance_id: str,
        lease_data: Dict[str, Any],
    ) -> bool:
        """Publish a lease-expired event, if an event bus is attached."""
        if self._event_bus is None:
            return False
        try:
            await self._event_bus.publish(
                ServiceEvent(
                    event_type=ServiceEventType.LEASE_EXPIRED,
                    service_name=service_name,
                    instance_id=instance_id,
                    data={
                        "action": "expired",
                        "lease": lease_data,
                    },
                )
            )
            return True
        except Exception as exc:
            logger.warning(
                "Failed to publish lease-expired event for '%s/%s': %s",
                service_name,
                instance_id,
                exc,
            )
            return False

    def _record_processed(self, result: Dict[str, Any]) -> None:
        with self._lock:
            self._processed.append(dict(result))
            if len(self._processed) > self._max_history:
                excess = len(self._processed) - self._max_history
                del self._processed[:excess]

    def __repr__(self) -> str:
        return (
            f"LeaseExpiration(checks={self._check_count}, "
            f"expired={self._expired_count})"
        )
