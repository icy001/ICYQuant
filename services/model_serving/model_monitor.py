"""
ICYQuant Model Monitor — Comprehensive model health and performance monitor.

Monitors deployed models for:
  - Load state and runtime health
  - Inference error rates and latency
  - Memory usage and resource consumption
  - Model staleness (time since last retrain)
  - Version lifecycle tracking
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .model_runtime import ModelRuntime
    from .deployment_manager import DeploymentManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

class ModelHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STALE = "stale"            # Needs retraining
    DEPRECATED = "deprecated"


@dataclass
class ModelMetrics:
    """Aggregated model health metrics."""
    model_id: str
    version: str
    state: str
    health: ModelHealth = ModelHealth.HEALTHY
    loaded: bool = False
    inference_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    last_inference_at: Optional[str] = None
    last_trained_at: Optional[str] = None
    days_since_training: float = 0.0
    memory_estimate_mb: float = 0.0
    deployment_stage: str = ""
    recommendations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Model Monitor
# ---------------------------------------------------------------------------

class ModelMonitor:
    """Comprehensive model health and lifecycle monitor.

    Usage::

        monitor = ModelMonitor(runtime, deployment_manager)
        await monitor.initialize()
        health = await monitor.check_model("nvda_model")
    """

    def __init__(
        self,
        runtime: "ModelRuntime",
        deployment_manager: "DeploymentManager",
        staleness_days_threshold: int = 30,
    ):
        self.runtime = runtime
        self.deployment_manager = deployment_manager
        self.staleness_days_threshold = staleness_days_threshold
        self._initialized = False

        # Historical health tracking
        self._health_history: Dict[str, List[Dict[str, Any]]] = {}

        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("ModelMonitor initialized")

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def check_model(self, model_id: str) -> ModelMetrics:
        """Perform a comprehensive health check on a model.

        Checks:
          1. Runtime health (loaded, ready, unhealthy)
          2. Deployment stage
          3. Error rate and latency
          4. Model staleness
          5. Resource consumption

        Args:
            model_id: Model identifier.

        Returns:
            ModelMetrics with health status and recommendations.
        """
        metrics = ModelMetrics(
            model_id=model_id,
            version="unknown",
            state="unknown",
        )

        try:
            # 1. Runtime info
            runtime_info = self.runtime.get_model_info(model_id, "production")
            if runtime_info:
                metrics.loaded = True
                metrics.version = runtime_info["version"]
                metrics.state = runtime_info["state"]
                metrics.inference_count = runtime_info["inference_count"]
                metrics.avg_latency_ms = runtime_info["avg_latency_ms"]
                metrics.error_rate = runtime_info["error_rate"]
            else:
                # Try any loaded version
                loaded = self.runtime.list_models()
                for m in loaded:
                    if m["model_id"] == model_id:
                        info = self.runtime.get_model_info(model_id, m["version"])
                        if info:
                            metrics.loaded = True
                            metrics.version = info["version"]
                            metrics.state = info["state"]
                        break

            # 2. Deployment info
            deployment = self.deployment_manager.get_production(model_id)
            if deployment:
                metrics.deployment_stage = deployment.state.value

            # 3. Health assessment
            metrics.health = await self._assess_health(metrics)

            # 4. Recommendations
            metrics.recommendations = self._generate_recommendations(metrics)

            # Record history
            self._record_health(metrics)

        except Exception as exc:
            metrics.health = ModelHealth.UNHEALTHY
            metrics.recommendations = [f"Health check failed: {exc}"]
            logger.exception("Health check failed for %s", model_id)

        return metrics

    async def check_all(self) -> Dict[str, ModelMetrics]:
        """Check all models in the system."""
        results: Dict[str, ModelMetrics] = {}

        # Check loaded models
        loaded = self.runtime.list_models()
        model_ids = set(m["model_id"] for m in loaded)

        # Also check deployed models
        for mid in self.deployment_manager._production:
            model_ids.add(mid)
        for mid in self.deployment_manager._canaries:
            model_ids.add(mid)

        for model_id in model_ids:
            results[model_id] = await self.check_model(model_id)

        return results

    async def _assess_health(self, metrics: ModelMetrics) -> ModelHealth:
        """Assess overall model health."""
        reasons = []

        # Not loaded
        if not metrics.loaded:
            return ModelHealth.UNHEALTHY

        # Runtime state
        if metrics.state == "unhealthy":
            return ModelHealth.UNHEALTHY

        # High error rate
        if metrics.error_rate > 0.10:
            reasons.append(f"high_error_rate={metrics.error_rate:.4f}")

        # Stale model
        if metrics.days_since_training > self.staleness_days_threshold:
            reasons.append(f"stale={metrics.days_since_training:.0f}d")

        if reasons:
            return ModelHealth.STALE if "stale" in reasons[0] else ModelHealth.DEGRADED

        return ModelHealth.HEALTHY

    def _generate_recommendations(self, metrics: ModelMetrics) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        if not metrics.loaded:
            recs.append("Model is not loaded — trigger deployment")
            return recs

        if metrics.state == "unhealthy":
            recs.append("Model is unhealthy — restart or rollback")
            return recs

        if metrics.error_rate > 0.05:
            recs.append(f"Error rate {metrics.error_rate:.2%} is high — investigate")

        if metrics.avg_latency_ms > 500:
            recs.append(f"High latency {metrics.avg_latency_ms:.0f}ms — optimize model")

        if metrics.days_since_training > self.staleness_days_threshold:
            recs.append(f"Model is {metrics.days_since_training:.0f}d old — consider retraining")

        if not recs:
            recs.append("Model is healthy — no action needed")

        return recs

    def _record_health(self, metrics: ModelMetrics) -> None:
        """Record health snapshot."""
        if metrics.model_id not in self._health_history:
            self._health_history[metrics.model_id] = []

        self._health_history[metrics.model_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": metrics.health.value,
            "error_rate": metrics.error_rate,
            "avg_latency_ms": metrics.avg_latency_ms,
        })

        # Keep last 100 records
        self._health_history[metrics.model_id] = (
            self._health_history[metrics.model_id][-100:]
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_health_history(self, model_id: str) -> List[Dict[str, Any]]:
        """Get historical health records for a model."""
        return self._health_history.get(model_id, [])

    def get_summary(self) -> Dict[str, Any]:
        """Get a high-level health summary."""
        healthy = 0
        degraded = 0
        unhealthy = 0

        for model_id, history in self._health_history.items():
            if history:
                last = history[-1]["health"]
                if last == "healthy":
                    healthy += 1
                elif last == "degraded":
                    degraded += 1
                else:
                    unhealthy += 1

        return {
            "total_models": healthy + degraded + unhealthy,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "health_ratio": round(
                healthy / max(healthy + degraded + unhealthy, 1), 4
            ),
        }

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_alert(
        self,
        callback: Callable[[str, str, Dict[str, Any]], None],
    ) -> None:
        self._alert_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "summary": self.get_summary(),
        }

    def __repr__(self) -> str:
        return f"ModelMonitor(models={len(self._health_history)})"
