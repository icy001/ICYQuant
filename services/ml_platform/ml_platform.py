"""
ICYQuant ML Platform - Core Platform.

Enterprise Feature Store & Machine Learning Pipeline for quantitative finance.
Provides the standard data layer between Market Data and ML Models.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform Enums
# ---------------------------------------------------------------------------


class PlatformState(Enum):
    """ML Platform lifecycle states."""

    UNINITIALIZED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    DEGRADED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class PlatformComponent(Enum):
    """Subsystems of the ML Platform."""

    FEATURE_STORE = "feature_store"
    OFFLINE_STORE = "offline_store"
    ONLINE_STORE = "online_store"
    TRAINING = "training"
    EXPERIMENT = "experiment"
    MODEL_REGISTRY = "model_registry"
    PIPELINE = "pipeline"
    DRIFT_DETECTOR = "drift_detector"


# ---------------------------------------------------------------------------
# Platform Config
# ---------------------------------------------------------------------------


@dataclass
class MLPlatformConfig:
    """Configuration for the ML platform."""

    # Feature Store
    feature_store_enabled: bool = True
    offline_store_backend: str = "parquet"  # parquet, delta, iceberg
    offline_store_path: str = "data/feature_store/offline"
    online_store_backend: str = "redis"  # redis, dynamodb, bigtable
    online_store_ttl_seconds: int = 86400

    # Training
    default_framework: str = "lightgbm"  # lightgbm, xgboost, pytorch, sklearn
    max_training_jobs: int = 10
    training_timeout_seconds: int = 3600

    # Experiment
    experiment_root: str = "experiments"
    auto_track: bool = True
    artifact_retention_days: int = 90

    # Model Registry
    model_registry_path: str = "models/registry"
    required_approval_stages: List[str] = field(default_factory=lambda: ["staging", "production"])

    # Drift
    drift_check_interval_hours: int = 24
    drift_threshold_data: float = 0.1
    drift_threshold_feature: float = 0.05
    drift_threshold_prediction: float = 0.05

    # Pipeline
    max_concurrent_pipelines: int = 5
    checkpoint_enabled: bool = True


# ---------------------------------------------------------------------------
# Platform Status
# ---------------------------------------------------------------------------


@dataclass
class PlatformStatus:
    """Current status of the ML platform."""

    state: PlatformState = PlatformState.UNINITIALIZED
    uptime_seconds: float = 0.0
    healthy_components: List[PlatformComponent] = field(default_factory=list)
    degraded_components: List[PlatformComponent] = field(default_factory=list)
    unhealthy_components: List[PlatformComponent] = field(default_factory=list)

    # Counters
    total_features: int = 0
    total_datasets: int = 0
    total_experiments: int = 0
    total_models: int = 0
    total_training_runs: int = 0
    active_pipelines: int = 0

    last_updated: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ML Platform
# ---------------------------------------------------------------------------


class MLPlatform:
    """Central ML Platform orchestrator.

    Manages all subsystems: Feature Store, Offline/Online Store,
    Training, Experiments, Model Registry, Drift Detection.
    """

    def __init__(self, config: Optional[MLPlatformConfig] = None) -> None:
        self.config = config or MLPlatformConfig()
        self._state = PlatformState.UNINITIALIZED
        self._started_at: Optional[datetime] = None
        self._subsystems: Dict[PlatformComponent, Any] = {}
        self._subsystem_states: Dict[PlatformComponent, PlatformState] = {}

    # -- Lifecycle --

    async def initialize(self) -> None:
        """Initialize all platform subsystems."""
        self._state = PlatformState.INITIALIZING
        logger.info("ML Platform initializing...")

        if self.config.feature_store_enabled:
            self._subsystem_states[PlatformComponent.FEATURE_STORE] = PlatformState.RUNNING
            self._subsystem_states[PlatformComponent.OFFLINE_STORE] = PlatformState.RUNNING
            self._subsystem_states[PlatformComponent.ONLINE_STORE] = PlatformState.RUNNING

        for comp in PlatformComponent:
            if comp not in self._subsystem_states:
                self._subsystem_states[comp] = PlatformState.RUNNING

        self._state = PlatformState.RUNNING
        self._started_at = datetime.utcnow()
        logger.info("ML Platform initialized and running.")

    async def shutdown(self) -> None:
        """Gracefully shutdown all subsystems."""
        self._state = PlatformState.STOPPING
        logger.info("ML Platform shutting down...")
        self._state = PlatformState.STOPPED

    # -- Health --

    def get_status(self) -> PlatformStatus:
        """Get comprehensive platform status."""
        status = PlatformStatus(
            state=self._state,
            healthy_components=[],
            degraded_components=[],
            unhealthy_components=[],
            last_updated=datetime.utcnow(),
        )

        for comp, state in self._subsystem_states.items():
            if state == PlatformState.RUNNING:
                status.healthy_components.append(comp)
            elif state == PlatformState.DEGRADED:
                status.degraded_components.append(comp)
            else:
                status.unhealthy_components.append(comp)

        if self._started_at:
            status.uptime_seconds = (datetime.utcnow() - self._started_at).total_seconds()

        return status

    def is_healthy(self) -> bool:
        """Check if the platform is healthy (no unhealthy components)."""
        return self._state == PlatformState.RUNNING and len(self._unhealthy_components()) == 0

    def _unhealthy_components(self) -> List[PlatformComponent]:
        return [
            comp for comp, state in self._subsystem_states.items()
            if state not in (PlatformState.RUNNING, PlatformState.DEGRADED)
        ]

    # -- Subsystem Registration --

    def register_subsystem(self, component: PlatformComponent, instance: Any) -> None:
        """Register a subsystem instance."""
        self._subsystems[component] = instance
        self._subsystem_states[component] = PlatformState.RUNNING
        logger.debug(f"Registered subsystem: {component.value}")

    def get_subsystem(self, component: PlatformComponent) -> Optional[Any]:
        """Get a registered subsystem instance."""
        return self._subsystems.get(component)

    # -- Async context manager --

    async def __aenter__(self) -> "MLPlatform":
        await self.initialize()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.shutdown()


# ---------------------------------------------------------------------------
# Global platform instance
# ---------------------------------------------------------------------------

_platform: Optional[MLPlatform] = None


def get_platform() -> MLPlatform:
    """Get or create the global ML Platform instance."""
    global _platform
    if _platform is None:
        _platform = MLPlatform()
    return _platform
