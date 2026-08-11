"""
Strategy Cluster — High-Correlation Strategy Group Detection

Detects strategy clusters where multiple strategies share high
correlation, factor overlap, or risk overlap. These clusters
represent concentrated bets, not independent diversification.

Example: 3 strategies with 0.82+ correlation → 1 cluster, not 3 bets.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    cluster_id: str
    strategy_ids: List[str]
    average_correlation: float
    severity: str  # HIGH, MEDIUM, LOW
    dominant_factor: Optional[str] = None


class StrategyCluster:
    """
    Detects and manages strategy correlation clusters.

    A cluster means multiple strategies represent a single
    concentrated bet, not independent diversification.
    The portfolio must limit total exposure to any cluster.
    """

    def __init__(
        self,
        cluster_id: Optional[str] = None,
        registry=None,
        exposure_matrix=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.cluster_id = cluster_id or f"sc-{uuid.uuid4().hex[:12]}"
        self._registry = registry
        self._exposure_matrix = exposure_matrix
        self.config = config or {}
        self._high_threshold = self.config.get("high_threshold", 0.70)
        self._clusters: List[ClusterResult] = []

    def detect(self) -> List[ClusterResult]:
        """Detect all strategy clusters from the exposure matrix."""
        self._clusters = []
        if not self._registry or not self._exposure_matrix:
            return self._clusters

        strategies = list(self._registry.get_active().keys())
        matrix = self._exposure_matrix.get_matrix()

        visited: Set[str] = set()
        for s1 in strategies:
            if s1 in visited:
                continue
            cluster_members = [s1]
            cluster_corrs = []
            for s2 in strategies:
                if s2 in visited or s1 == s2:
                    continue
                corr = matrix.get(s1, {}).get(s2, 0) if s2 in matrix.get(s1, {}) else (
                    matrix.get(s2, {}).get(s1, 0) if s1 in matrix.get(s2, {}) else 0
                )
                if abs(corr) > self._high_threshold:
                    cluster_members.append(s2)
                    cluster_corrs.append(abs(corr))
                    visited.add(s2)

            if len(cluster_members) > 1:
                visited.add(s1)
                avg_corr = sum(cluster_corrs) / len(cluster_corrs) if cluster_corrs else 0
                severity = "HIGH" if avg_corr > 0.85 else "MEDIUM"
                self._clusters.append(ClusterResult(
                    cluster_id=f"cl-{uuid.uuid4().hex[:8]}",
                    strategy_ids=cluster_members,
                    average_correlation=avg_corr,
                    severity=severity,
                ))

        return self._clusters

    def get_high_clusters(self) -> List[ClusterResult]:
        return [c for c in self._clusters if c.severity == "HIGH"]

    def get_cluster_for_strategy(self, strategy_id: str) -> Optional[ClusterResult]:
        for c in self._clusters:
            if strategy_id in c.strategy_ids:
                return c
        return None

    def get_effective_strategy_count(self) -> int:
        """Effective independent strategies after clustering."""
        if not self._registry:
            return 0
        total = len(self._registry.get_active())
        clustered = set()
        for c in self._clusters:
            clustered.update(c.strategy_ids)
        return total - len(clustered) + len(self._clusters)
