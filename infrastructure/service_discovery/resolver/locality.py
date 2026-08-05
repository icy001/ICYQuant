"""Locality-based routing for service discovery.

Provides ``LocalityRouter`` which prefers instances in the same
region, zone, or rack as the caller. Falls back to broader
locality levels when closer matches are unavailable.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class LocalityRouter:
    """Routes service instances by geographic/network locality.

    Priority order: Region → Zone → Rack (reserved) → Fallback.

    Usage::

        router = LocalityRouter()
        router.set_affinity(region="us-east-1", zone="us-east-1a")
        filtered = router.filter(instances, context)
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._preferred_region: Optional[str] = None
        self._preferred_zone: Optional[str] = None
        self._route_count = 0
        self._local_hits = 0
        self._fallback_count = 0

    def set_affinity(
        self,
        region: str = None,
        zone: str = None,
    ) -> None:
        """Set preferred locality for routing.

        Args:
            region: Preferred geographic region.
            zone: Preferred availability zone.
        """
        with self._lock:
            self._preferred_region = region
            self._preferred_zone = zone
            logger.debug(
                "Locality affinity set: region=%s, zone=%s",
                region,
                zone,
            )

    def filter(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> List[ServiceInstance]:
        """Filter instances preferring local locality.

        Attempts to match instances at region, then zone, then
        rack level before falling back to all available instances.

        Args:
            instances: Candidate instances.
            context: Optional resolution context.

        Returns:
            Filtered list of instances prioritizing locality.
        """
        if not instances:
            return []

        with self._lock:
            self._route_count += 1
            preferred_region = self._preferred_region
            preferred_zone = self._preferred_zone

        if context is not None:
            if preferred_region is None and context.region:
                preferred_region = context.region
            if preferred_zone is None and context.zone:
                preferred_zone = context.zone

        if preferred_region is None and preferred_zone is None:
            with self._lock:
                self._fallback_count += 1
            return list(instances)

        region_matches = self._match_by_region(instances, preferred_region)
        if region_matches:
            if preferred_zone is not None:
                zone_matches = self._match_by_zone(region_matches, preferred_zone)
                if zone_matches:
                    with self._lock:
                        self._local_hits += 1
                    return zone_matches
            with self._lock:
                self._local_hits += 1
            return region_matches

        with self._lock:
            self._fallback_count += 1
        return list(instances)

    def score(self, instance: ServiceInstance) -> float:
        """Compute a locality score for an instance.

        Higher scores indicate closer locality to the preferred
        region/zone. Score range: 0.0 (distant) to 1.0 (same zone).

        Args:
            instance: The instance to score.

        Returns:
            A float between 0.0 and 1.0.
        """
        if instance is None:
            return 0.0

        with self._lock:
            preferred_region = self._preferred_region
            preferred_zone = self._preferred_zone

        instance_region = ""
        instance_zone = ""
        if isinstance(instance.metadata, dict):
            instance_region = str(instance.metadata.get("region", ""))
            instance_zone = str(instance.metadata.get("zone", ""))

        score = 0.0

        if preferred_region is not None and instance_region == preferred_region:
            score += 0.5
            if preferred_zone is not None and instance_zone == preferred_zone:
                score += 0.5
        elif preferred_region is None and preferred_zone is not None:
            if instance_zone == preferred_zone:
                score += 1.0

        return score

    @staticmethod
    def _match_by_region(
        instances: List[ServiceInstance],
        region: Optional[str],
    ) -> List[ServiceInstance]:
        if region is None:
            return list(instances)
        result: List[ServiceInstance] = []
        for instance in instances:
            instance_region = ""
            if isinstance(instance.metadata, dict):
                instance_region = str(instance.metadata.get("region", ""))
            if instance_region == region:
                result.append(instance)
        return result

    @staticmethod
    def _match_by_zone(
        instances: List[ServiceInstance],
        zone: Optional[str],
    ) -> List[ServiceInstance]:
        if zone is None:
            return list(instances)
        result: List[ServiceInstance] = []
        for instance in instances:
            instance_zone = ""
            if isinstance(instance.metadata, dict):
                instance_zone = str(instance.metadata.get("zone", ""))
            if instance_zone == zone:
                result.append(instance)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return locality router statistics.

        Returns:
            A dictionary with routing counts and affinity settings.
        """
        with self._lock:
            return {
                "router": "LocalityRouter",
                "preferred_region": self._preferred_region,
                "preferred_zone": self._preferred_zone,
                "route_count": self._route_count,
                "local_hits": self._local_hits,
                "fallback_count": self._fallback_count,
                "local_hit_rate": (
                    self._local_hits / self._route_count
                    if self._route_count
                    else 0.0
                ),
            }

    def __repr__(self) -> str:
        return (
            f"LocalityRouter(region={self._preferred_region!r}, "
            f"zone={self._preferred_zone!r}, routes={self._route_count})"
        )