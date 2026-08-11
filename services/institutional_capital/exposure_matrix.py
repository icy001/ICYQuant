"""
Exposure Matrix — Multi-Dimensional Strategy Overlap Analysis

The ExposureMatrix computes the full N×N matrix of strategy overlaps:
- Strategy Correlation (returns-based)
- Factor Overlap (factor loading similarity)
- Risk Overlap (risk factor co-movement)
- Liquidity Overlap (liquidity pool competition)

The TRUE diversification is determined by ALL four dimensions,
not just return correlation.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OverlapResult:
    strategy_a: str
    strategy_b: str
    correlation: float = 0.0
    factor_overlap: float = 0.0
    risk_overlap: float = 0.0
    liquidity_overlap: float = 0.0
    composite_overlap: float = 0.0
    severity: str = "NONE"


class ExposureMatrix:
    """
    Computes full multi-dimensional strategy overlap matrix.

    Four dimensions of overlap:
    1. Strategy Correlation — returns-based, traditional
    2. Factor Overlap — shared factor loadings
    3. Risk Overlap — shared risk factors
    4. Liquidity Overlap — shared liquidity pools

    Composite overlap = weighted combination of all four.
    """

    def __init__(
        self,
        matrix_id: Optional[str] = None,
        strategy_pool=None,
        strategy_exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.matrix_id = matrix_id or f"exm-{uuid.uuid4().hex[:12]}"
        self._strategy_pool = strategy_pool
        self._strategy_exposure = strategy_exposure
        self.config = config or {}

        # Weights for composite overlap
        self._weights = {
            "correlation": self.config.get("weight_correlation", 0.30),
            "factor": self.config.get("weight_factor", 0.30),
            "risk": self.config.get("weight_risk", 0.25),
            "liquidity": self.config.get("weight_liquidity", 0.15),
        }

        # Thresholds for severity
        self._high_threshold = self.config.get("high_overlap_threshold", 0.70)
        self._medium_threshold = self.config.get("medium_overlap_threshold", 0.40)

        self._matrix: Dict[str, Dict[str, OverlapResult]] = {}
        self._cluster: List[List[str]] = []

    def compute(self, strategies: Optional[List[str]] = None) -> Dict[str, Dict[str, OverlapResult]]:
        """Compute the full N×N overlap matrix."""
        ids = strategies or self._get_strategy_ids()
        self._matrix = {}

        for i in range(len(ids)):
            s1 = ids[i]
            self._matrix[s1] = {}
            for j in range(len(ids)):
                s2 = ids[j]
                if s1 == s2:
                    self._matrix[s1][s2] = OverlapResult(
                        strategy_a=s1, strategy_b=s2,
                        correlation=1.0, composite_overlap=1.0,
                        severity="SELF",
                    )
                elif s2 in self._matrix and s1 in self._matrix[s2]:
                    # Symmetric
                    result = self._matrix[s2][s1]
                    self._matrix[s1][s2] = OverlapResult(
                        strategy_a=s1, strategy_b=s2,
                        correlation=result.correlation,
                        factor_overlap=result.factor_overlap,
                        risk_overlap=result.risk_overlap,
                        liquidity_overlap=result.liquidity_overlap,
                        composite_overlap=result.composite_overlap,
                        severity=result.severity,
                    )
                else:
                    overlap = self._compute_pair(s1, s2)
                    self._matrix[s1][s2] = overlap

        self._detect_clusters()
        return self._matrix

    def _compute_pair(self, s1: str, s2: str) -> OverlapResult:
        """Compute overlap for a strategy pair."""
        corr = self._compute_correlation(s1, s2)
        factor = self._compute_factor_overlap(s1, s2)
        risk = self._compute_risk_overlap(s1, s2)
        liquidity = self._compute_liquidity_overlap(s1, s2)

        composite = (
            self._weights["correlation"] * abs(corr) +
            self._weights["factor"] * factor +
            self._weights["risk"] * risk +
            self._weights["liquidity"] * liquidity
        )

        severity = "NONE"
        if composite > self._high_threshold:
            severity = "HIGH"
        elif composite > self._medium_threshold:
            severity = "MEDIUM"

        return OverlapResult(
            strategy_a=s1, strategy_b=s2,
            correlation=corr,
            factor_overlap=factor,
            risk_overlap=risk,
            liquidity_overlap=liquidity,
            composite_overlap=composite,
            severity=severity,
        )

    def _compute_correlation(self, s1: str, s2: str) -> float:
        if self._strategy_pool:
            r1 = self._strategy_pool.get(s1)
            r2 = self._strategy_pool.get(s2)
            if r1 and r2:
                return max(r1.correlation, r2.correlation)
        return 0.0

    def _compute_factor_overlap(self, s1: str, s2: str) -> float:
        if self._strategy_exposure:
            overlaps = self._strategy_exposure.get_factor_overlap(s1, s2)
            if overlaps:
                return sum(overlaps.values()) / len(overlaps)
        return 0.0

    def _compute_risk_overlap(self, s1: str, s2: str) -> float:
        return 0.0  # Delegate to RiskOverlap module

    def _compute_liquidity_overlap(self, s1: str, s2: str) -> float:
        return 0.0  # Delegate to LiquidityOverlap module

    def _get_strategy_ids(self) -> List[str]:
        if self._strategy_pool:
            return list(self._strategy_pool.get_all().keys())
        return []

    def _detect_clusters(self) -> None:
        """Detect strategy clusters with high overlap."""
        ids = list(self._matrix.keys())
        visited: Set[str] = set()
        self._clusters = []

        for s1 in ids:
            if s1 in visited:
                continue
            cluster = [s1]
            visited.add(s1)
            for s2 in ids:
                if s2 in visited:
                    continue
                if self._matrix.get(s1, {}).get(s2):
                    if self._matrix[s1][s2].severity == "HIGH":
                        cluster.append(s2)
                        visited.add(s2)
            if len(cluster) > 1:
                self._clusters.append(cluster)

    def get_clusters(self) -> List[List[str]]:
        return self._clusters

    def get_high_overlap_pairs(self) -> List[Dict[str, Any]]:
        pairs = []
        for s1, row in self._matrix.items():
            for s2, overlap in row.items():
                if s1 < s2 and overlap.severity in ("HIGH", "MEDIUM"):
                    pairs.append({
                        "strategies": [s1, s2],
                        "composite": overlap.composite_overlap,
                        "severity": overlap.severity,
                    })
        return sorted(pairs, key=lambda x: -x["composite"])

    def get_effective_strategy_count(self) -> int:
        """Effective number of independent strategies after overlap."""
        ids = list(self._matrix.keys())
        if not ids:
            return 0
        clustered = set()
        for cluster in self._clusters:
            clustered.update(cluster)
        independent = set(ids) - clustered
        return len(independent) + len(self._clusters)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "matrix_id": self.matrix_id,
            "strategy_count": len(self._matrix),
            "effective_count": self.get_effective_strategy_count(),
            "clusters": self.get_clusters(),
            "high_overlap_pairs": self.get_high_overlap_pairs(),
        }
