"""Async lease manager for ICYQuant service discovery.

Provides ``AsyncLeaseManager`` extending the synchronous
``LeaseManager`` with coroutine-based lease lifecycle operations
(create, renew, expire, check, cleanup) suitable for asyncio-based
service discovery workflows. Integrates with the event bus for lease
lifecycle notifications.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .events import ServiceEvent, ServiceEventBus, ServiceEventType
from .exceptions import LeaseRenewalError
from .lease import LeaseManager, ServiceLease

logger = logging.getLogger(__name__)


class AsyncLeaseManager(LeaseManager):
    """Async-capable lease manager.

    Wraps the synchronous ``LeaseManager`` operations in coroutines
    and publishes lease lifecycle events through an optional
    ``ServiceEventBus``.

    Args:
        event_bus: Optional ``ServiceEventBus`` for publishing lease events.
    """

    def __init__(self, event_bus: Optional[ServiceEventBus] = None) -> None:
        super().__init__()
        self._event_bus = event_bus

    # ── Async lease lifecycle ──

    async def create_lease(
        self,
        service_name: str,
        instance_id: str,
        ttl: int = 20,
        renew_interval: int = 5,
    ) -> ServiceLease:
        """Asynchronously create a lease for an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            ttl: Time-to-live in seconds.
            renew_interval: Suggested renewal interval in seconds.

        Returns:
            The newly created ``ServiceLease``.
        """
        loop = asyncio.get_event_loop()
        lease = await loop.run_in_executor(
            None,
            lambda: self._create_sync(
                service_name, instance_id, ttl, renew_interval
            ),
        )
        if self._event_bus is not None:
            await self._event_bus.publish(
                ServiceEvent(
                    event_type=ServiceEventType.LEASE_RENEWED,
                    service_name=service_name,
                    instance_id=instance_id,
                    data={
                        "action": "created",
                        "ttl": lease.ttl,
                        "renew_interval": lease.renew_interval,
                    },
                )
            )
        return lease

    def _create_sync(
        self,
        service_name: str,
        instance_id: str,
        ttl: int,
        renew_interval: int,
    ) -> ServiceLease:
        """Synchronous lease creation honoring a renew interval."""
        with self._lock:
            lease = ServiceLease(
                service_name=service_name,
                instance_id=instance_id,
                ttl=ttl,
                renew_interval=renew_interval,
            )
            key = self._make_key(service_name, instance_id)
            self._leases[key] = lease
            self._created_count += 1
        logger.info(
            "Created lease for '%s/%s' (ttl=%ds, renew=%ds).",
            service_name,
            instance_id,
            ttl,
            renew_interval,
        )
        return lease

    async def renew_lease(
        self, service_name: str, instance_id: str
    ) -> Optional[ServiceLease]:
        """Asynchronously renew an existing lease.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            The renewed ``ServiceLease`` or None if no lease exists.
        """
        loop = asyncio.get_event_loop()
        try:
            lease = await loop.run_in_executor(
                None, super().renew_lease, service_name, instance_id
            )
        except LeaseRenewalError as exc:
            if self._event_bus is not None:
                await self._event_bus.publish(
                    ServiceEvent(
                        event_type=ServiceEventType.LEASE_EXPIRED,
                        service_name=service_name,
                        instance_id=instance_id,
                        data={"action": "renew_failed", "error": str(exc)},
                    )
                )
            raise
        if lease is not None and self._event_bus is not None:
            await self._event_bus.publish(
                ServiceEvent(
                    event_type=ServiceEventType.LEASE_RENEWED,
                    service_name=service_name,
                    instance_id=instance_id,
                    data={"action": "renewed", "ttl": lease.ttl},
                )
            )
        return lease

    async def expire_lease(
        self, service_name: str, instance_id: str
    ) -> Dict[str, Any]:
        """Asynchronously expire and remove a lease.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            A dictionary describing the expiry result.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, super().expire_lease, service_name, instance_id
        )
        if self._event_bus is not None:
            await self._event_bus.publish(
                ServiceEvent(
                    event_type=ServiceEventType.LEASE_EXPIRED,
                    service_name=service_name,
                    instance_id=instance_id,
                    data={"action": "expired"},
                )
            )
        return {
            "service_name": service_name,
            "instance_id": instance_id,
            "expired": True,
            "timestamp": time.time(),
        }

    async def check_leases(self) -> Dict[str, int]:
        """Check all leases and return summary counts.

        Returns:
            A dictionary with ``total``, ``active``, and ``expired``
            counts.
        """
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(None, self.get_stats)
        return {
            "total": stats.get("total_leases", 0),
            "active": stats.get("active_leases", 0),
            "expired": stats.get("expired_leases", 0),
        }

    async def cleanup_expired(self) -> int:
        """Asynchronously remove all expired leases.

        Returns:
            The number of leases cleaned up.
        """
        expired = self.get_expired_leases()
        loop = asyncio.get_event_loop()
        cleaned = await loop.run_in_executor(None, super().cleanup_expired)
        if cleaned and self._event_bus is not None:
            for lease in expired:
                await self._event_bus.publish(
                    ServiceEvent(
                        event_type=ServiceEventType.LEASE_EXPIRED,
                        service_name=lease.service_name,
                        instance_id=lease.instance_id,
                        data={"action": "cleanup"},
                    )
                )
        return cleaned

    # ── Synchronous accessors (inherited) ──

    def get_lease(self, service_name: str, instance_id: str) -> Optional[ServiceLease]:
        """Return the lease for an instance, if present."""
        return super().get_lease(service_name, instance_id)

    def get_all_leases(self) -> List[Dict[str, Any]]:
        """Return all leases as a list of dictionaries."""
        with self._lock:
            return [lease.to_dict() for lease in self._leases.values()]

    def get_expired_leases(self) -> List[ServiceLease]:
        """Return all currently expired leases."""
        return super().get_expired_leases()

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the async lease manager."""
        stats = super().get_stats()
        stats["event_bus_attached"] = self._event_bus is not None
        return stats

    def __repr__(self) -> str:
        return f"AsyncLeaseManager(leases={len(self._leases)})"
