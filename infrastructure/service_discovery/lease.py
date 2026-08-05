"""Service lease management.

Provides ``ServiceLease`` and ``LeaseManager`` for tracking
time-to-live leases on service instances, enabling automatic
deregistration of stale instances. All operations are thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import LeaseExpiredError, LeaseRenewalError

logger = logging.getLogger(__name__)


class ServiceLease:
    """A time-limited lease on a service instance.

    Args:
        service_name: The logical service name.
        instance_id: The instance identifier.
        ttl: Time-to-live in seconds.
        renew_interval: Suggested renewal interval in seconds.
    """

    __slots__ = (
        "service_name",
        "instance_id",
        "ttl",
        "renew_interval",
        "created_at",
        "last_renewed",
        "expired",
        "_lock",
    )

    def __init__(
        self,
        service_name: str,
        instance_id: str,
        ttl: int = 30,
        renew_interval: int = 10,
    ) -> None:
        self.service_name = service_name
        self.instance_id = instance_id
        self.ttl = int(ttl) if ttl and ttl > 0 else 30
        self.renew_interval = int(renew_interval) if renew_interval and renew_interval > 0 else 10
        self.created_at = time.time()
        self.last_renewed = self.created_at
        self.expired = False
        self._lock = threading.RLock()

    def is_expired(self) -> bool:
        """Return whether the lease has expired.

        Returns:
            True if the lease was explicitly expired or its TTL has
            elapsed since the last renewal.
        """
        with self._lock:
            if self.expired:
                return True
            return (time.time() - self.last_renewed) > self.ttl

    def renew(self) -> None:
        """Renew the lease, extending its TTL.

        Raises:
            LeaseExpiredError: If the lease has already expired.
        """
        with self._lock:
            if self.expired:
                raise LeaseExpiredError(
                    f"Cannot renew expired lease for '{self.service_name}/{self.instance_id}'."
                )
            self.last_renewed = time.time()
            logger.debug(
                "Renewed lease for '%s/%s' (ttl=%ds).",
                self.service_name,
                self.instance_id,
                self.ttl,
            )

    def expire(self) -> None:
        """Mark the lease as explicitly expired."""
        with self._lock:
            self.expired = True
            logger.info(
                "Expired lease for '%s/%s'.",
                self.service_name,
                self.instance_id,
            )

    def get_remaining_ttl(self) -> int:
        """Return the remaining TTL in seconds.

        Returns:
            Remaining seconds until expiry. Returns 0 if expired.
        """
        with self._lock:
            if self.expired:
                return 0
            elapsed = time.time() - self.last_renewed
            remaining = int(self.ttl - elapsed)
            return max(remaining, 0)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the lease to a dictionary."""
        with self._lock:
            return {
                "service_name": self.service_name,
                "instance_id": self.instance_id,
                "ttl": self.ttl,
                "renew_interval": self.renew_interval,
                "created_at": datetime.utcfromtimestamp(self.created_at).isoformat()
                if self.created_at
                else None,
                "last_renewed": datetime.utcfromtimestamp(self.last_renewed).isoformat()
                if self.last_renewed
                else None,
                "expired": self.expired,
                "remaining_ttl": self.get_remaining_ttl(),
            }

    def __repr__(self) -> str:
        return (
            f"ServiceLease(service_name={self.service_name!r}, "
            f"instance_id={self.instance_id!r}, ttl={self.ttl}, "
            f"expired={self.expired})"
        )


class LeaseManager:
    """Manages service leases with TTL-based expiry.

    Tracks leases keyed by (service_name, instance_id) and supports
    renewal, expiry, and periodic cleanup. Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leases: Dict[str, ServiceLease] = {}
        self._created_count = 0
        self._renewed_count = 0
        self._expired_count = 0

    def _make_key(self, service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def create_lease(
        self,
        service_name: str,
        instance_id: str,
        ttl: int = 30,
    ) -> ServiceLease:
        """Create a new lease for an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
            ttl: Time-to-live in seconds.

        Returns:
            The newly created ``ServiceLease``.
        """
        key = self._make_key(service_name, instance_id)
        renew_interval = max(int(ttl) // 3, 5) if ttl else 10
        lease = ServiceLease(
            service_name=service_name,
            instance_id=instance_id,
            ttl=ttl,
            renew_interval=renew_interval,
        )
        with self._lock:
            self._leases[key] = lease
            self._created_count += 1
        logger.info(
            "Created lease for '%s/%s' (ttl=%ds).",
            service_name,
            instance_id,
            ttl,
        )
        return lease

    def renew_lease(self, service_name: str, instance_id: str) -> Optional[ServiceLease]:
        """Renew an existing lease.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            The renewed ``ServiceLease`` or None if no lease exists.

        Raises:
            LeaseRenewalError: If the lease cannot be renewed.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            lease = self._leases.get(key)
            if lease is None:
                return None
            try:
                lease.renew()
                self._renewed_count += 1
                return lease
            except LeaseExpiredError as e:
                self._leases.pop(key, None)
                self._expired_count += 1
                raise LeaseRenewalError(str(e)) from e

    def expire_lease(self, service_name: str, instance_id: str) -> None:
        """Explicitly expire and remove a lease.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            lease = self._leases.pop(key, None)
            if lease is not None:
                lease.expire()
                self._expired_count += 1

    def get_lease(self, service_name: str, instance_id: str) -> Optional[ServiceLease]:
        """Return the lease for an instance, if present.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            The ``ServiceLease`` or None.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            return self._leases.get(key)

    def get_expired_leases(self) -> List[ServiceLease]:
        """Return all currently expired leases.

        Returns:
            A list of expired ``ServiceLease`` objects.
        """
        with self._lock:
            return [lease for lease in self._leases.values() if lease.is_expired()]

    def cleanup_expired(self) -> int:
        """Remove all expired leases.

        Returns:
            The number of leases cleaned up.
        """
        cleaned = 0
        with self._lock:
            expired_keys: List[str] = []
            for key, lease in self._leases.items():
                if lease.is_expired():
                    expired_keys.append(key)
            for key in expired_keys:
                lease = self._leases.pop(key, None)
                if lease is not None:
                    lease.expired = True
                    cleaned += 1
                    self._expired_count += 1
            if cleaned:
                logger.info("Cleaned up %d expired lease(s).", cleaned)
        return cleaned

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the lease manager.

        Returns:
            A dictionary with lease counts and renewal/expiry totals.
        """
        with self._lock:
            total = len(self._leases)
            expired = sum(1 for lease in self._leases.values() if lease.is_expired())
            return {
                "total_leases": total,
                "active_leases": total - expired,
                "expired_leases": expired,
                "created_total": self._created_count,
                "renewed_total": self._renewed_count,
                "expired_total": self._expired_count,
            }

    def __repr__(self) -> str:
        return f"LeaseManager(leases={len(self._leases)})"
