"""
Risk Overlap — Risk Factor Co-Movement Between Strategies

Identifies shared risk factor exposures that aren't captured by
simple return correlation. E.g., three different strategies all
exposed to "AI Growth Risk" — not 3 independent bets, but 1 big bet.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RiskCluster:
    cluster_id: str
    risk_factor: str
    strategies: List[str]
    total_exposure: float
    severity: str


class RiskOverlap:
    """
    Identifies risk factor clusters where multiple strategies
    share the same underlying risk.

    A "Risk Cluster" is NOT 3 independent bets — it's 1 large,
    concentrated risk position.
    """

    def __init__(
        self,
        overlap_id: Optional[str] = None,
        strategy_exposure=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.overlap_id = overlap_id or f"ro-{uuid.uuid4().hex[:12]}"
        self._strategy_exposure = strategy_exposure
        self.config = config or {}
        self._clusters: List[RiskCluster] = []

    def detect_clusters(self) -> List[RiskCluster]:
        """
        Detect risk clusters: strategies sharing same risk factors.

        Returns clusters where multiple strategies have significant
        exposure to the same risk factor.
        """
        self._clusters = []

        if not self._strategy_exposure:
            return self._clusters

        profiles = self._strategy_exposure.get_all_profiles()
        # Aggregate factor exposures across strategies
        factor_strategies: Dict[str, Dict[str, float]] = {}
        for sid, profile in profiles.items():
            for fname, fexp in profile.factor_exposures.items():
                if abs(fexp.exposure) > 0.2:
                    factor_strategies.setdefault(fname, {})[sid] = abs(fexp.exposure)

        for factor, exposures in factor_strategies.items():
            if len(exposures) >= 2:
                total_exp = sum(exposures.values())
                severity = "HIGH" if len(exposures) >= 3 else "MEDIUM"
                self._clusters.append(RiskCluster(
                    cluster_id=f"rc-{uuid.uuid4().hex[:8]}",
                    risk_factor=factor,
                    strategies=list(exposures.keys()),
                    total_exposure=total_exp,
                    severity=severity,
                ))

        return self._clusters

    def get_high_risk_clusters(self) -> List[RiskCluster]:
        return [c for c in self._clusters if c.severity == "HIGH"]

    def get_clusters_for_strategy(self, strategy_id: str) -> List[RiskCluster]:
        return [c for c in self._clusters if strategy_id in c.strategies]

    def get_effective_diversification(self) -> float:
        """
        Compute effective diversification ratio.

        If 3 strategies share 1 risk cluster, effective bets ≈ 1,
        not 3. This ratio informs true diversification.
        """
        if not self._strategy_exposure:
            return 1.0
        profiles = self._strategy_exposure.get_all_profiles()
        total_strategies = len(profiles)
        if total_strategies == 0:
            return 1.0

        clustered = set()
        for c in self._clusters:
            clustered.update(c.strategies)

        effective = len(set(profiles.keys()) - clustered) + len(self._clusters)
        return effective / total_strategies

    def get_summary(self) -> Dict[str, Any]:
        return {
            "overlap_id": self.overlap_id,
            "risk_clusters": len(self._clusters),
            "high_risk_clusters": len(self.get_high_risk_clusters()),
            "effective_diversification": self.get_effective_diversification(),
            "clusters": [
                {
                    "factor": c.risk_factor,
                    "strategies": c.strategies,
                    "severity": c.severity,
                }
                for c in self._clusters
            ],
        }
