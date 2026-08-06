"""Distributed Lock — fine-grained distributed locking for the scheduler cluster.

The :class:`DistributedLock` prevents duplicate scheduling and ensures
mutual exclusion across scheduler nodes. It supports schedule-level,
job-level, trigger-level, and worker-level locks.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from .lease_manager import LeaseManager, LeaseStatus

logger = logging.getLogger(__name__)


class LockType:
    """Types of distributed locks."""

    SCHEDULE = "schedule"
    JOB = "job"
    TRIGGER = "trigger"
    WORKER = "worker"
    CUSTOM = "custom"


class LockAcquisition:
    """Result of a lock acquisition attempt."""

    def __init__(
        self,
        acquired: bool,
        lock_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.acquired = acquired
        self.lock_id = lock_id
        self.reason = reason
        self.timestamp = datetime.now(timezone.utc)


class DistributedLock:
    """Fine-grained distributed locking for preventing duplicate scheduling.

    Supports lock types:
    - schedule: lock an entire schedule definition
    - job: lock a specific job execution
    - trigger: lock a trigger evaluation
    - worker: lock a worker node for exclusive assignment

    Usage::

        lock = DistributedLock(lease_manager=lease_mgr)
        result = await lock.acquire("schedule:daily-report", lock_type=LockType.SCHEDULE, ttl=60.0)
        if result.acquired:
            try:
                # do exclusive work
                pass
            finally:
                await lock.release(result.lock_id)
    """

    def __init__(
        self,
        *,
        lease_manager: Optional[LeaseManager] = None,
        default_ttl_seconds: float = 30.0,
        retry_interval_seconds: float = 0.1,
        max_retries: int = 10,
    ) -> None:
        self._lease_mgr = lease_manager or LeaseManager(default_ttl_seconds=default_ttl_seconds)
        self._default_ttl = default_ttl_seconds
        self._retry_interval = retry_interval_seconds
        self._max_retries = max_retries
        self._lock = threading.Lock()
        self._acquired: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active_lock_count(self) -> int:
        with self._lock:
            return len(self._acquired)

    # ------------------------------------------------------------------
    # Lock Operations
    # ------------------------------------------------------------------

    async def acquire(
        self,
        resource: str,
        *,
        lock_type: str = LockType.CUSTOM,
        holder_id: str = "default",
        ttl: Optional[float] = None,
        blocking: bool = False,
    ) -> LockAcquisition:
        """Acquire a distributed lock on a resource.

        Args:
            resource: The resource identifier to lock.
            lock_type: Type of lock (schedule/job/trigger/worker/custom).
            holder_id: ID of the requesting entity.
            ttl: Lock time-to-live in seconds.
            blocking: If True, retry until acquired or max_retries exceeded.

        Returns:
            LockAcquisition indicating success or failure.
        """
        ttl = ttl or self._default_ttl
        key = f"{lock_type}:{resource}"
        retries = 0

        while True:
            lease_id = await self._lease_mgr.acquire(
                holder_id=holder_id,
                resource=key,
                ttl=ttl,
            )

            if lease_id:
                with self._lock:
                    self._acquired[lease_id] = {
                        "resource": key,
                        "lock_type": lock_type,
                        "holder_id": holder_id,
                        "acquired_at": datetime.now(timezone.utc),
                    }
                logger.debug("Lock acquired [type=%s, resource=%s, holder=%s]",
                              lock_type, resource, holder_id)
                return LockAcquisition(acquired=True, lock_id=lease_id)

            if not blocking or retries >= self._max_retries:
                return LockAcquisition(
                    acquired=False,
                    reason=f"Resource {key} is locked after {retries} retries",
                )

            retries += 1
            await asyncio.sleep(self._retry_interval * (2 ** (retries - 1)))

    async def release(self, lock_id: str) -> bool:
        """Release a previously acquired lock."""
        released = await self._lease_mgr.release(lock_id)
        if released:
            with self._lock:
                self._acquired.pop(lock_id, None)
        return released

    async def renew(self, lock_id: str) -> bool:
        """Renew a lock's TTL."""
        return await self._lease_mgr.renew(lock_id)

    def is_held(self, resource: str, *, lock_type: str = LockType.CUSTOM) -> bool:
        """Check if a lock is currently held on a resource."""
        key = f"{lock_type}:{resource}"
        with self._lock:
            for info in self._acquired.values():
                if info["resource"] == key:
                    return True
        return False

    async def force_release(self, resource: str, *, lock_type: str = LockType.CUSTOM) -> int:
        """Forcefully release all locks on a given resource. Returns count."""
        key = f"{lock_type}:{resource}"
        released = 0
        with self._lock:
            to_release = [lid for lid, info in self._acquired.items() if info["resource"] == key]
        for lid in to_release:
            if await self._lease_mgr.revoke(lid):
                released += 1
        return released

    def get_lock_info(self) -> Dict[str, Any]:
        """Return distributed lock status summary."""
        return {
            "active_locks": self.active_lock_count,
            "default_ttl_seconds": self._default_ttl,
            "retry_interval_seconds": self._retry_interval,
            "max_retries": self._max_retries,
        }
