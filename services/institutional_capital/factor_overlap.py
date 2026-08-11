"""
Factor Overlap — Factor Loading Similarity Between Strategies

Two strategies may have low P&L correlation but high factor overlap.
E.g., both Momentum and Mean Reversion strategies might load on
the same Value/Momentum factors during certain regimes.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FactorOverlapResult:
    strategy_a: str
    strategy_b: str
    overlap_score: float
    dominant_factors: List[str]
    severity: str = "NONE"


class FactorOverlap:
    """
    Computes factor loading overlap between strategy pairs.

    Measures how much two strategies share the same risk factor
    exposures, regardless of their return correlation.
    """

    def __init__(
        self,
        overlap_id: Optional[str] = None,
        strategy_exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.overlap_id = overlap_id or f"fo-{uuid.uuid4().hex[:12]}"
        self._strategy_exposure = strategy_exposure
        self.config = config or {}
        self._results: Dict[str, Dict[str, FactorOverlapResult]] = {}

    def compute(self, s1: str, s2: str) -> FactorOverlapResult:
        """Compute factor overlap between two strategies."""
        factors_s1: Dict[str, float] = {}
        factors_s2: Dict[str, float] = {}

        if self._strategy_exposure:
            p1 = self._strategy_exposure.get_profile(s1)
            p2 = self._strategy_exposure.get_profile(s2)
            if p1:
                factors_s1 = {k: abs(v.exposure) for k, v in p1.factor_exposures.items()}
            if p2:
                factors_s2 = {k: abs(v.exposure) for k, v in p2.factor_exposures.items()}

        all_factors = set(factors_s1.keys()) | set(factors_s2.keys())
        if not all_factors:
            return FactorOverlapResult(
                strategy_a=s1, strategy_b=s2,
                overlap_score=0.0,
                dominant_factors=[],
                severity="NONE",
            )

        overlaps = {}
        dominant = []
        for f in all_factors:
            e1 = factors_s1.get(f, 0)
            e2 = factors_s2.get(f, 0)
            if e1 > 0 or e2 > 0:
                overlap = 1.0 - abs(e1 - e2) / max(e1, e2) if max(e1, e2) > 0 else 0
                overlaps[f] = overlap
                if overlap > 0.5:
                    dominant.append(f)

        score = sum(overlaps.values()) / len(overlaps) if overlaps else 0.0
        severity = "HIGH" if score > 0.7 else "MEDIUM" if score > 0.4 else "LOW"

        result = FactorOverlapResult(
            strategy_a=s1, strategy_b=s2,
            overlap_score=score,
            dominant_factors=dominant,
            severity=severity,
        )
        self._results.setdefault(s1, {})[s2] = result
        self._results.setdefault(s2, {})[s1] = result
        return result

    def get(self, s1: str, s2: str) -> Optional[FactorOverlapResult]:
        return self._results.get(s1, {}).get(s2)

    def get_all_high_overlaps(self) -> List[FactorOverlapResult]:
        """Return all pairs with HIGH factor overlap."""
        seen = set()
        high = []
        for s1, row in self._results.items():
            for s2, result in row.items():
                pair = tuple(sorted([s1, s2]))
                if pair not in seen and result.severity == "HIGH":
                    seen.add(pair)
                    high.append(result)
        return high
