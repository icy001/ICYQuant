"""Resource Predictor — forecasts future resource demand.

The :class:`ResourcePredictor` analyzes current load and historical patterns
to forecast future capacity needs.  Supports simple moving-average and
trend-based prediction with configurable lookahead windows.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


@dataclass
class PredictionResult:
    """Predicted resource demand for a future time window."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    forecast_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10))
    cpu_cores: float = 0.0
    memory_mb: float = 0.0
    gpu_units: float = 0.0
    job_count: int = 0
    confidence: float = 0.5
    trend: str = "stable"  # rising / stable / falling


class ResourcePredictor:
    """Predicts future resource demand based on historical patterns.

    Usage::

        predictor = ResourcePredictor()
        # Record current usage
        predictor.record_usage(cpu=45.0, memory_mb=16000, job_count=12)
        # Predict 30 minutes ahead
        result = predictor.predict(lookahead_minutes=30)
    """

    def __init__(self, max_history: int = 1440) -> None:
        """max_history: maximum data points to retain (e.g., 1440 = 24h at 1-min intervals)."""
        self._lock = threading.RLock()
        self._max_history = max_history

        # History: list of (timestamp, cpu, memory, gpu, job_count)
        self._history: List[tuple] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_usage(
        self, cpu: float, memory_mb: float,
        gpu: float = 0.0, job_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._history.append((now, cpu, memory_mb, gpu, job_count))
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, lookahead_minutes: int = 10) -> PredictionResult:
        """Predict resource demand *lookahead_minutes* into the future."""
        with self._lock:
            if len(self._history) < 5:
                return PredictionResult(confidence=0.1, trend="stable")

            # Simple moving average of last N points
            window = min(len(self._history), 60)
            recent = self._history[-window:]

            cpu_avg = sum(r[1] for r in recent) / len(recent)
            mem_avg = sum(r[2] for r in recent) / len(recent)
            gpu_avg = sum(r[3] for r in recent) / len(recent)
            job_avg = sum(r[4] for r in recent) / len(recent)

            # Trend detection: compare first half vs second half
            half = window // 2
            if half >= 3:
                first_half_cpu = sum(r[1] for r in recent[:half]) / half
                second_half_cpu = sum(r[1] for r in recent[half:]) / (window - half)
                diff_pct = (second_half_cpu - first_half_cpu) / max(first_half_cpu, 0.01)
                if diff_pct > 0.1:
                    trend = "rising"
                elif diff_pct < -0.1:
                    trend = "falling"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            confidence = min(1.0, len(self._history) / 100.0)

            return PredictionResult(
                forecast_at=datetime.now(timezone.utc) + timedelta(minutes=lookahead_minutes),
                cpu_cores=cpu_avg,
                memory_mb=mem_avg,
                gpu_units=gpu_avg,
                job_count=int(job_avg),
                confidence=confidence,
                trend=trend,
            )

    def capacity_forecast(self, total_cpu: float, total_memory_mb: float,
                          lookahead_minutes: int = 30) -> Dict[str, Any]:
        """Forecast capacity headroom."""
        pred = self.predict(lookahead_minutes)
        return {
            "forecast": pred,
            "cpu_headroom_pct": max(0.0, (1 - pred.cpu_cores / max(total_cpu, 0.01)) * 100),
            "memory_headroom_pct": max(0.0, (1 - pred.memory_mb / max(total_memory_mb, 0.01)) * 100),
            "needs_scale_out": pred.cpu_cores > total_cpu * 0.8,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self, minutes: int = 60) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        with self._lock:
            return [
                {
                    "timestamp": ts.isoformat(),
                    "cpu": cpu, "memory_mb": mem,
                    "gpu": gpu, "job_count": jobs,
                }
                for ts, cpu, mem, gpu, jobs in self._history
                if ts >= cutoff
            ]

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "history_points": len(self._history),
                "max_history": self._max_history,
                "latest": self._history[-1] if self._history else None,
            }
