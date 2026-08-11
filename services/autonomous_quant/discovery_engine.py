"""Discovery Engine — Core engine for autonomous market discovery.

Orchestrates the full discovery process: scan → detect → rank → task.
This is the primary entry point for the autonomous research pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .market_scanner import MarketScanner
from .anomaly_detector import AnomalyDetector
from .regime_detector import RegimeDetector
from .opportunity_detector import OpportunityDetector
from .hypothesis_generator import HypothesisGenerator

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Result of a discovery run."""

    discovery_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    observations: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    regimes: List[Dict[str, Any]] = field(default_factory=list)
    opportunities: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "discovery_id": self.discovery_id,
            "timestamp": self.timestamp.isoformat(),
            "observation_count": len(self.observations),
            "anomaly_count": len(self.anomalies),
            "regime_count": len(self.regimes),
            "opportunity_count": len(self.opportunities),
            "hypothesis_count": len(self.hypotheses),
            "opportunities": self.opportunities,
            "hypotheses": self.hypotheses,
        }


class DiscoveryEngine:
    """Discovery Engine — autonomous market research discovery.

    Core loop:
        Market Data → Scanner → Anomaly/Regime → Opportunity → Hypothesis

    The engine does NOT produce trading orders. It produces:
        - Market observations
        - Research opportunities
        - Testable hypotheses
    """

    def __init__(self) -> None:
        self.scanner = MarketScanner()
        self.anomaly_detector = AnomalyDetector()
        self.regime_detector = RegimeDetector()
        self.opportunity_detector = OpportunityDetector()
        self.hypothesis_generator = HypothesisGenerator()
        self._discoveries: List[DiscoveryResult] = []

    async def scan(
        self,
        universe: Optional[List[str]] = None,
    ) -> DiscoveryResult:
        """Run a complete discovery scan.

        Args:
            universe: Optional list of symbols to scan.

        Returns:
            DiscoveryResult with all findings.
        """
        discovery = DiscoveryResult(
            discovery_id=f"disc_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        )

        # Step 1: Market scan → observations
        scan_result = await self.scanner.scan(universe=universe)
        discovery.observations = scan_result.get("observations", [])

        if not discovery.observations:
            logger.info("No observations found in scan")
            self._discoveries.append(discovery)
            return discovery

        # Step 2: Anomaly detection
        anomaly_result = await self.anomaly_detector.detect(discovery.observations)
        discovery.anomalies = anomaly_result.get("anomalies", [])

        # Step 3: Regime detection
        regime_result = await self.regime_detector.detect(discovery.observations)
        discovery.regimes = regime_result.get("regimes", [])

        # Step 4: Opportunity detection
        opp_result = await self.opportunity_detector.detect(
            discovery.observations,
            anomalies=discovery.anomalies,
            regimes=discovery.regimes,
        )
        discovery.opportunities = opp_result.get("opportunities", [])

        if not discovery.opportunities:
            logger.info("No opportunities detected")
            self._discoveries.append(discovery)
            return discovery

        # Step 5: Hypothesis generation
        hyp_result = await self.hypothesis_generator.generate(discovery.opportunities)
        discovery.hypotheses = hyp_result.get("hypotheses", [])

        self._discoveries.append(discovery)
        logger.info(
            "Discovery complete: %d obs, %d anomalies, %d regimes, %d opportunities, %d hypotheses",
            len(discovery.observations),
            len(discovery.anomalies),
            len(discovery.regimes),
            len(discovery.opportunities),
            len(discovery.hypotheses),
        )

        return discovery

    async def rank_opportunities(
        self,
        opportunities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Rank opportunities by priority/confidence."""
        return sorted(
            opportunities,
            key=lambda o: (
                o.get("priority_score", 0),
                o.get("confidence", 0),
            ),
            reverse=True,
        )

    async def create_research_task(
        self,
        opportunity: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a research task from an opportunity."""
        return {
            "task_id": f"task_{opportunity.get('opportunity_id', '')}",
            "opportunity": opportunity,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "discovery_research",
        }

    def get_last_discovery(self) -> Optional[DiscoveryResult]:
        """Get the most recent discovery result."""
        return self._discoveries[-1] if self._discoveries else None
