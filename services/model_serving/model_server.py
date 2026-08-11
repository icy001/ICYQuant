"""
ICYQuant Model Server — Central model serving gateway.

Orchestrates model loading, inference routing, deployment management,
and lifecycle coordination across all serving subsystems.

Architecture:
    Model Registry → Model Repository → Model Runtime → Inference Engine
       → Prediction Service → Traffic Router → Monitoring → Alerting
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ServerState(str, Enum):
    """Model server lifecycle states."""
    INITIALIZING = "initializing"
    LOADING_MODELS = "loading_models"
    READY = "ready"
    DRAINING = "draining"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServingMode(str, Enum):
    """Serving operation mode."""
    ONLINE = "online"          # < 50ms real-time inference
    BATCH = "batch"             # Scheduled batch inference
    HYBRID = "hybrid"           # Both online + batch


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ServerConfig:
    """Model server configuration."""
    host: str = "0.0.0.0"
    http_port: int = 8080
    grpc_port: int = 9090
    websocket_port: int = 8081
    serving_mode: ServingMode = ServingMode.HYBRID
    max_concurrent_inferences: int = 100
    max_batch_size: int = 256
    inference_timeout_ms: int = 5000
    warmup_iterations: int = 10
    enable_canary: bool = True
    enable_shadow: bool = True
    enable_rollback: bool = True
    model_cache_size: int = 8
    prediction_cache_ttl_seconds: int = 60
    health_check_interval_seconds: int = 15
    metrics_export_interval_seconds: int = 30


@dataclass
class ServerStatus:
    """Current server status snapshot."""
    state: ServerState = ServerState.INITIALIZING
    uptime_seconds: float = 0.0
    loaded_models: int = 0
    active_deployments: int = 0
    total_inferences: int = 0
    inferences_per_second: float = 0.0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    last_health_check: Optional[datetime] = None
    canary_active: bool = False
    shadow_active: bool = False
    retraining_active: bool = False


# ---------------------------------------------------------------------------
# Model Server
# ---------------------------------------------------------------------------

class ModelServer:
    """Central model serving gateway.

    Coordinates all serving subsystems:
      - Model loading / warming / unloading
      - Inference routing (online + batch)
      - Deployment strategy (canary, shadow, rollback)
      - Health monitoring & metrics
      - Retraining orchestration

    Usage::

        server = ModelServer(config)
        await server.start()
        prediction = await server.predict("nvda_alpha_model", features)
        await server.stop()
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        self.config = config or ServerConfig()
        self._status = ServerStatus()
        self._started_at: Optional[datetime] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Subsystem references (lazy-init)
        self._model_repository = None
        self._model_runtime = None
        self._inference_engine = None
        self._prediction_service = None
        self._deployment_manager = None
        self._traffic_router = None
        self._monitor = None
        self._retraining_manager = None

        # Task tracking
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the model server and all subsystems."""
        self._started_at = datetime.now(timezone.utc)
        self._loop = asyncio.get_running_loop()
        self._status.state = ServerState.INITIALIZING
        logger.info("ModelServer starting — mode=%s", self.config.serving_mode)

        try:
            await self._init_subsystems()
            await self._load_models()
            await self._start_background_tasks()

            self._status.state = ServerState.READY
            logger.info("ModelServer ready — %d models loaded",
                        self._status.loaded_models)
        except Exception:
            self._status.state = ServerState.DEGRADED
            logger.exception("ModelServer start failed — entering degraded state")
            raise

    async def stop(self, drain: bool = True) -> None:
        """Gracefully stop the model server.

        Args:
            drain: If True, complete in-flight requests before stopping.
        """
        self._status.state = ServerState.DRAINING if drain else ServerState.STOPPING
        logger.info("ModelServer stopping — drain=%s", drain)

        if drain:
            await self._drain_inflight_requests()

        self._shutdown_event.set()

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        await self._shutdown_subsystems()

        self._status.state = ServerState.STOPPED
        self._status.uptime_seconds = self._compute_uptime()
        logger.info("ModelServer stopped — uptime=%.1fs", self._status.uptime_seconds)

    # ------------------------------------------------------------------
    # Inference — primary API
    # ------------------------------------------------------------------

    async def predict(
        self,
        model_id: str,
        features: Dict[str, Any],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run a single inference.

        Args:
            model_id: Model identifier (e.g. 'nvda_alpha_model').
            features: Feature dictionary keyed by feature name.
            version: Optional pinned version; defaults to production.
            timeout_ms: Per-request timeout override.

        Returns:
            Prediction dict with model_id, version, prediction, confidence, etc.
        """
        if self._status.state != ServerState.READY:
            raise RuntimeError(f"Server not ready (state={self._status.state})")

        return await self._inference_engine.predict(
            model_id=model_id,
            features=features,
            version=version,
            timeout_ms=timeout_ms or self.config.inference_timeout_ms,
        )

    async def predict_batch(
        self,
        model_id: str,
        features_list: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Run batch inference across multiple feature sets."""
        return await self._inference_engine.predict_batch(
            model_id=model_id,
            features_list=features_list,
            version=version,
            timeout_ms=timeout_ms or self.config.inference_timeout_ms,
        )

    async def stream_predict(
        self,
        model_id: str,
        features_stream: AsyncIterator[Dict[str, Any]],
        *,
        version: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream inference results for a continuous feature stream."""
        async for features in features_stream:
            prediction = await self.predict(model_id, features, version=version)
            yield prediction

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    async def deploy_model(self, model_id: str, version: str) -> Dict[str, Any]:
        """Deploy a model version to production."""
        return await self._deployment_manager.deploy(model_id, version)

    async def rollback_model(self, model_id: str) -> Dict[str, Any]:
        """Rollback a model to its previous stable version."""
        return await self._deployment_manager.rollback(model_id)

    async def canary_deploy(
        self, model_id: str, candidate_version: str, traffic_percent: float = 5.0
    ) -> Dict[str, Any]:
        """Start canary deployment for a candidate model."""
        return await self._deployment_manager.start_canary(
            model_id, candidate_version, traffic_percent
        )

    async def promote_canary(self, model_id: str) -> Dict[str, Any]:
        """Promote a successful canary to full production."""
        return await self._deployment_manager.promote_canary(model_id)

    async def shadow_deploy(self, model_id: str, candidate_version: str) -> Dict[str, Any]:
        """Start shadow deployment — evaluate without affecting live traffic."""
        return await self._deployment_manager.start_shadow(model_id, candidate_version)

    # ------------------------------------------------------------------
    # Retraining
    # ------------------------------------------------------------------

    async def trigger_retraining(self, model_id: str, reason: str = "manual") -> str:
        """Manually trigger a retraining run.

        Returns:
            Retraining run ID.
        """
        return await self._retraining_manager.trigger(model_id, reason)

    async def get_retraining_status(self, run_id: str) -> Dict[str, Any]:
        """Query status of a retraining run."""
        return await self._retraining_manager.get_status(run_id)

    async def get_model_comparison(
        self, model_id: str, version_a: str, version_b: str
    ) -> Dict[str, Any]:
        """Compare two model versions side-by-side."""
        return await self._retraining_manager.compare_versions(
            model_id, version_a, version_b
        )

    # ------------------------------------------------------------------
    # Status & health
    # ------------------------------------------------------------------

    @property
    def status(self) -> ServerStatus:
        self._status.uptime_seconds = self._compute_uptime()
        return self._status

    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check across all subsystems."""
        checks: Dict[str, Any] = {
            "server": self._status.state.value,
            "uptime_seconds": self._compute_uptime(),
            "subsystems": {},
        }

        subsystems = {
            "repository": self._model_repository,
            "runtime": self._model_runtime,
            "inference": self._inference_engine,
            "deployment": self._deployment_manager,
            "traffic": self._traffic_router,
            "monitor": self._monitor,
            "retraining": self._retraining_manager,
        }

        for name, sub in subsystems.items():
            if sub and hasattr(sub, "health"):
                try:
                    checks["subsystems"][name] = await sub.health()
                except Exception as exc:
                    checks["subsystems"][name] = {"status": "error", "error": str(exc)}
            else:
                checks["subsystems"][name] = {"status": "not_initialized"}

        # Aggregate health
        all_healthy = all(
            s.get("status") in ("healthy", "ready", "not_initialized")
            for s in checks["subsystems"].values()
        )
        checks["healthy"] = all_healthy and self._status.state == ServerState.READY

        self._status.last_health_check = datetime.now(timezone.utc)
        return checks

    # ------------------------------------------------------------------
    # Internals — initialization
    # ------------------------------------------------------------------

    async def _init_subsystems(self) -> None:
        """Initialize all serving subsystems in dependency order."""
        # Lazy imports to avoid circular dependencies
        from .model_repository import ModelRepository
        from .model_loader import ModelLoader
        from .model_runtime import ModelRuntime
        from .inference_engine import InferenceEngine
        from .prediction_service import PredictionService
        from .deployment_manager import DeploymentManager
        from .traffic_router import TrafficRouter

        # 1. Model repository (artifact store)
        self._model_repository = ModelRepository()
        await self._model_repository.initialize()

        # 2. Model loader (loads artifacts into runtime)
        self._model_loader = ModelLoader(self._model_repository)

        # 3. Model runtime (in-memory model execution)
        self._model_runtime = ModelRuntime(
            cache_size=self.config.model_cache_size
        )
        await self._model_runtime.initialize()

        # 4. Inference engine (orchestrates feature→prediction)
        self._inference_engine = InferenceEngine(
            runtime=self._model_runtime,
            feature_adapter=None,  # injected later
        )
        await self._inference_engine.initialize()

        # 5. Prediction service
        self._prediction_service = PredictionService(
            engine=self._inference_engine,
            cache_ttl=self.config.prediction_cache_ttl_seconds,
        )
        await self._prediction_service.initialize()

        # 6. Deployment manager
        self._deployment_manager = DeploymentManager(
            runtime=self._model_runtime,
            repository=self._model_repository,
        )
        await self._deployment_manager.initialize()

        # 7. Traffic router
        self._traffic_router = TrafficRouter(
            engine=self._inference_engine,
            deployment_manager=self._deployment_manager,
        )
        await self._traffic_router.initialize()

        # Connect feature adapter to inference engine
        from .feature_adapter import FeatureAdapter
        from .online_feature_provider import OnlineFeatureProvider

        feature_provider = OnlineFeatureProvider()
        await feature_provider.initialize()

        self._feature_adapter = FeatureAdapter(
            provider=feature_provider
        )
        self._inference_engine.feature_adapter = self._feature_adapter

        logger.info("All serving subsystems initialized")

    async def _load_models(self) -> None:
        """Load models from registry into runtime."""
        self._status.state = ServerState.LOADING_MODELS

        from .model_resolver import ModelResolver
        resolver = ModelResolver(self._model_repository)

        # Load production versions
        models = await resolver.resolve_production_models()
        for model_spec in models:
            await self._model_runtime.load(
                model_id=model_spec["model_id"],
                version=model_spec["version"],
            )
            self._status.loaded_models += 1

        # Warmup
        await self._model_runtime.warmup_all(
            iterations=self.config.warmup_iterations
        )

        logger.info("Loaded %d models into runtime", self._status.loaded_models)

    async def _start_background_tasks(self) -> None:
        """Start periodic background maintenance tasks."""
        tasks = [
            self._health_check_loop(),
            self._metrics_export_loop(),
        ]
        for t in tasks:
            task = asyncio.create_task(t)
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    async def _shutdown_subsystems(self) -> None:
        """Shutdown subsystems in reverse order."""
        for sub in [self._traffic_router, self._deployment_manager,
                     self._inference_engine, self._model_runtime,
                     self._model_repository]:
            if sub and hasattr(sub, "shutdown"):
                try:
                    await sub.shutdown()
                except Exception:
                    logger.exception("Error shutting down %s", type(sub).__name__)

    async def _drain_inflight_requests(self, timeout: float = 30.0) -> None:
        """Wait for in-flight requests to complete."""
        # Delegate to inference engine
        if self._inference_engine:
            await self._inference_engine.drain(timeout=timeout)

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while not self._shutdown_event.is_set():
            try:
                await self.health_check()
            except Exception:
                logger.exception("Health check loop error")
            await asyncio.sleep(self.config.health_check_interval_seconds)

    async def _metrics_export_loop(self) -> None:
        """Periodic metrics export."""
        while not self._shutdown_event.is_set():
            try:
                await self._export_metrics()
            except Exception:
                logger.exception("Metrics export error")
            await asyncio.sleep(self.config.metrics_export_interval_seconds)

    async def _export_metrics(self) -> None:
        """Export current metrics snapshot."""
        from .metrics import ServingMetrics
        ServingMetrics.record_uptime(self._compute_uptime())
        ServingMetrics.record_loaded_models(self._status.loaded_models)
        ServingMetrics.record_inferences_total(self._status.total_inferences)

    def _compute_uptime(self) -> float:
        if self._started_at is None:
            return 0.0
        return (datetime.now(timezone.utc) - self._started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"ModelServer(state={self._status.state.value}, "
            f"models={self._status.loaded_models}, "
            f"mode={self.config.serving_mode.value})"
        )
