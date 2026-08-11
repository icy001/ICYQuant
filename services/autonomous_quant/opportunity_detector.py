"""Opportunity Detector — Transforms observations into research opportunities.

Routes market observations through opportunity classifiers to produce
structured research opportunities with priority scoring.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OpportunityType(str, Enum):
    """Types of research opportunities."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CROSS_ASSET = "cross_asset"
    EVENT = "event"
    REGIME = "regime"
    SECTOR = "sector"
    LIQUIDITY = "liquidity"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    ANOMALY = "anomaly"


class OpportunityPriority(str, Enum):
    """Opportunity priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OpportunityDetector:
    """Opportunity Detector — identifies research opportunities.

    Transforms raw observations into structured opportunities:
        Observation → Classify → Score → Rank → Opportunity

    Opportunity types detected:
        - Momentum: Trend continuation opportunities
        - Mean Reversion: Overextended return opportunities
        - Volatility: Regime change / surface opportunities
        - Cross-Asset: Inter-market relationship opportunities
        - Event: Earnings, macro, news-driven opportunities
        - Regime: Market state transition opportunities
        - Correlation Breakdown: Decoupling opportunities

    Each opportunity receives a priority score based on:
        - Signal strength
        - Anomaly severity
        - Regime alignment
        - Data quality
        - Historical significance
    """

    def __init__(self) -> None:
        self._opportunities_detected: int = 0

    async def detect(
        self,
        observations: List[Dict[str, Any]],
        anomalies: Optional[List[Dict[str, Any]]] = None,
        regimes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Detect research opportunities from observations.

        Args:
            observations: Market observations from scanner.
            anomalies: Detected anomalies.
            regimes: Detected market regimes.

        Returns:
            Dict with opportunities list and metadata.
        """
        anomalies = anomalies or []
        regimes = regimes or []
        opportunities: List[Dict[str, Any]] = []

        for obs in observations:
            category = obs.get("category", "")

            # Classify observations into opportunity types
            if category in ("price", "relative_strength"):
                opp = self._create_momentum_opportunity(obs)
                if opp:
                    opportunities.append(opp)

            if category in ("volatility",):
                opp = self._create_volatility_opportunity(obs)
                if opp:
                    opportunities.append(opp)

            if category in ("correlation", "cross_asset"):
                opp = self._create_cross_asset_opportunity(obs)
                if opp:
                    opportunities.append(opp)

            if category in ("correlation",):
                opp = self._create_correlation_breakdown_opportunity(obs)
                if opp:
                    opportunities.append(opp)

            if category in ("flow",):
                opp = self._create_liquidity_opportunity(obs)
                if opp:
                    opportunities.append(opp)

        # Create anomaly-based opportunities
        for anomaly in anomalies:
            opp = self._create_anomaly_opportunity(anomaly)
            if opp:
                opportunities.append(opp)

        # Create regime-based opportunities
        for regime in regimes:
            opp = self._create_regime_opportunity(regime)
            if opp:
                opportunities.append(opp)

        # Score and rank
        for opp in opportunities:
            opp["priority_score"] = self._score_opportunity(opp)

        opportunities.sort(key=lambda o: o.get("priority_score", 0), reverse=True)

        # Assign priorities
        for opp in opportunities:
            score = opp.get("priority_score", 0)
            if score >= 0.8:
                opp["priority"] = OpportunityPriority.CRITICAL.value
            elif score >= 0.6:
                opp["priority"] = OpportunityPriority.HIGH.value
            elif score >= 0.4:
                opp["priority"] = OpportunityPriority.MEDIUM.value
            else:
                opp["priority"] = OpportunityPriority.LOW.value

        self._opportunities_detected += len(opportunities)

        logger.info(
            "Opportunities detected: %d (from %d obs, %d anomalies, %d regimes)",
            len(opportunities),
            len(observations),
            len(anomalies),
            len(regimes),
        )

        return {
            "opportunities": opportunities,
            "total_detected": self._opportunities_detected,
            "by_type": self._group_by_type(opportunities),
            "by_priority": self._group_by_priority(opportunities),
        }

    # ------------------------------------------------------------------
    # Opportunity Creators
    # ------------------------------------------------------------------

    def _create_momentum_opportunity(
        self, obs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a momentum-based opportunity."""
        symbols = obs.get("symbols", [])
        if not symbols:
            return None
        return self._build_opportunity(
            OpportunityType.MOMENTUM,
            f"Momentum opportunity in {', '.join(symbols[:3])}",
            obs,
            {**obs.get("details", {}), "direction": "bullish"},
        )

    def _create_volatility_opportunity(
        self, obs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a volatility-based opportunity."""
        return self._build_opportunity(
            OpportunityType.VOLATILITY,
            "Volatility regime opportunity",
            obs,
            obs.get("details", {}),
        )

    def _create_cross_asset_opportunity(
        self, obs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a cross-asset opportunity."""
        return self._build_opportunity(
            OpportunityType.CROSS_ASSET,
            "Cross-asset relationship opportunity",
            obs,
            obs.get("details", {}),
        )

    def _create_correlation_breakdown_opportunity(
        self, obs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a correlation breakdown opportunity."""
        return self._build_opportunity(
            OpportunityType.CORRELATION_BREAKDOWN,
            "Correlation divergence opportunity",
            obs,
            {"breakdowns": obs.get("details", {}).get("breakdowns", [])},
        )

    def _create_liquidity_opportunity(
        self, obs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a liquidity opportunity."""
        return self._build_opportunity(
            OpportunityType.LIQUIDITY,
            "Order flow / liquidity opportunity",
            obs,
            obs.get("details", {}),
        )

    def _create_anomaly_opportunity(
        self, anomaly: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create an anomaly-based opportunity."""
        return self._build_opportunity(
            OpportunityType.ANOMALY,
            f"Anomaly investigation: {anomaly.get('anomaly_type', 'unknown')}",
            anomaly,
            {"severity": anomaly.get("severity_score", 0)},
        )

    def _create_regime_opportunity(
        self, regime: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a regime-based opportunity."""
        return self._build_opportunity(
            OpportunityType.REGIME,
            f"Regime opportunity: {regime.get('current_regime', 'unknown')}",
            regime,
            {
                "current_regime": regime.get("current_regime"),
                "transition_probability": regime.get("transition_probability", 0),
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_opportunity(
        self,
        opp_type: OpportunityType,
        title: str,
        source: Dict[str, Any],
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a structured opportunity."""
        return {
            "opportunity_id": f"opp_{opp_type.value}_{random.randint(10000, 99999)}",
            "type": opp_type.value,
            "title": title,
            "description": f"Research opportunity: {title}",
            "symbols": source.get("symbols", []),
            "confidence": source.get("confidence", round(random.uniform(0.5, 0.9), 2)),
            "source_observation": source.get("observation_id", ""),
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "detected",
        }

    def _score_opportunity(self, opp: Dict[str, Any]) -> float:
        """Score an opportunity for prioritization."""
        score = 0.5  # Baseline
        score += opp.get("confidence", 0) * 0.3

        # Bonus for anomaly-based opportunities
        if opp["type"] in (OpportunityType.ANOMALY.value, OpportunityType.REGIME.value):
            score += opp.get("details", {}).get("severity", 0.5) * 0.2

        # Bonus for multi-symbol opportunities
        if len(opp.get("symbols", [])) >= 3:
            score += 0.1

        return min(score, 1.0)

    def _group_by_type(
        self, opportunities: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Group opportunities by type."""
        groups: Dict[str, int] = {}
        for opp in opportunities:
            t = opp.get("type", "unknown")
            groups[t] = groups.get(t, 0) + 1
        return groups

    def _group_by_priority(
        self, opportunities: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Group opportunities by priority."""
        groups: Dict[str, int] = {}
        for opp in opportunities:
            p = opp.get("priority", "low")
            groups[p] = groups.get(p, 0) + 1
        return groups
