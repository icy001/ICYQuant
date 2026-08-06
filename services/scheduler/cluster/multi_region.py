"""Multi-Region Manager — cross-region scheduling framework.

The :class:`MultiRegionManager` provides a foundation for multi-region
scheduler deployments. It manages regional scheduler clusters, routes
jobs to the appropriate region, and supports global scheduling policies.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RegionRole:
    """Roles for scheduler regions."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EDGE = "edge"
    GLOBAL = "global"


class MultiRegionManager:
    """Manages multi-region scheduler deployments.

    Architecture::

        Global Scheduler
              │
        ┌─────┼─────┐
        Region-A  Region-B  Region-C
              │
        ┌─────┼─────┐
        Scheduler Nodes (per region)

    Usage::

        mgr = MultiRegionManager()
        mgr.register_region("us-east", role=RegionRole.PRIMARY)
        mgr.register_region("eu-west", role=RegionRole.SECONDARY)
        region = mgr.route_job(job, prefer_region="us-east")
    """

    def __init__(
        self,
        *,
        default_region: str = "default",
    ) -> None:
        self._default_region = default_region
        self._lock = threading.Lock()
        self._regions: Dict[str, Dict[str, Any]] = {}
        self._primary_region: Optional[str] = None
        self._routing_table: Dict[str, str] = {}  # key → region

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def default_region(self) -> str:
        return self._default_region

    @property
    def primary_region(self) -> Optional[str]:
        return self._primary_region

    @property
    def region_count(self) -> int:
        with self._lock:
            return len(self._regions)

    # ------------------------------------------------------------------
    # Region Management
    # ------------------------------------------------------------------

    def register_region(
        self,
        region_id: str,
        *,
        role: str = RegionRole.SECONDARY,
        endpoint: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a scheduler region.

        Args:
            region_id: Unique region identifier (e.g., "us-east-1").
            role: Region role (primary/secondary/edge/global).
            endpoint: Connection endpoint for the region.
            metadata: Additional region metadata.
        """
        with self._lock:
            self._regions[region_id] = {
                "region_id": region_id,
                "role": role,
                "endpoint": endpoint,
                "status": "active",
                "registered_at": datetime.now(timezone.utc),
                "metadata": metadata or {},
                "node_count": 0,
            }
            if role == RegionRole.PRIMARY:
                self._primary_region = region_id

        logger.info("Region registered [id=%s, role=%s]", region_id, role)

    def remove_region(self, region_id: str) -> None:
        """Remove a region."""
        with self._lock:
            self._regions.pop(region_id, None)
            if self._primary_region == region_id:
                self._primary_region = None

    def get_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """Get region details."""
        with self._lock:
            return dict(self._regions.get(region_id, {}))

    def list_regions(self, *, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """List registered regions, optionally filtered by role."""
        with self._lock:
            regions = list(self._regions.values())
            if role:
                regions = [r for r in regions if r["role"] == role]
            return [dict(r) for r in regions]

    def get_primary(self) -> Optional[Dict[str, Any]]:
        """Get the primary region."""
        with self._lock:
            if self._primary_region and self._primary_region in self._regions:
                return dict(self._regions[self._primary_region])
        return None

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_job(self, job: Any, *, prefer_region: Optional[str] = None) -> str:
        """Determine which region should handle a job.

        Routing priority:
        1. Explicit routing key
        2. Prefer region (affinity)
        3. Primary region
        4. Default region

        Returns:
            Region ID.
        """
        # Check routing table
        job_key = getattr(job, "region_key", None)
        if job_key:
            with self._lock:
                if job_key in self._routing_table:
                    return self._routing_table[job_key]

        # Prefer region
        if prefer_region:
            with self._lock:
                if prefer_region in self._regions:
                    return prefer_region

        # Primary region
        with self._lock:
            if self._primary_region:
                return self._primary_region

        return self._default_region

    def set_routing_rule(self, key: str, region_id: str) -> None:
        """Set a routing rule: key → region."""
        with self._lock:
            self._routing_table[key] = region_id
        logger.debug("Routing rule set [%s → %s]", key, region_id)

    def remove_routing_rule(self, key: str) -> None:
        """Remove a routing rule."""
        with self._lock:
            self._routing_table.pop(key, None)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def update_region_status(self, region_id: str, status: str, node_count: int = 0) -> None:
        """Update the status of a region."""
        with self._lock:
            if region_id in self._regions:
                self._regions[region_id]["status"] = status
                self._regions[region_id]["node_count"] = node_count

    def get_region_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all regions."""
        with self._lock:
            return {
                rid: {"status": r["status"], "role": r["role"], "node_count": r["node_count"]}
                for rid, r in self._regions.items()
            }

    def get_multi_region_info(self) -> Dict[str, Any]:
        """Return multi-region status summary."""
        return {
            "default_region": self._default_region,
            "primary_region": self._primary_region,
            "region_count": self.region_count,
            "routing_rules": len(self._routing_table),
            "regions": self.list_regions(),
        }
