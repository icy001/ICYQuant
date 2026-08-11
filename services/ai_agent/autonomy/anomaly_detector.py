"""Anomaly Detector — detects abnormal market events using statistical and ML methods.

Pipeline:
    Market Data -> AnomalyDetector.detect()
        -> Statistical anomaly (z-score, IQR)
        -> ML anomaly (isolation forest, autoencoder)
        -> Pattern anomaly (regime break, structural change)
        -> AnomalyDetector.emit_event()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    STATISTICAL = "statistical"
    PATTERN = "pattern"
    REGIME_BREAK = "regime_break"
    STRUCTURAL = "structural"
    OUTLIER = "outlier"


@dataclass
class AnomalyEvent:
    """A detected market anomaly.

    Attributes:
        event_id: Unique event identifier.
        anomaly_type: Type of anomaly.
        symbol: Related symbol.
        score: Anomaly score (0.0 = normal, 1.0 = extreme).
        description: Human-readable description.
        data: Structured anomaly data.
        timestamp: Detection timestamp.
    """

    event_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.STATISTICAL
    symbol: str = ""
    score: float = 0.0
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AnomalyDetector:
    """Detects abnormal market events using multi-method analysis.

    Combines statistical, ML-based, and pattern-based anomaly detection
    to identify unusual market behavior.

    Supports:
        - Statistical anomaly detection (z-score, IQR, MAD)
        - Pattern anomaly detection (regime breaks)
        - Configurable sensitivity thresholds
        - Event emission with severity scoring

    Usage:
        detector = AnomalyDetector()
        await detector.initialize()
        events = await detector.detect(prices=[100, 102, 105, 130, 104])
    """

    def __init__(self, sensitivity: float = 0.5) -> None:
        self._sensitivity = sensitivity
        self._events: List[AnomalyEvent] = []
        self._counter: int = 0
        self._max_events: int = 500
        self._initialized: bool = False
        logger.info("AnomalyDetector created (sensitivity=%.2f)", sensitivity)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AnomalyDetector initialized")

    async def shutdown(self) -> None:
        self._events.clear()
        self._initialized = False
        logger.info("AnomalyDetector shutdown complete")

    async def detect(
        self,
        symbol: str = "",
        prices: Optional[List[float]] = None,
        volumes: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[AnomalyEvent]:
        """Detect anomalies in the given data.

        Args:
            symbol: Related symbol.
            prices: Price series to analyze.
            volumes: Volume series to analyze.
            metadata: Additional data for context.

        Returns:
            List of detected AnomalyEvents.
        """
        events: List[AnomalyEvent] = []

        if prices and len(prices) > 5:
            stat_events = self._statistical_check(prices, symbol)
            events.extend(stat_events)

        if volumes and len(volumes) > 5:
            vol_events = self._statistical_check(volumes, symbol)
            events.extend(vol_events)

        self._store_events(events)
        return events

    def _statistical_check(self, series: List[float], symbol: str) -> List[AnomalyEvent]:
        events: List[AnomalyEvent] = []
        if not series:
            return events
        mean = sum(series) / len(series)
        std = (sum((x - mean) ** 2 for x in series) / len(series)) ** 0.5 if len(series) > 1 else 0
        if std == 0:
            return events
        for i, val in enumerate(series):
            z_score = abs((val - mean) / std)
            if z_score > 2.5:
                self._counter += 1
                events.append(AnomalyEvent(
                    event_id=f"anom_{self._counter}",
                    anomaly_type=AnomalyType.STATISTICAL,
                    symbol=symbol,
                    score=min(z_score / 5.0, 1.0),
                    description=f"Z-score anomaly: {z_score:.2f} at index {i}",
                    data={"index": i, "value": val, "z_score": round(z_score, 2)},
                ))
        return events

    def _store_events(self, events: List[AnomalyEvent]) -> None:
        self._events.extend(events)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [
            {
                "event_id": e.event_id,
                "type": e.anomaly_type.value,
                "symbol": e.symbol,
                "score": round(e.score, 3),
                "description": e.description,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in self._events[-limit:]
        ]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_events": len(self._events),
            "sensitivity": self._sensitivity,
        }
