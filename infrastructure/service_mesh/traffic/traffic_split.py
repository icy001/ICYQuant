"""Traffic split for ICYQuant Service Mesh.

Provides ``TrafficSplit`` for weighted/percentage/user-group/region/
feature-flag based traffic distribution across destinations.
"""

from __future__ import annotations

import hashlib
import logging
import random
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrafficSplit:
    """Distributes traffic across multiple destinations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._split_count = 0

    def select_destination(
        self,
        destinations: List[Dict[str, Any]],
        key: str = "",
        strategy: str = "weighted",
        user_groups: Optional[List[str]] = None,
        region: str = "",
        feature_flags: Optional[Dict[str, bool]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select a destination based on the split strategy."""
        if not destinations:
            return None

        with self._lock:
            self._split_count += 1

        if strategy == "user_group" and user_groups:
            return self._select_by_user_group(
                destinations, user_groups
            )
        elif strategy == "region" and region:
            return self._select_by_region(destinations, region)
        elif strategy == "feature_flag" and feature_flags:
            return self._select_by_feature_flag(
                destinations, feature_flags
            )
        elif strategy == "percentage" and key:
            return self._select_by_percentage(
                destinations, key
            )
        else:
            return self._select_by_weight(destinations, key)

    def _select_by_weight(
        self,
        destinations: List[Dict[str, Any]],
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """Select destination by weight."""
        total_weight = sum(
            d.get("weight", 1.0) for d in destinations
        )
        if total_weight <= 0:
            return destinations[0]

        if key:
            hash_val = int(
                hashlib.md5(key.encode()).hexdigest(), 16
            )
            target = (hash_val % 1000) / 1000.0 * total_weight
        else:
            target = random.uniform(0, total_weight)

        cumulative = 0.0
        for dest in destinations:
            cumulative += dest.get("weight", 1.0)
            if cumulative >= target:
                return dest

        return destinations[-1]

    def _select_by_percentage(
        self,
        destinations: List[Dict[str, Any]],
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """Select destination by percentage using consistent hash."""
        total_pct = sum(
            d.get("weight", 1.0) for d in destinations
        )
        hash_val = int(
            hashlib.md5(key.encode()).hexdigest(), 16
        )
        target = (hash_val % 10000) / 10000.0 * total_pct

        cumulative = 0.0
        for dest in destinations:
            cumulative += dest.get("weight", 1.0)
            if cumulative >= target:
                return dest

        return destinations[-1]

    def _select_by_user_group(
        self,
        destinations: List[Dict[str, Any]],
        user_groups: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Select destination by user group label."""
        for dest in destinations:
            dest_groups = dest.get("user_groups", [])
            if any(g in user_groups for g in dest_groups):
                return dest
        return destinations[0]

    def _select_by_region(
        self,
        destinations: List[Dict[str, Any]],
        region: str,
    ) -> Optional[Dict[str, Any]]:
        """Select destination by region label."""
        for dest in destinations:
            dest_region = dest.get("region", "")
            if dest_region == region:
                return dest
        return destinations[0]

    def _select_by_feature_flag(
        self,
        destinations: List[Dict[str, Any]],
        feature_flags: Dict[str, bool],
    ) -> Optional[Dict[str, Any]]:
        """Select destination by feature flag."""
        for dest in destinations:
            dest_flags = dest.get("feature_flags", {})
            if dest_flags and all(
                feature_flags.get(k, False)
                for k in dest_flags
            ):
                return dest
        return destinations[0]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "split_count": self._split_count,
            }