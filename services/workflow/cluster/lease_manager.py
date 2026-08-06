"""Lease Manager — distributed lease management for workflow resources.

Manages three types of leases:

* **Workflow Lease** — ensures at most one node executes a given workflow instance
* **Node Lease** — node membership lease, tied to heartbeat
* **Scheduler Lease** — leadership lease for the distributed scheduler

Features:
* Automatic renewal with configurable intervals
* Automatic expiration with takeover protection
* Preemptive recovery on lease expiry
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LeaseType(str, Enum):
    """Types of leases managed by the system."""

    WORKFLOW = "workflow"
    NODE = "node"
    SCHEDULER = "scheduler"


class LeaseState(str, Enum):
    """Lifecycle states of a lease."""

    ACQUIRED = "acquired"
    RENEWING = "renewing"
    EXPIRED = "expired"
    RELEASED = "released"
    PREEMPTED = "preempted"


@dataclass
class Lease:
    """A distributed lease with automatic expiration."""

    lease_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lease_type: LeaseType = LeaseType.NODE
    owner_id: str = ""
    resource_id: str = ""
    acquired_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    renewed_at: Optional[datetime] = None
    state: LeaseState = LeaseState.ACQUIRED
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at

    @property
    def ttl_seconds(self) -> float:
        if self.expires_at is None:
            return float("inf")
        remaining = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(0.0, remaining)

    @property
    def age_seconds(self) -> float:
        return (datetime.utcnow() - self.acquired_at).total_seconds()

    def renew(self, duration_seconds: float) -> None:
        """Extend the lease by the given duration."""
        self.expires_at = datetime.utcnow()
        self.expires_at = self.expires_at.replace(
            microsecond=0
        ) + __import__("datetime").timedelta(seconds=duration_seconds)
        self.renewed_at = datetime.utcnow()
        self.state = LeaseState.RENEWING
        self.version += 1

    def expire(self) -> None:
        """Mark the lease as expired."""
        self.state = LeaseState.EXPIRED

    def release(self) -> None:
        """Voluntarily release the lease."""
        self.state = LeaseState.RELEASED

    def preempt(self) -> None:
        """Mark the lease as preempted (taken over by another owner)."""
        self.state = LeaseState.PREEMPTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "lease_type": self.lease_type.value,
            "owner_id": self.owner_id,
            "resource_id": self.resource_id,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "renewed_at": self.renewed_at.isoformat() if self.renewed_at else None,
            "state": self.state.value,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Lease:
        acquired_at = data.get("acquired_at")
        expires_at = data.get("expires_at")
        renewed_at = data.get("renewed_at")
        return cls(
            lease_id=data.get("lease_id", str(uuid.uuid4())),
            lease_type=LeaseType(data.get("lease_type", "node")),
            owner_id=data.get("owner_id", ""),
            resource_id=data.get("resource_id", ""),
            acquired_at=datetime.fromisoformat(acquired_at) if acquired_at else datetime.utcnow(),
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
            renewed_at=datetime.fromisoformat(renewed_at) if renewed_at else None,
            state=LeaseState(data.get("state", "acquired")),
            version=int(data.get("version", 1)),
            metadata=dict(data.get("metadata", {})),
        )


class LeaseManager:
    """Manages distributed leases for workflow resources.

    Usage::

        mgr = LeaseManager(default_duration=30.0)
        lease = await mgr.acquire("workflow_123", owner="node_abc", lease_type=LeaseType.WORKFLOW)
        await mgr.renew(lease.lease_id)
        await mgr.release(lease.lease_id)
    """

    def __init__(
        self,
        *,
        default_duration_seconds: float = 30.0,
        renew_interval_seconds: float = 10.0,
    ) -> None:
        self._default_duration = default_duration_seconds
        self._renew_interval = renew_interval_seconds
        self._lock = threading.RLock()
        self._leases: Dict[str, Lease] = {}
        self._leases_by_resource: Dict[str, str] = {}  # resource_id → lease_id

        # Background renewal
        self._started = False
        self._renew_task: Optional[asyncio.Task] = None
        self._expire_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_expire_callbacks: list = []
        self._on_preempt_callbacks: list = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active_lease_count(self) -> int:
        with self._lock:
            return sum(1 for l in self._leases.values() if l.state == LeaseState.ACQUIRED)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the lease manager and background renewal/expiry loops."""
        self._started = True
        self._renew_task = asyncio.create_task(self._renew_loop())
        self._expire_task = asyncio.create_task(self._expire_loop())
        logger.info("LeaseManager: started")

    async def stop(self) -> None:
        """Stop the lease manager and release all held leases."""
        self._started = False
        for task in (self._renew_task, self._expire_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Release all active leases
        with self._lock:
            for lease in list(self._leases.values()):
                if lease.state == LeaseState.ACQUIRED:
                    lease.release()
        logger.info("LeaseManager: stopped")

    # ------------------------------------------------------------------
    # Lease operations
    # ------------------------------------------------------------------

    async def acquire(
        self,
        resource_id: str,
        *,
        owner_id: str,
        lease_type: LeaseType = LeaseType.WORKFLOW,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Lease:
        """Acquire a lease for a resource.

        Returns the new lease. If the resource already has an active lease,
        attempts preemption.
        """
        duration = duration_seconds or self._default_duration

        with self._lock:
            # Check for existing lease on this resource
            existing_id = self._leases_by_resource.get(resource_id)
            if existing_id and existing_id in self._leases:
                existing = self._leases[existing_id]
                if existing.state == LeaseState.ACQUIRED and not existing.is_expired:
                    if existing.owner_id != owner_id:
                        # Preempt
                        existing.preempt()
                        for cb in self._on_preempt_callbacks:
                            try:
                                cb(existing)
                            except Exception:
                                logger.exception("LeaseManager: preempt callback error")

            lease = Lease(
                lease_type=lease_type,
                owner_id=owner_id,
                resource_id=resource_id,
                metadata=metadata or {},
            )
            lease.renew(duration)
            self._leases[lease.lease_id] = lease
            self._leases_by_resource[resource_id] = lease.lease_id

        logger.debug("LeaseManager: acquired lease %s for resource %s by %s",
                      lease.lease_id, resource_id, owner_id)
        return lease

    async def renew(self, lease_id: str, duration_seconds: Optional[float] = None) -> bool:
        """Renew an existing lease. Returns False if the lease is not found or expired."""
        duration = duration_seconds or self._default_duration
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                return False
            if lease.state in (LeaseState.EXPIRED, LeaseState.PREEMPTED, LeaseState.RELEASED):
                return False
            lease.renew(duration)
        return True

    async def release(self, lease_id: str) -> bool:
        """Release a lease. Returns False if not found."""
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                return False
            lease.release()
            if lease.resource_id in self._leases_by_resource:
                del self._leases_by_resource[lease.resource_id]
        return True

    async def get_lease(self, lease_id: str) -> Optional[Lease]:
        """Retrieve a lease by ID."""
        with self._lock:
            return self._leases.get(lease_id)

    async def get_lease_for_resource(self, resource_id: str) -> Optional[Lease]:
        """Retrieve the lease for a given resource."""
        with self._lock:
            lease_id = self._leases_by_resource.get(resource_id)
            if lease_id:
                return self._leases.get(lease_id)
            return None

    async def list_leases(
        self,
        *,
        owner_id: Optional[str] = None,
        lease_type: Optional[LeaseType] = None,
    ) -> List[Lease]:
        """List leases, optionally filtered."""
        with self._lock:
            results = []
            for lease in self._leases.values():
                if owner_id and lease.owner_id != owner_id:
                    continue
                if lease_type and lease.lease_type != lease_type:
                    continue
                results.append(lease)
            return results

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _renew_loop(self) -> None:
        """Automatically renew all active leases held by this node."""
        while self._started:
            try:
                await asyncio.sleep(self._renew_interval)
                with self._lock:
                    for lease in list(self._leases.values()):
                        if lease.state == LeaseState.ACQUIRED:
                            lease.renew(self._default_duration)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("LeaseManager: error in renew loop")

    async def _expire_loop(self) -> None:
        """Check for and handle expired leases."""
        while self._started:
            try:
                await asyncio.sleep(1.0)
                with self._lock:
                    for lease in list(self._leases.values()):
                        if lease.state == LeaseState.ACQUIRED and lease.is_expired:
                            lease.expire()
                            for cb in self._on_expire_callbacks:
                                try:
                                    cb(lease)
                                except Exception:
                                    logger.exception("LeaseManager: expire callback error")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("LeaseManager: error in expire loop")

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_expire(self, callback) -> None:
        """Register a callback for lease expiration events."""
        self._on_expire_callbacks.append(callback)

    def on_preempt(self, callback) -> None:
        """Register a callback for lease preemption events."""
        self._on_preempt_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active_leases": self.active_lease_count,
                "total_leases": len(self._leases),
                "default_duration_seconds": self._default_duration,
            }
