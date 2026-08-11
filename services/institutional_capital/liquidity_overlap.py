"""
Liquidity Overlap — Detect Strategies Competing for Same Liquidity

Multiple strategies buying/selling the same assets or same sectors
may compete for the same liquidity pool, causing:
- Increased market impact
- Worse execution prices
- Slippage that compound when strategies trade simultaneously
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LiquidityOverlapResult:
    strategy_a: str
    strategy_b: str
    overlap_score: float
    shared_assets: List[str] = field(default_factory=list)
    shared_sectors: List[str] = field(default_factory=list)
    severity: str = "NONE"


class LiquidityOverlap:
    """
    Detects strategies competing for the same liquidity.

    High liquidity overlap → increased execution risk when
    both strategies are active simultaneously.
    """

    def __init__(
        self,
        overlap_id: Optional[str] = None,
        strategy_exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.overlap_id = overlap_id or f"lo-{uuid.uuid4().hex[:12]}"
        self._strategy_exposure = strategy_exposure
        self.config = config or {}
        self._strategy_sectors: Dict[str, Dict[str, float]] = {}
        self._strategy_assets: Dict[str, Set[str]] = {}
        self._results: Dict[str, Dict[str, LiquidityOverlapResult]] = {}

    def set_strategy_sectors(self, strategy_id: str, sectors: Dict[str, float]) -> None:
        self._strategy_sectors[strategy_id] = sectors

    def set_strategy_assets(self, strategy_id: str, assets: Set[str]) -> None:
        self._strategy_assets[strategy_id] = assets

    def compute(self, s1: str, s2: str) -> LiquidityOverlapResult:
        """Compute liquidity overlap between two strategies."""
        sectors1 = self._strategy_sectors.get(s1, {})
        sectors2 = self._strategy_sectors.get(s2, {})
        assets1 = self._strategy_assets.get(s1, set())
        assets2 = self._strategy_assets.get(s2, set())

        # Asset-level overlap
        shared_assets = list(assets1 & assets2)
        asset_overlap = len(shared_assets) / max(1, len(assets1 | assets2))

        # Sector-level overlap
        shared_sectors = [s for s in set(sectors1.keys()) & set(sectors2.keys())]
        sector_overlap = 0.0
        for s in shared_sectors:
            w1 = sectors1.get(s, 0)
            w2 = sectors2.get(s, 0)
            sector_overlap += min(w1, w2)

        # Composite score
        score = 0.6 * asset_overlap + 0.4 * sector_overlap
        severity = "HIGH" if score > 0.5 else "MEDIUM" if score > 0.25 else "LOW"

        result = LiquidityOverlapResult(
            strategy_a=s1, strategy_b=s2,
            overlap_score=score,
            shared_assets=shared_assets[:20],
            shared_sectors=shared_sectors,
            severity=severity,
        )
        self._results.setdefault(s1, {})[s2] = result
        self._results.setdefault(s2, {})[s1] = result
        return result

    def detect_liquidity_clusters(self) -> List[Dict[str, Any]]:
        """Detect groups of strategies competing for same liquidity."""
        clusters = []
        for s1, row in self._results.items():
            for s2, result in row.items():
                if s1 < s2 and result.severity == "HIGH":
                    clusters.append({
                        "strategies": [s1, s2],
                        "score": result.overlap_score,
                        "shared_assets": result.shared_assets[:5],
                    })
        return sorted(clusters, key=lambda x: -x["score"])

    def get(self, s1: str, s2: str) -> Optional[LiquidityOverlapResult]:
        return self._results.get(s1, {}).get(s2)
