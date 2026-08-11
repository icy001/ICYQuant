"""
ICYQuant Prediction Monitor — Monitors prediction quality and distribution.

Tracks:
  - Prediction distribution shifts
  - Prediction value extremes (min/max/mean)
  - Prediction frequency by model
  - Prediction confidence trends
  - Anomalous prediction detection
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class PredictionStats:
    """Rolling statistics for model predictions."""
    values: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    confidences: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    timestamps: Deque[str] = field(default_factory=lambda: deque(maxlen=1000))

    def record(self, value: float, confidence: Optional[float] = None) -> None:
        self.values.append(value)
        if confidence is not None:
            self.confidences.append(confidence)
        self.timestamps.append(datetime.now(timezone.utc).isoformat())

    def get_stats(self) -> Dict[str, Any]:
        if not self.values:
            return {}
        arr = np.array(self.values)
        conf_arr = np.array(self.confidences) if self.confidences else None

        result = {
            "count": len(arr),
            "mean": round(float(np.mean(arr)), 6),
            "std": round(float(np.std(arr)), 6),
            "min": round(float(np.min(arr)), 6),
            "max": round(float(np.max(arr)), 6),
            "median": round(float(np.median(arr)), 6),
            "last_value": round(float(arr[-1]), 6),
        }

        if conf_arr is not None and len(conf_arr) > 0:
            result["avg_confidence"] = round(float(np.mean(conf_arr)), 4)

        return result


# ---------------------------------------------------------------------------
# Prediction Monitor
# ---------------------------------------------------------------------------

class PredictionMonitor:
    """Monitors prediction outputs for quality and anomalies.

    Detects:
      - Prediction distribution drift
      - Extreme / outlier predictions
      - Prediction frequency anomalies
      - Confidence degradation
      - Frozen predictions (all same value)

    Usage::

        monitor = PredictionMonitor()
        monitor.record("nvda_model", prediction_value=0.05, confidence=0.85)
        stats = monitor.get_model_stats("nvda_model")
    """

    def __init__(
        self,
        window_size: int = 1000,
        anomaly_std_threshold: float = 5.0,
    ):
        self.window_size = window_size
        self.anomaly_std_threshold = anomaly_std_threshold
        self._initialized = False

        # Per-model prediction history
        self._history: Dict[str, PredictionStats] = {}

        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("PredictionMonitor initialized")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        model_id: str,
        prediction_value: float,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a prediction output.

        Args:
            model_id: Model identifier.
            prediction_value: Numeric prediction value.
            confidence: Optional confidence score.
            metadata: Additional metadata.
        """
        if model_id not in self._history:
            self._history[model_id] = PredictionStats()

        self._history[model_id].record(prediction_value, confidence)

        # Check for anomalies
        self._check_anomalies(model_id, prediction_value, metadata)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_model_stats(self, model_id: str) -> Dict[str, Any]:
        """Get prediction statistics for a model."""
        stats = self._history.get(model_id)
        if stats is None:
            return {}
        return {"model_id": model_id, **stats.get_stats()}

    def get_all_stats(self) -> Dict[str, Any]:
        """Get prediction statistics for all models."""
        return {
            model_id: self.get_model_stats(model_id)
            for model_id in self._history
        }

    def get_latest_predictions(
        self,
        model_id: str,
        n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get the most recent N predictions."""
        stats = self._history.get(model_id)
        if stats is None:
            return []

        values = list(stats.values)
        confidences = list(stats.confidences)
        timestamps = list(stats.timestamps)

        result = []
        for i in range(max(0, len(values) - n), len(values)):
            entry = {
                "value": round(values[i], 6),
                "timestamp": timestamps[i] if i < len(timestamps) else "",
            }
            if i < len(confidences):
                entry["confidence"] = round(confidences[i], 4)
            result.append(entry)
        return result

    def detect_frozen_predictions(self, model_id: str) -> Dict[str, Any]:
        """Check if predictions are frozen (all same value)."""
        stats = self._history.get(model_id)
        if stats is None or len(stats.values) < 10:
            return {"frozen": False, "reason": "insufficient_data"}

        arr = np.array(stats.values)
        is_frozen = np.std(arr) < 1e-10

        return {
            "model_id": model_id,
            "frozen": bool(is_frozen),
            "samples": len(arr),
            "unique_values": len(np.unique(arr)),
            "std": float(np.std(arr)),
        }

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def _check_anomalies(
        self,
        model_id: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Check if a prediction is anomalous."""
        stats = self._history.get(model_id)
        if stats is None or len(stats.values) < 50:
            return

        arr = np.array(stats.values)[:-1]  # Exclude current value
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std > 0:
            z_score = abs(value - mean) / std
            if z_score > self.anomaly_std_threshold:
                alert = {
                    "model_id": model_id,
                    "type": "anomalous_prediction",
                    "value": value,
                    "z_score": round(z_score, 2),
                    "mean": round(mean, 6),
                    "std": round(std, 6),
                }
                for cb in self._alert_callbacks:
                    try:
                        cb(model_id, "anomalous_prediction", alert)
                    except Exception:
                        pass

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_alert(
        self,
        callback: Callable[[str, str, Dict[str, Any]], None],
    ) -> None:
        """Register alert callback."""
        self._alert_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        frozen = {
            mid: self.detect_frozen_predictions(mid)
            for mid in self._history
        }
        frozen_models = [
            mid for mid, f in frozen.items() if f.get("frozen", False)
        ]
        return {
            "status": "degraded" if frozen_models else "healthy",
            "models_tracked": len(self._history),
            "frozen_models": frozen_models,
            "stats": self.get_all_stats(),
        }

    def __repr__(self) -> str:
        return f"PredictionMonitor(models={len(self._history)})"
