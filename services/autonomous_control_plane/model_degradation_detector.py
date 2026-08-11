"""
Model Degradation Detector — Identifies models that are degrading.

Monitors multiple signals (performance, risk, drift, execution)
to detect when a model should be degraded or quarantined.
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    NONE = "none"
    EARLY_WARNING = "early_warning"
    WARNING = "warning"
    DEGRADED = "degraded"
    SEVERE = "severe"


class ModelDegradationDetector:
    """
    Detects when a production model is degrading and needs intervention.

    Monitors:
    - Performance metrics relative to baseline
    - Risk limit breaches
    - Execution quality degradation
    - Data quality issues
    - Model drift
    """

    def __init__(self):
        self._degradation_signals: dict[str, dict] = {}
        self._degradation_history: dict[str, list[dict]] = {}

    def evaluate(
        self,
        model_id: str,
        performance_ratio: float = 1.0,
        risk_breach: bool = False,
        execution_degraded: bool = False,
        data_quality_low: bool = False,
        drift_detected: bool = False,
    ) -> tuple[DegradationLevel, list[str]]:
        """
        Evaluate degradation signals for a model.

        Returns (level, triggered_signals).
        """
        signals = []
        severity = 0

        if performance_ratio < 0.5:
            signals.append("performance_critical")
            severity += 3
        elif performance_ratio < 0.8:
            signals.append("performance_declining")
            severity += 1

        if risk_breach:
            signals.append("risk_breach")
            severity += 3

        if execution_degraded:
            signals.append("execution_degraded")
            severity += 1

        if data_quality_low:
            signals.append("data_quality_low")
            severity += 1

        if drift_detected:
            signals.append("drift_detected")
            severity += 2

        if severity >= 6:
            level = DegradationLevel.SEVERE
        elif severity >= 3:
            level = DegradationLevel.DEGRADED
        elif severity >= 2:
            level = DegradationLevel.WARNING
        elif severity >= 1:
            level = DegradationLevel.EARLY_WARNING
        else:
            level = DegradationLevel.NONE

        # Record
        self._degradation_signals[model_id] = {
            "level": level.value,
            "signals": signals,
            "severity": severity,
            "timestamp": time.time(),
        }
        self._degradation_history.setdefault(model_id, []).append(self._degradation_signals[model_id])

        if level in (DegradationLevel.DEGRADED, DegradationLevel.SEVERE):
            logger.warning("Model %s degradation: %s (signals: %s)", model_id, level.value, signals)

        return level, signals

    def is_degraded(self, model_id: str) -> bool:
        signals = self._degradation_signals.get(model_id, {})
        level = DegradationLevel(signals.get("level", "none"))
        return level in (DegradationLevel.DEGRADED, DegradationLevel.SEVERE)

    def stats(self) -> dict:
        return {
            "models_tracked": len(self._degradation_signals),
            "degraded": len([s for s in self._degradation_signals.values() if s.get("level") in ("degraded", "severe")]),
            "warnings": len([s for s in self._degradation_signals.values() if s.get("level") == "warning"]),
        }
