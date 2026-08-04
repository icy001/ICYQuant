"""
Vault Lease management.

Provides lease tracking, expiration
monitoring, and revocation capabilities
for Vault secrets and tokens.

Lease lifecycle:
1. Created (with duration/TTL)
2. Active (within duration)
3. Renewable (can extend)
4. Expired (past duration)
5. Revoked (explicitly terminated)
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LeaseState(str, Enum):
    """Lease lifecycle states."""

    ACTIVE = "active"
    RENEWABLE = "renewable"
    EXPIRED = "expired"
    REVOKED = "revoked"
    RENEW_FAILED = "renew_failed"


class Lease:
    """
    Vault lease object.

    Represents a single lease for a Vault
    secret or token, tracking its lifecycle.

    Attributes:
        lease_id: Unique lease identifier.
        duration: Initial lease duration in seconds.
        renewable: Whether the lease can be renewed.
        token: The associated token or lease ID.
        expire_at: Calculated expiration time.
    """

    def __init__(
        self,
        lease_id: str,
        duration: int,
        renewable: bool = True,
        token: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.lease_id = lease_id
        self.duration = duration
        self.renewable = renewable
        self.token = token
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.expire_at = self.created_at + timedelta(seconds=duration)
        self.state = LeaseState.RENEWABLE if renewable else LeaseState.ACTIVE
        self.renewal_count = 0
        self.last_renewal_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Check if lease is currently active."""
        if self.state in (LeaseState.EXPIRED, LeaseState.REVOKED):
            return False
        return datetime.utcnow() < self.expire_at

    @property
    def is_expired(self) -> bool:
        """Check if lease has expired."""
        return datetime.utcnow() >= self.expire_at

    @property
    def seconds_remaining(self) -> int:
        """Get seconds until expiration."""
        remaining = (self.expire_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))

    def renew(self, new_duration: Optional[int] = None) -> None:
        """
        Renew the lease.

        Args:
            new_duration: New duration in seconds
                          (defaults to original duration).
        """
        if not self.is_active:
            raise ValueError(f"Cannot renew lease in state: {self.state}")

        duration = new_duration or self.duration
        self.expire_at = datetime.utcnow() + timedelta(seconds=duration)
        self.state = LeaseState.RENEWABLE if self.renewable else LeaseState.ACTIVE
        self.renewal_count += 1
        self.last_renewal_at = datetime.utcnow()

    def revoke(self) -> None:
        """Revoke the lease immediately."""
        self.state = LeaseState.REVOKED
        self.expire_at = datetime.utcnow()

    def mark_renew_failed(self) -> None:
        """Mark renewal as failed."""
        self.state = LeaseState.RENEW_FAILED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lease_id": self.lease_id,
            "duration": self.duration,
            "renewable": self.renewable,
            "state": self.state.value,
            "created_at": self.created_at.isoformat() + "Z",
            "expire_at": self.expire_at.isoformat() + "Z",
            "is_active": self.is_active,
            "seconds_remaining": self.seconds_remaining,
            "renewal_count": self.renewal_count,
            "last_renewal_at": (
                self.last_renewal_at.isoformat() + "Z"
                if self.last_renewal_at
                else None
            ),
            "metadata": self.metadata,
        }


class LeaseManager:
    """
    Manages multiple Vault leases.

    Provides lease tracking, expiration
    monitoring, and batch operations.

    Usage:
        manager = LeaseManager()
        lease = manager.add_lease(lease_id="abc", duration=3600)
        active = manager.get_active_leases()
        manager.expire_old_leases()
    """

    def __init__(self) -> None:
        self._leases: Dict[str, Lease] = {}
        self._lock = threading.Lock()
        self._on_expire: Optional[Callable[[Lease], None]] = None

    def add_lease(
        self,
        lease_id: str,
        duration: int,
        renewable: bool = True,
        token: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Lease:
        """
        Add a new lease.

        Args:
            lease_id: Unique lease identifier.
            duration: Duration in seconds.
            renewable: Whether renewable.
            token: Associated token.
            metadata: Additional metadata.

        Returns:
            Created Lease object.
        """
        with self._lock:
            lease = Lease(
                lease_id=lease_id,
                duration=duration,
                renewable=renewable,
                token=token,
                metadata=metadata,
            )
            self._leases[lease_id] = lease
            return lease

    def get_lease(self, lease_id: str) -> Optional[Lease]:
        """Get a lease by ID."""
        with self._lock:
            return self._leases.get(lease_id)

    def remove_lease(self, lease_id: str) -> Optional[Lease]:
        """Remove a lease."""
        with self._lock:
            return self._leases.pop(lease_id, None)

    def revoke_lease(self, lease_id: str) -> bool:
        """Revoke a lease."""
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease:
                lease.revoke()
                return True
            return False

    def get_active_leases(self) -> List[Lease]:
        """Get all active leases."""
        with self._lock:
            return [l for l in self._leases.values() if l.is_active]

    def get_expiring_leases(
        self,
        within_seconds: int = 60,
    ) -> List[Lease]:
        """
        Get leases expiring within specified time.

        Args:
            within_seconds: Seconds before expiry to consider.

        Returns:
            List of expiring leases.
        """
        with self._lock:
            cutoff = datetime.utcnow() + timedelta(seconds=within_seconds)
            return [
                l
                for l in self._leases.values()
                if l.is_active and l.expire_at <= cutoff
            ]

    def get_expired_leases(self) -> List[Lease]:
        """Get all expired leases."""
        with self._lock:
            return [l for l in self._leases.values() if l.is_expired]

    def expire_old_leases(self) -> List[Lease]:
        """
        Expire all old leases and fire callbacks.

        Returns:
            List of newly expired leases.
        """
        expired = self.get_expired_leases()
        for lease in expired:
            lease.state = LeaseState.EXPIRED
            if self._on_expire:
                try:
                    self._on_expire(lease)
                except Exception as e:
                    logger.error("Expiry callback failed: %s", e)
        return expired

    def set_expiry_callback(
        self,
        callback: Callable[[Lease], None],
    ) -> None:
        """Set callback for lease expiration."""
        self._on_expire = callback

    def count(self) -> int:
        """Get total lease count."""
        with self._lock:
            return len(self._leases)

    def get_stats(self) -> Dict[str, Any]:
        """Get lease manager statistics."""
        with self._lock:
            leases = list(self._leases.values())
            active = [l for l in leases if l.is_active]
            expired = [l for l in leases if l.is_expired]
            renewable = [l for l in leases if l.renewable]
            return {
                "total": len(leases),
                "active": len(active),
                "expired": len(expired),
                "renewable": len(renewable),
                "failed": len([l for l in leases if l.state == LeaseState.RENEW_FAILED]),
            }
