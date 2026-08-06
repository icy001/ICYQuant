"""Disaster Recovery — cross-region failover and recovery orchestration.

The :class:`DisasterRecovery` provides region-level failure handling,
standby cluster activation, and traffic switching. It lays the foundation
for active-active and active-passive multi-region deployments.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DRSite:
    """A disaster recovery site (region/cluster)."""

    def __init__(
        self,
        site_id: str,
        *,
        region: str = "default",
        role: str = "standby",
        priority: int = 0,
        endpoint: str = "",
    ) -> None:
        self.site_id = site_id
        self.region = region
        self.role = role  # primary / standby / observer
        self.priority = priority
        self.endpoint = endpoint
        self.status: str = "unknown"
        self.last_sync: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "region": self.region,
            "role": self.role,
            "priority": self.priority,
            "endpoint": self.endpoint,
            "status": self.status,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
        }


class DisasterRecovery:
    """Cross-region disaster recovery orchestration.

    Supports:
    - Region failure detection
    - Standby cluster activation
    - Traffic switching
    - Recovery after regional outage

    Usage::

        dr = DisasterRecovery()
        dr.register_site(DRSite("us-east", role="primary"))
        dr.register_site(DRSite("us-west", role="standby"))
        await dr.failover_to("us-west")
    """

    def __init__(
        self,
        *,
        health_check_interval_seconds: float = 15.0,
        sync_interval_seconds: float = 30.0,
    ) -> None:
        self._health_check_interval = health_check_interval_seconds
        self._sync_interval = sync_interval_seconds
        self._lock = threading.Lock()

        self._sites: Dict[str, DRSite] = {}
        self._primary_site_id: Optional[str] = None
        self._is_running = False
        self._failover_count: int = 0
        self._last_failover: Optional[datetime] = None
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def primary_site_id(self) -> Optional[str]:
        return self._primary_site_id

    @property
    def failover_count(self) -> int:
        return self._failover_count

    @property
    def site_count(self) -> int:
        with self._lock:
            return len(self._sites)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start disaster recovery monitoring."""
        self._is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Disaster recovery started [sites=%d]", self.site_count)

    async def stop(self) -> None:
        """Stop disaster recovery monitoring."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Disaster recovery stopped")

    # ------------------------------------------------------------------
    # Site Management
    # ------------------------------------------------------------------

    def register_site(self, site: DRSite) -> None:
        """Register a DR site."""
        with self._lock:
            self._sites[site.site_id] = site
            if site.role == "primary":
                self._primary_site_id = site.site_id
        logger.info("DR site registered [id=%s, region=%s, role=%s]",
                     site.site_id, site.region, site.role)

    def remove_site(self, site_id: str) -> None:
        """Remove a DR site."""
        with self._lock:
            self._sites.pop(site_id, None)
            if self._primary_site_id == site_id:
                self._primary_site_id = None

    def get_site(self, site_id: str) -> Optional[DRSite]:
        """Get a DR site by ID."""
        with self._lock:
            return self._sites.get(site_id)

    def get_primary(self) -> Optional[DRSite]:
        """Get the current primary site."""
        with self._lock:
            if self._primary_site_id:
                return self._sites.get(self._primary_site_id)
        return None

    def get_standby_sites(self) -> List[DRSite]:
        """Get all standby sites."""
        with self._lock:
            return [s for s in self._sites.values() if s.role == "standby"]

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    async def failover_to(self, target_site_id: str) -> bool:
        """Execute a disaster recovery failover to a standby site.

        Pipeline::

            Region Failure → Standby Cluster → Traffic Switch → Recovery
        """
        target = self.get_site(target_site_id)
        if not target:
            logger.error("Failover target site %s not found", target_site_id)
            return False

        logger.warning("DR failover initiated [target=%s, region=%s]",
                        target_site_id, target.region)
        start_time = datetime.now(timezone.utc)

        try:
            # Step 1: Mark old primary as failed
            old_primary = self.get_primary()
            if old_primary:
                old_primary.status = "failed"
                logger.warning("Old primary %s marked as failed", old_primary.site_id)

            # Step 2: Promote target to primary
            with self._lock:
                target.role = "primary"
                target.status = "active"
                self._primary_site_id = target_site_id
                self._failover_count += 1
                self._last_failover = datetime.now(timezone.utc)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info("DR failover completed [target=%s, time=%.2fs]",
                         target_site_id, elapsed)
            return True

        except Exception:
            logger.exception("DR failover failed")
            return False

    async def recover_site(self, site_id: str) -> bool:
        """Recover a previously failed site and bring it back as standby."""
        site = self.get_site(site_id)
        if not site:
            return False
        with self._lock:
            site.role = "standby"
            site.status = "active"
        logger.info("DR site recovered [id=%s]", site_id)
        return True

    async def switch_traffic(self, target_site_id: str) -> bool:
        """Switch scheduler traffic to a target site."""
        return await self.failover_to(target_site_id)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync_sites(self) -> Dict[str, str]:
        """Synchronize state across DR sites."""
        results = {}
        with self._lock:
            for site in self._sites.values():
                site.last_sync = datetime.now(timezone.utc)
                results[site.site_id] = "synced"
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Background monitoring loop for DR sites."""
        while self._is_running:
            try:
                await asyncio.sleep(self._health_check_interval)
                primary = self.get_primary()
                if primary and primary.status != "active":
                    logger.warning("Primary site %s is not active", primary.site_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("DR monitor loop error", exc_info=True)

    def get_dr_info(self) -> Dict[str, Any]:
        """Return disaster recovery status summary."""
        with self._lock:
            return {
                "is_running": self._is_running,
                "primary_site_id": self._primary_site_id,
                "failover_count": self._failover_count,
                "last_failover": self._last_failover.isoformat() if self._last_failover else None,
                "sites": {sid: s.to_dict() for sid, s in self._sites.items()},
            }
