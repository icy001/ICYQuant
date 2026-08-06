"""Model Deployment — deployment pipeline for research models.

Commit 11 Part 1.5: Manages the deployment lifecycle of research models
from staging to production, including canary and rollback strategies.

Architecture::

    Model Registry → Version → Artifact → Deployment → Serving

Deployment strategies:
    - Direct (immediate promotion)
    - Canary (gradual traffic shift)
    - Blue-Green (swap instances)
    - Shadow (mirror traffic for validation)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ModelDeploymentState(str, Enum):
    """Model deployment lifecycle states."""

    CREATED = "created"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    RUNNING = "running"
    CANARY = "canary"
    ROLLING_BACK = "rolling_back"
    STOPPED = "stopped"
    FAILED = "failed"


class DeploymentStrategy(str, Enum):
    """Deployment strategies."""

    DIRECT = "direct"
    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    SHADOW = "shadow"


class ModelDeployment:
    """Manages model deployment lifecycle.

    Handles deployment from registry to serving infrastructure with
    support for canary deployments, traffic splitting, and rollback.

    Usage::

        deployment = ModelDeployment(
            model_id="model-abc",
            version=3,
            strategy=DeploymentStrategy.CANARY,
        )
        await deployment.initialize()
        await deployment.deploy()
        await deployment.set_traffic_split(canary_percent=10)
        await deployment.promote_canary()
    """

    def __init__(
        self,
        model_id: str,
        version: int,
        strategy: DeploymentStrategy = DeploymentStrategy.DIRECT,
        *,
        deployment_id: Optional[str] = None,
        serving_endpoint: Optional[str] = None,
    ) -> None:
        self._id: str = deployment_id or f"dep-{uuid4().hex[:12]}"
        self._model_id: str = model_id
        self._version: int = version
        self._strategy: DeploymentStrategy = strategy
        self._serving_endpoint: str = serving_endpoint or f"/models/{model_id}/v{version}"
        self._state: ModelDeploymentState = ModelDeploymentState.CREATED

        self._created_at: datetime = datetime.now(timezone.utc)
        self._deployed_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None

        # Traffic management
        self._canary_percent: float = 0.0
        self._traffic_rules: Dict[str, float] = {}

        # Health & metrics
        self._health_status: str = "unknown"
        self._request_count: int = 0
        self._error_count: int = 0
        self._avg_latency_ms: float = 0.0

        # History
        self._events: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def state(self) -> ModelDeploymentState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == ModelDeploymentState.RUNNING

    @property
    def canary_percent(self) -> float:
        return self._canary_percent

    @property
    def error_rate(self) -> float:
        if self._request_count == 0:
            return 0.0
        return self._error_count / self._request_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize deployment."""
        logger.info("Initializing ModelDeployment [%s] %s v%d strategy=%s",
                     self._id, self._model_id, self._version, self._strategy.value)
        await asyncio.sleep(0.001)
        self._add_event("initialized")

    async def shutdown(self) -> None:
        """Stop deployment and clean up."""
        if self._state == ModelDeploymentState.RUNNING:
            await self.stop()
        self._add_event("shutdown")

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    async def deploy(self) -> None:
        """Deploy the model version."""
        if self._state != ModelDeploymentState.CREATED:
            raise RuntimeError(f"Cannot deploy from state: {self._state.value}")

        self._state = ModelDeploymentState.PREPARING
        self._add_event("preparing")
        logger.info("Preparing deployment [%s]...", self._id)

        await asyncio.sleep(0.01)  # simulate artifact download and setup

        self._state = ModelDeploymentState.DEPLOYING
        self._add_event("deploying")
        logger.info("Deploying [%s] via %s strategy...", self._id, self._strategy.value)

        await asyncio.sleep(0.01)  # simulate deployment

        self._state = ModelDeploymentState.RUNNING
        self._deployed_at = datetime.now(timezone.utc)
        self._health_status = "healthy"
        self._add_event("deployed")
        logger.info("Deployment complete [%s] at %s", self._id, self._serving_endpoint)

    async def stop(self) -> None:
        """Stop the deployment."""
        if self._state not in (ModelDeploymentState.RUNNING, ModelDeploymentState.CANARY):
            raise RuntimeError(f"Cannot stop from state: {self._state.value}")

        self._state = ModelDeploymentState.STOPPED
        self._stopped_at = datetime.now(timezone.utc)
        self._add_event("stopped")
        logger.info("Deployment stopped [%s]", self._id)

    # ------------------------------------------------------------------
    # Canary Deployment
    # ------------------------------------------------------------------

    async def set_traffic_split(self, canary_percent: float) -> None:
        """Set canary traffic percentage.

        Args:
            canary_percent: Percentage of traffic routed to this deployment (0-100).
        """
        if self._state not in (ModelDeploymentState.RUNNING, ModelDeploymentState.CANARY):
            raise RuntimeError(f"Cannot set traffic split from state: {self._state.value}")
        if not 0 <= canary_percent <= 100:
            raise ValueError("canary_percent must be between 0 and 100")

        self._canary_percent = canary_percent
        if canary_percent > 0 and canary_percent < 100:
            self._state = ModelDeploymentState.CANARY
        self._add_event(f"traffic_split:{canary_percent}%")
        logger.info("Traffic split set to %.1f%% for [%s]", canary_percent, self._id)

    async def promote_canary(self) -> None:
        """Promote canary to full production (100% traffic)."""
        if self._state != ModelDeploymentState.CANARY:
            raise RuntimeError(f"Not in canary state: {self._state.value}")

        await self.set_traffic_split(100.0)
        self._state = ModelDeploymentState.RUNNING
        self._add_event("promoted_to_full")
        logger.info("Canary promoted to full production [%s]", self._id)

    async def rollback(self) -> None:
        """Rollback the deployment."""
        if self._state not in (ModelDeploymentState.RUNNING, ModelDeploymentState.CANARY):
            raise RuntimeError(f"Cannot rollback from state: {self._state.value}")

        self._state = ModelDeploymentState.ROLLING_BACK
        self._add_event("rolling_back")
        logger.info("Rolling back deployment [%s]...", self._id)

        await asyncio.sleep(0.01)
        self._state = ModelDeploymentState.STOPPED
        self._stopped_at = datetime.now(timezone.utc)
        self._add_event("rolled_back")
        logger.info("Rollback complete [%s]", self._id)

    # ------------------------------------------------------------------
    # Health & Metrics
    # ------------------------------------------------------------------

    async def report_health(self, status: str) -> None:
        """Report deployment health status."""
        self._health_status = status
        if status == "unhealthy" and self._state == ModelDeploymentState.CANARY:
            logger.warning("Canary unhealthy, triggering rollback [%s]", self._id)
            await self.rollback()

    async def record_request(self, latency_ms: float, is_error: bool = False) -> None:
        """Record a serving request for metrics."""
        self._request_count += 1
        if is_error:
            self._error_count += 1
        # Exponential moving average for latency
        alpha = 0.1
        self._avg_latency_ms = alpha * latency_ms + (1 - alpha) * self._avg_latency_ms

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_event(self, event: str) -> None:
        """Record a deployment event."""
        self._events.append({
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def to_dict(self) -> Dict[str, Any]:
        """Export deployment as dictionary."""
        return {
            "id": self._id,
            "model_id": self._model_id,
            "version": self._version,
            "strategy": self._strategy.value,
            "serving_endpoint": self._serving_endpoint,
            "state": self._state.value,
            "canary_percent": self._canary_percent,
            "health_status": self._health_status,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self.error_rate,
            "avg_latency_ms": self._avg_latency_ms,
            "created_at": self._created_at.isoformat(),
            "deployed_at": self._deployed_at.isoformat() if self._deployed_at else None,
            "stopped_at": self._stopped_at.isoformat() if self._stopped_at else None,
            "event_count": len(self._events),
        }
