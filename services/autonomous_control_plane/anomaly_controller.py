"""
Anomaly Controller — Detects and responds to system anomalies.

Monitors for anomalous patterns that could indicate problems before
they become incidents.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AnomalyController:
    """
    Detects and responds to system anomalies.

    Proactive anomaly detection to catch issues before they escalate
    to incidents requiring circuit breakers or kill switches.
    """

    def __init__(self, incident_manager=None):
        self._incident_manager = incident_manager
        self._anomalies: list[dict] = []
        self._detection_count = 0

    async def detect(
        self,
        anomaly_type: str,
        description: str,
        severity: str = "warning",
        context: Optional[dict] = None,
    ) -> Optional[str]:
        """Detect an anomaly and optionally create an incident."""
        self._detection_count += 1
        anomaly = {
            "type": anomaly_type,
            "description": description,
            "severity": severity,
            "context": context or {},
            "detected_at": time.time(),
        }
        self._anomalies.append(anomaly)

        logger.warning("Anomaly detected: %s (%s)", anomaly_type, severity)

        # Auto-escalate critical anomalies to incidents
        if severity in ("critical", "major") and self._incident_manager:
            return await self._incident_manager.create_incident(
                anomaly_type, description, severity, context
            )

        return None

    def recent_anomalies(self, since_seconds: int = 3600) -> list[dict]:
        """Get anomalies from the last N seconds."""
        cutoff = time.time() - since_seconds
        return [a for a in self._anomalies if a["detected_at"] >= cutoff]

    def stats(self) -> dict:
        return {
            "detections_total": self._detection_count,
            "recent_total": len(self.recent_anomalies()),
        }
