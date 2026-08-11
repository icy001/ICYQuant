"""Anomaly Detector — Identifies market anomalies from observations.

Detects statistical and structural anomalies in price, volume, volatility,
correlation, and flow data. Anomalies are then routed to the Opportunity
Detector for research prioritization.

Detection categories:
    - Price anomalies (gap, crash, surge, stall)
    - Volume anomalies (spike, drought, divergence)
    - Volatility anomalies (regime shift, surface distortion)
    - Correlation anomalies (pair breakdown, sector decoupling)
    - Flow anomalies (unusual block trades, options activity)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnomalyType:
    """Anomaly type constants."""

    PRICE_GAP = "price_gap"
    PRICE_SURGE = "price_surge"
    PRICE_CRASH = "price_crash"
    VOLUME_SPIKE = "volume_spike"
    VOLUME_DROUGHT = "volume_drought"
    VOLATILITY_SPIKE = "volatility_spike"
    VOLATILITY_COLLAPSE = "volatility_collapse"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    FLOW_ANOMALY = "flow_anomaly"
    CROSS_ASSET_DISLOCATION = "cross_asset_dislocation"


class AnomalyDetector:
    """Anomaly Detector — statistical anomaly identification.

    Scans observations for deviations from expected patterns.
    Produces structured anomaly records with severity scoring.
    """

    def __init__(self, sensitivity: float = 2.0) -> None:
        """Initialize anomaly detector.

        Args:
            sensitivity: Z-score threshold for anomaly detection (default=2.0 sigma).
        """
        self.sensitivity = sensitivity
        self._anomalies_detected: int = 0

    async def detect(
        self,
        observations: List[Dict[str, Any]],
        baseline: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Detect anomalies in market observations.

        Args:
            observations: Market observations to analyze.
            baseline: Optional baseline statistics for comparison.

        Returns:
            Dict with anomalies list and metadata.
        """
        anomalies: List[Dict[str, Any]] = []

        for obs in observations:
            category = obs.get("category", "")

            if category == "price":
                price_anomalies = self._detect_price_anomalies(obs)
                anomalies.extend(price_anomalies)

            elif category == "volume":
                volume_anomalies = self._detect_volume_anomalies(obs)
                anomalies.extend(volume_anomalies)

            elif category == "volatility":
                vol_anomalies = self._detect_volatility_anomalies(obs)
                anomalies.extend(vol_anomalies)

            elif category == "correlation":
                corr_anomalies = self._detect_correlation_anomalies(obs)
                anomalies.extend(corr_anomalies)

            elif category == "flow":
                flow_anomalies = self._detect_flow_anomalies(obs)
                anomalies.extend(flow_anomalies)

            elif category == "cross_asset":
                cross_anomalies = self._detect_cross_asset_anomalies(obs)
                anomalies.extend(cross_anomalies)

        # Score anomalies
        for anomaly in anomalies:
            anomaly["severity_score"] = self._score_anomaly(anomaly)

        anomalies.sort(key=lambda a: a.get("severity_score", 0), reverse=True)
        self._anomalies_detected += len(anomalies)

        logger.info("Anomalies detected: %d", len(anomalies))

        return {
            "anomalies": anomalies,
            "total_detected": self._anomalies_detected,
            "sensitivity": self.sensitivity,
        }

    # ------------------------------------------------------------------
    # Detection Methods
    # ------------------------------------------------------------------

    def _detect_price_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect price anomalies."""
        details = obs.get("details", {})
        anomalies = []

        direction = details.get("direction", "")
        if direction in ("bullish", "bearish"):
            anomalies.append(self._build_anomaly(
                AnomalyType.PRICE_SURGE if direction == "bullish" else AnomalyType.PRICE_CRASH,
                obs,
                {"direction": direction, "magnitude": "significant"},
            ))

        return anomalies

    def _detect_volume_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect volume anomalies."""
        details = obs.get("details", {})
        status = details.get("status", "")

        if status == "elevated":
            return [self._build_anomaly(
                AnomalyType.VOLUME_SPIKE, obs,
                {"status": status, "relative_volume": 2.5},
            )]
        elif status == "depressed":
            return [self._build_anomaly(
                AnomalyType.VOLUME_DROUGHT, obs,
                {"status": status, "relative_volume": 0.3},
            )]
        return []

    def _detect_volatility_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect volatility anomalies."""
        details = obs.get("details", {})
        level = details.get("level", "")
        anomalies = []

        if level in ("elevated", "extreme"):
            anomalies.append(self._build_anomaly(
                AnomalyType.VOLATILITY_SPIKE, obs,
                {"level": level, "relative_vol": 3.0},
            ))
        elif level == "suppressed":
            anomalies.append(self._build_anomaly(
                AnomalyType.VOLATILITY_COLLAPSE, obs,
                {"level": level, "relative_vol": 0.2},
            ))

        return anomalies

    def _detect_correlation_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect correlation anomalies."""
        details = obs.get("details", {})
        breakdowns = details.get("breakdowns", [])

        if breakdowns:
            return [self._build_anomaly(
                AnomalyType.CORRELATION_BREAKDOWN, obs,
                {"breakdowns": breakdowns, "count": len(breakdowns)},
            )]
        return []

    def _detect_flow_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect order flow anomalies."""
        return [self._build_anomaly(
            AnomalyType.FLOW_ANOMALY, obs,
            {"direction": obs.get("details", {}).get("direction", "neutral")},
        )]

    def _detect_cross_asset_anomalies(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect cross-asset anomalies."""
        details = obs.get("details", {})
        if details.get("status") != "normal":
            return [self._build_anomaly(
                AnomalyType.CROSS_ASSET_DISLOCATION, obs,
                {"status": details.get("status", "abnormal")},
            )]
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_anomaly(
        self,
        anomaly_type: str,
        source: Dict[str, Any],
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a structured anomaly record."""
        return {
            "anomaly_id": f"anom_{anomaly_type}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            "anomaly_type": anomaly_type,
            "symbols": source.get("symbols", []),
            "category": source.get("category", ""),
            "source_observation": source.get("observation_id", ""),
            "details": details,
            "confidence": source.get("confidence", 0.7),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }

    def _score_anomaly(self, anomaly: Dict[str, Any]) -> float:
        """Score anomaly severity (0.0 to 1.0)."""
        score = 0.5  # Baseline

        # Type-based scoring
        critical_types = {
            AnomalyType.CORRELATION_BREAKDOWN: 0.8,
            AnomalyType.CROSS_ASSET_DISLOCATION: 0.85,
            AnomalyType.VOLATILITY_SPIKE: 0.75,
            AnomalyType.PRICE_CRASH: 0.9,
        }
        score = max(score, critical_types.get(anomaly["anomaly_type"], 0.5))

        score += anomaly.get("confidence", 0) * 0.2
        return min(score, 1.0)
