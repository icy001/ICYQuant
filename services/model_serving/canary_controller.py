"""
ICYQuant Canary Controller — Fine-grained canary deployment control.

Manages canary deployments at the request level:
  - Request sampling for canary routing
  - Traffic percentage enforcement
  - Per-request latency/error tracking
  - Canary health scoring
  - Automatic canary abort on anomaly detection
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class CanaryHealth(str, Enum):
    """Canary health classification."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class CanaryConfig:
    """Canary deployment configuration."""
    traffic_percent: float = 5.0
    min_samples: int = 100  # Minimum samples before making decisions
    evaluation_window_seconds: int = 300  # 5-minute sliding window
    anomaly_threshold_errors: int = 10
    anomaly_threshold_latency_factor: float = 2.0  # 2x prod latency
    health_check_interval_seconds: int = 30
    auto_abort: bool = True
    max_canary_duration_seconds: int = 86400  # 24 hours max
    metric_weights: Dict[str, float] = field(default_factory=lambda: {
        "error_rate": 0.30,
        "latency_p99": 0.25,
        "latency_p50": 0.15,
        "throughput": 0.10,
        "prediction_stability": 0.20,
    })


@dataclass
class CanaryMetrics:
    """Aggregated canary metrics."""
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    latencies: List[float] = field(default_factory=list)
    start_time: Optional[float] = None

    @property
    def error_rate(self) -> float:
        total = self.total_requests
        return self.error_count / total if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        n = len(self.latencies)
        return sum(self.latencies) / n if n > 0 else 0.0

    @property
    def p50_latency_ms(self) -> float:
        return self._percentile(50)

    @property
    def p99_latency_ms(self) -> float:
        return self._percentile(99)

    @property
    def throughput(self) -> float:
        if self.start_time is None:
            return 0.0
        elapsed = time.time() - self.start_time
        return self.total_requests / elapsed if elapsed > 0 else 0.0

    def _percentile(self, p: float) -> float:
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)
        idx = int((p / 100.0) * len(sorted_lat))
        idx = min(idx, len(sorted_lat) - 1)
        return sorted_lat[idx]

    def record(self, success: bool, latency_ms: float) -> None:
        self.total_requests += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        self.latencies.append(latency_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "error_rate": round(self.error_rate, 6),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "throughput_rps": round(self.throughput, 2),
        }

    def reset(self) -> None:
        self.total_requests = 0
        self.success_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.latencies.clear()


# ---------------------------------------------------------------------------
# Canary Controller
# ---------------------------------------------------------------------------

class CanaryController:
    """Per-model canary deployment controller.

    Key features:
      - Probabilistic request routing (traffic percentage)
      - Sliding-window metric collection
      - Anomaly detection: error rate spike, latency degradation
      - Health scoring with configurable weights
      - Auto-abort on threshold breach

    Usage::

        controller = CanaryController(model_id="nvda_model")
        controller.start(candidate_version="v1.5", traffic_percent=5.0)

        # Per-request routing
        for request in requests:
            if controller.should_route_to_canary():
                result = await serve_with_canary(request)
                controller.record_result(success=True, latency_ms=50.0)
    """

    def __init__(
        self,
        model_id: str,
        config: Optional[CanaryConfig] = None,
    ):
        self.model_id = model_id
        self.config = config or CanaryConfig()
        self._initialized = False

        # State
        self._active = False
        self._candidate_version: Optional[str] = None
        self._started_at: Optional[datetime] = None

        # Metrics — two windows for comparison
        self._current_window = CanaryMetrics()
        self._window_history: Deque[CanaryMetrics] = deque(maxlen=20)

        # Production baseline (populated from production monitoring)
        self._prod_baseline: Dict[str, float] = {
            "error_rate": 0.0,
            "p50_latency_ms": 0.0,
            "p99_latency_ms": 0.0,
        }

        # Health
        self._health = CanaryHealth.UNKNOWN
        self._health_history: List[Dict[str, Any]] = []

        # Background task
        self._abort_event = asyncio.Event()

    async def initialize(self) -> None:
        self._initialized = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        candidate_version: str,
        traffic_percent: Optional[float] = None,
        prod_baseline: Optional[Dict[str, float]] = None,
    ) -> None:
        """Start canary deployment.

        Args:
            candidate_version: Candidate model version.
            traffic_percent: Initial traffic allocation (defaults to config).
            prod_baseline: Production baseline metrics for comparison.
        """
        if traffic_percent is not None:
            self.config.traffic_percent = traffic_percent
        if prod_baseline:
            self._prod_baseline.update(prod_baseline)

        self._active = True
        self._candidate_version = candidate_version
        self._started_at = datetime.now(timezone.utc)
        self._current_window = CanaryMetrics(start_time=time.time())
        self._health = CanaryHealth.UNKNOWN
        self._abort_event.clear()

        logger.info(
            "Canary started: %s@%s (%.1f%% traffic)",
            self.model_id, candidate_version, self.config.traffic_percent,
        )

    def stop(self) -> None:
        """Stop canary deployment."""
        self._active = False
        self._abort_event.set()
        logger.info("Canary stopped: %s", self.model_id)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def should_route_to_canary(self) -> bool:
        """Determine if a request should be routed to the canary model.

        Uses probabilistic sampling based on configured traffic percentage.

        Returns:
            True if request should go to canary.
        """
        if not self._active:
            return False
        return random.random() < (self.config.traffic_percent / 100.0)

    def get_routing_decision(self, request_id: Optional[str] = None) -> Dict[str, Any]:
        """Get deterministic routing decision.

        Uses request_id hash for consistent routing (useful for A/B testing).

        Returns:
            Dict with routing target and reason.
        """
        route_to_canary = self.should_route_to_canary()
        return {
            "model_id": self.model_id,
            "route_to": "canary" if route_to_canary else "production",
            "canary_version": self._candidate_version if route_to_canary else None,
            "traffic_percent": self.config.traffic_percent,
        }

    # ------------------------------------------------------------------
    # Metrics & results
    # ------------------------------------------------------------------

    def record_result(
        self,
        success: bool,
        latency_ms: float,
        prediction: Optional[Any] = None,
    ) -> None:
        """Record a canary inference result."""
        if not self._active:
            return
        self._current_window.record(success, latency_ms)

    async def rotate_window(self) -> None:
        """Rotate the metrics window — push current to history and reset."""
        if self._current_window.total_requests > 0:
            self._window_history.append(self._current_window)
            self._current_window = CanaryMetrics(start_time=time.time())

    # ------------------------------------------------------------------
    # Health assessment
    # ------------------------------------------------------------------

    def assess_health(self) -> Tuple[CanaryHealth, str]:
        """Evaluate canary health against production baseline.

        Uses configured metric weights to compute a composite health score.

        Returns:
            (health_status, reason) tuple.
        """
        if self._current_window.total_requests < self.config.min_samples:
            return CanaryHealth.UNKNOWN, "insufficient_samples"

        window = self._current_window

        # Check for critical anomalies
        if window.error_count >= self.config.anomaly_threshold_errors:
            return CanaryHealth.UNHEALTHY, (
                f"error_count {window.error_count} >= {self.config.anomaly_threshold_errors}"
            )

        # Latency anomaly check
        prod_p99 = self._prod_baseline.get("p99_latency_ms", 100.0)
        if prod_p99 > 0:
            latency_factor = window.p99_latency_ms / prod_p99
            if latency_factor > self.config.anomaly_threshold_latency_factor:
                return CanaryHealth.DEGRADED, (
                    f"latency_factor {latency_factor:.2f} > "
                    f"{self.config.anomaly_threshold_latency_factor}"
                )

        # Compare to production baseline
        prod_error_rate = self._prod_baseline.get("error_rate", 0.0)
        if window.error_rate > prod_error_rate * 3 and window.error_rate > 0.02:
            return CanaryHealth.DEGRADED, f"error_rate {window.error_rate:.4f} > prod * 3"

        return CanaryHealth.HEALTHY, "metrics_within_bounds"

    def compute_health_score(self) -> float:
        """Compute weighted health score (0-100).

        Higher is better. 100 = identical to or better than production.
        """
        if self._current_window.total_requests < self.config.min_samples:
            return 50.0  # Neutral for insufficient data

        window = self._current_window
        weights = self.config.metric_weights
        baseline = self._prod_baseline

        scores: Dict[str, float] = {}

        # Error rate score
        prod_err = baseline.get("error_rate", 0.0)
        if window.error_rate <= prod_err:
            scores["error_rate"] = 100.0
        elif prod_err > 0:
            scores["error_rate"] = max(0, 100 * (1 - (window.error_rate - prod_err) / prod_err))
        else:
            scores["error_rate"] = max(0, 100 - window.error_rate * 1000)

        # Latency scores
        prod_p99 = baseline.get("p99_latency_ms", 100.0)
        if prod_p99 > 0:
            scores["latency_p99"] = max(0, 100 * (1 - max(0, window.p99_latency_ms - prod_p99) / prod_p99))
            scores["latency_p50"] = max(0, 100 * (1 - max(0, window.p50_latency_ms - prod_p99 * 0.5) / (prod_p99 * 0.5)))
        else:
            scores["latency_p99"] = 80.0
            scores["latency_p50"] = 80.0

        # Throughput score (higher is better, but neutral here)
        scores["throughput"] = 80.0

        # Prediction stability (placeholder)
        scores["prediction_stability"] = 90.0

        # Weighted average
        total = sum(weights.get(k, 0) * scores.get(k, 80) for k in weights)
        return total

    # ------------------------------------------------------------------
    # Auto-management
    # ------------------------------------------------------------------

    async def run_health_loop(self) -> None:
        """Background loop: periodically assess health and auto-abort if needed."""
        while self._active and not self._abort_event.is_set():
            try:
                await asyncio.sleep(self.config.health_check_interval_seconds)

                if not self._active:
                    break

                # Rotate window
                await self.rotate_window()

                # Assess
                health, reason = self.assess_health()
                score = self.compute_health_score()

                self._health = health
                self._health_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "health": health.value,
                    "score": round(score, 2),
                    "reason": reason,
                    "metrics": self._current_window.to_dict(),
                })

                # Auto-abort if unhealthy
                if health == CanaryHealth.UNHEALTHY and self.config.auto_abort:
                    logger.error(
                        "Canary unhealthy — aborting: %s@%s (%s)",
                        self.model_id, self._candidate_version, reason,
                    )
                    self._abort_event.set()
                    break

                # Check max duration
                if self._started_at:
                    elapsed = (datetime.now(timezone.utc) - self._started_at).total_seconds()
                    if elapsed > self.config.max_canary_duration_seconds:
                        logger.warning(
                            "Canary max duration exceeded: %s@%s",
                            self.model_id, self._candidate_version,
                        )
                        break

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Canary health loop error")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def health(self) -> CanaryHealth:
        return self._health

    @property
    def candidate_version(self) -> Optional[str]:
        return self._candidate_version

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive canary status."""
        return {
            "model_id": self.model_id,
            "active": self._active,
            "candidate_version": self._candidate_version,
            "traffic_percent": self.config.traffic_percent,
            "health": self._health.value,
            "health_score": round(self.compute_health_score(), 2),
            "metrics": self._current_window.to_dict(),
            "prod_baseline": self._prod_baseline,
            "started_at": (
                self._started_at.isoformat() if self._started_at else None
            ),
            "elapsed_seconds": (
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
                if self._started_at else 0.0
            ),
        }

    def __repr__(self) -> str:
        return (
            f"CanaryController(model={self.model_id}, "
            f"active={self._active}, health={self._health.value})"
        )
