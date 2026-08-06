"""Lease Manager — time-bounded leases for cluster coordination.

The :class:`LeaseManager` provides time-bounded, renewable leases that
are essential for leader election, distributed locking, and exclusive
resource access in the scheduler cluster.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LeaseStatus:
    """Lease lifecycle status."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    RENEWING = "renewing"


class LeaseManager:
    """Manages time-bounded leases for cluster coordination.

    Leases are used for:
    - Leadership tenure (leader must hold a valid lease)
    - Distributed lock duration
    - Job ownership window

    Usage::

        mgr = LeaseManager()
        lease_id = await mgr.acquire("scheduler-1", "leadership", ttl=15.0)
        # ... do work ...
        await mgr.renew(lease_id)
        await mgr.release(lease_id)
    """

    def __init__(self, *, default_ttl_seconds: float = 30.0) -> None:
        self._default_ttl = default_ttl_seconds
        self._leases: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def default_ttl_seconds(self) -> float:
        return self._default_ttl

    @property
    def active_lease_count(self) -> int:
        with self._lock:
            return sum(1 for l in self._leases.values()
                       if l["status"] == LeaseStatus.ACTIVE)

    # ------------------------------------------------------------------
    # Lease Operations
    # ------------------------------------------------------------------

    async def acquire(
        self,
        holder_id: str,
        resource: str,
        *,
        ttl: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Acquire a lease on a resource.

        Args:
            holder_id: ID of the node/entity requesting the lease.
            resource: The resource to lease (e.g., "leadership", "job:j1").
            ttl: Time-to-live in seconds. Uses default if not specified.
            metadata: Optional metadata to attach.

        Returns:
            Lease ID if acquired, None if the resource is already leased.
        """
        ttl = ttl or self._default_ttl

        with self._lock:
            # Check if resource already has an active lease
            for existing in self._leases.values():
                if existing["resource"] == resource and existing["status"] == LeaseStatus.ACTIVE:
                    if not self._is_expired(existing):
                        logger.debug("Resource %s already leased by %s", resource, existing["holder_id"])
                        return None

            lease_id = str(uuid.uuid4())[:12]
            now = datetime.now(timezone.utc)
            lease = {
                "lease_id": lease_id,
                "holder_id": holder_id,
                "resource": resource,
                "ttl": ttl,
                "status": LeaseStatus.ACTIVE,
                "acquired_at": now,
                "expires_at": datetime.fromtimestamp(now.timestamp() + ttl, tz=timezone.utc),
                "renewals": 0,
                "metadata": metadata or {},
            }
            self._leases[lease_id] = lease

        logger.debug("Lease acquired [id=%s, holder=%s, resource=%s, ttl=%.1fs]",
                      lease_id, holder_id, resource, ttl)
        return lease_id

    async def renew(self, lease_id: str) -> bool:
        """Renew an existing lease, extending its TTL.

        Returns:
            True if renewed, False if lease not found or expired.
        """
        with self._lock:
            lease = self._leases.get(lease_id)
            if not lease:
                return False
            if self._is_expired(lease):
                lease["status"] = LeaseStatus.EXPIRED
                return False

            lease["expires_at"] = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + lease["ttl"],
                tz=timezone.utc,
            )
            lease["renewals"] += 1
            lease["status"] = LeaseStatus.ACTIVE
        return True

    async def release(self, lease_id: str) -> bool:
        """Release a lease, making the resource available again.

        Returns:
            True if released, False if not found.
        """
        with self._lock:
            lease = self._leases.get(lease_id)
            if not lease:
                return False
            lease["status"] = LeaseStatus.REVOKED
            del self._leases[lease_id]
        logger.debug("Lease released [id=%s]", lease_id)
        return True

    async def revoke(self, lease_id: str) -> bool:
        """Forcefully revoke a lease (e.g., during failover)."""
        with self._lock:
            lease = self._leases.get(lease_id)
            if not lease:
                return False
            lease["status"] = LeaseStatus.REVOKED
        logger.warning("Lease revoked [id=%s]", lease_id)
        return True

    def is_valid(self, lease_id: str) -> bool:
        """Check if a lease is still valid (active and not expired)."""
        with self._lock:
            lease = self._leases.get(lease_id)
            if not lease or lease["status"] != LeaseStatus.ACTIVE:
                return False
            return not self._is_expired(lease)

    def get_lease(self, lease_id: str) -> Optional[Dict[str, Any]]:
        """Get lease details."""
        with self._lock:
            return dict(self._leases.get(lease_id, {}))

    def get_leases_by_holder(self, holder_id: str) -> list:
        """Get all leases held by a specific holder."""
        with self._lock:
            return [dict(l) for l in self._leases.values() if l["holder_id"] == holder_id]

    def cleanup_expired(self) -> int:
        """Remove expired leases. Returns count of removed leases."""
        removed = 0
        with self._lock:
            expired_ids = [
                lid for lid, l in self._leases.items()
                if self._is_expired(l) or l["status"] == LeaseStatus.REVOKED
            ]
            for lid in expired_ids:
                del self._leases[lid]
                removed += 1
        if removed:
            logger.debug("Cleaned up %d expired leases", removed)
        return removed

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _is_expired(lease: Dict[str, Any]) -> bool:
        return datetime.now(timezone.utc) > lease["expires_at"]

    def get_lease_info(self) -> Dict[str, Any]:
        """Return lease manager status summary."""
        return {
            "active_leases": self.active_lease_count,
            "total_leases": len(self._leases),
            "default_ttl_seconds": self._default_ttl,
        }
