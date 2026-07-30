"""Serving Service — central orchestration for model serving.

The top-level service that composes all serving components into a unified
interface. Coordinates model loading, routing, feature joining, caching,
A/B testing, canary release, and monitoring.

Usage::

    service = ServingService(config=ServingConfig())
    service.start()
    result = service.predict("NVDA")
    service.deploy("alpha_v38", strategy="canary")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.serving.inference import InferenceEngine, InferenceConfig
from services.serving.predictor import OnlinePredictor, PredictRequest, PredictResult, PredictSignal, BatchPredictor
from services.serving.model_loader import ModelLoader, ModelFormat, LoadConfig
from services.serving.model_router import ModelRouter, RouteRule, RouterConfig
from services.serving.feature_join import FeatureJoiner, JoinSpec, JoinStrategy
from services.serving.prediction_cache import PredictionCache, CacheConfig, CachePolicy
from services.serving.ab_testing import ABTesting, ABExperiment, ABVariant, ABConfig
from services.serving.canary import CanaryManager, CanaryStage, CanaryConfig, CanaryStatus
from services.serving.rollout import RolloutManager, RolloutConfig, RolloutStrategy
from services.serving.monitor import InferenceMonitor, MonitorConfig, HealthStatus


class ServingMode(str, Enum):
    """Serving service operational mode."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ServingConfig:
    """Top-level serving service configuration.

    Attributes:
        mode: Operational mode.
        inference: Inference engine config.
        loader: Model loader config.
        router: Model router config.
        cache: Prediction cache config.
        ab_testing: A/B testing config.
        canary: Canary release config.
        rollout: Rollout manager config.
        monitor: Inference monitor config.
        enable_ab_testing: Enable A/B testing.
        enable_canary: Enable canary release.
        enable_prediction_cache: Enable prediction caching.
    """

    mode: ServingMode = ServingMode.DEVELOPMENT
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    loader: LoadConfig = field(default_factory=LoadConfig)
    router: RouterConfig = field(default_factory=RouterConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    ab_testing: ABConfig = field(default_factory=ABConfig)
    canary: CanaryConfig = field(default_factory=CanaryConfig)
    rollout: RolloutConfig = field(default_factory=RolloutConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    enable_ab_testing: bool = False
    enable_canary: bool = False
    enable_prediction_cache: bool = True


class ServingService:
    """Central serving orchestration service.

    Wires together all inference components: model loading, routing,
    feature joining, caching, A/B testing, canary, and monitoring.

    Usage::

        service = ServingService(
            config=ServingConfig(),
            online_store=feature_store,
            registry=model_registry,
            storage=ml_storage,
        )
        service.start()
        result = service.predict("NVDA")
        results = service.predict_batch(["NVDA", "AAPL", "GOOGL"])
        service.deploy("alpha_v38", strategy="canary")
    """

    def __init__(
        self,
        config: Optional[ServingConfig] = None,
        online_store: Any = None,
        registry: Any = None,
        storage: Any = None,
    ):
        self.config = config or ServingConfig()
        self.mode = self.config.mode

        # Model loader
        self.loader = ModelLoader(
            registry=registry,
            storage=storage,
            config=self.config.loader,
        )

        # Model router
        self.router = ModelRouter(
            config=self.config.router,
            model_loader=self.loader,
        )

        # Feature joiner
        self.joiner = FeatureJoiner(
            online_store=online_store,
            feature_service=None,
            default_strategy=JoinStrategy.ONLINE_ONLY,
        )

        # Prediction cache
        self.cache = PredictionCache(config=self.config.cache) if self.config.enable_prediction_cache else None

        # Inference engine
        self.engine = InferenceEngine(config=self.config.inference)

        # Predictor
        self.predictor = OnlinePredictor(
            inference_engine=self.engine,
            feature_joiner=self.joiner,
            model_router=self.router,
            prediction_cache=self.cache,
        )

        # A/B testing
        self.ab_testing = ABTesting(config=self.config.ab_testing) if self.config.enable_ab_testing else None

        # Canary manager
        self.canary = CanaryManager(config=self.config.canary) if self.config.enable_canary else None

        # Rollout manager
        self.rollout = RolloutManager(
            model_loader=self.loader,
            canary_manager=self.canary,
            registry=registry,
            config=self.config.rollout,
        )

        # Monitor
        self.monitor = InferenceMonitor(config=self.config.monitor)

        self._started = False

    def start(self) -> None:
        """Start the serving service: preload models, start watcher."""
        if self._started:
            return

        # Preload all production models
        if self.config.loader.preload_on_startup:
            self.loader.preload_all_production()

        # Start registry watcher for auto-deploy
        if self.config.rollout.auto_deploy:
            self.rollout.watch()

        self._started = True

    def stop(self) -> None:
        """Stop the serving service."""
        self.rollout.stop_watch()
        self._started = False

    # ---- prediction APIs ----

    def predict(
        self,
        symbol: str,
        features: Optional[Dict[str, float]] = None,
        model_name: Optional[str] = None,
        market: str = "US",
    ) -> PredictResult:
        """Single online prediction with full serving pipeline.

        Flow: AB test → Cache → Feature Join → Route → Infer → Cache → Monitor
        """
        start = time.perf_counter()

        # A/B testing: check if symbol is in an experiment
        ab_variant = None
        if self.ab_testing:
            for exp in self.ab_testing.list_experiments():
                variant = self.ab_testing.select_variant(symbol, exp.name)
                if variant:
                    ab_variant = variant
                    model_name = variant.model_name
                    break

        # Canary: check if request goes to canary model
        if self.canary and self.canary.status.state != "idle":
            import hashlib
            hash_val = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            if self.canary.is_new_model(hash_val):
                model_name = self.canary.status.model_name

        # Predict
        request = PredictRequest(
            symbol=symbol,
            features=features,
            model_name=model_name or None,
            market=market,
        )
        result = self.predictor.predict(request)

        # Monitor
        self.monitor.record_latency(result.latency_ms)
        self.monitor.record_prediction(result.prediction, result.model_name)
        if result.cached:
            self.monitor.record_cache_hit(True)
        else:
            self.monitor.record_cache_hit(False)

        return result

    def predict_batch(
        self,
        symbols: List[str],
        features_list: Optional[List[Dict[str, float]]] = None,
        market: str = "US",
    ) -> List[PredictResult]:
        """Batch prediction for multiple symbols."""
        requests = []
        for i, symbol in enumerate(symbols):
            feats = features_list[i] if features_list else None
            requests.append(PredictRequest(symbol=symbol, features=feats, market=market))

        start = time.perf_counter()
        results = self.predictor.predict_batch(requests)
        latency = (time.perf_counter() - start) * 1000

        for r in results:
            self.monitor.record_latency(latency / len(results) if results else 0)
            self.monitor.record_prediction(r.prediction, r.model_name)

        return results

    def predict_portfolio(
        self,
        symbols: List[str],
        features_dict: Optional[Dict[str, Dict[str, float]]] = None,
        market: str = "US",
    ) -> Dict[str, PredictResult]:
        """Predict for an entire portfolio."""
        return self.predictor.predict_portfolio(symbols, market, features_dict)

    # ---- deployment APIs ----

    def deploy(
        self,
        model_name: str,
        version: str,
        strategy: str = "immediate",
        model: Any = None,
    ) -> Any:
        """Deploy a model version for serving.

        Args:
            model_name: Model to deploy.
            version: Version to deploy.
            strategy: 'immediate', 'canary', 'blue_green', 'shadow'.
            model: Pre-loaded model (optional).

        Returns:
            RolloutResult from RolloutManager.
        """
        from services.serving.rollout import RolloutStrategy
        s = RolloutStrategy(strategy) if isinstance(strategy, str) else strategy
        return self.rollout.deploy(model_name, version, strategy=s, model=model)

    def rollback(self, model_name: str) -> Any:
        """Rollback a model to previous version."""
        return self.rollout.rollback(model_name)

    # ---- A/B testing APIs ----

    def create_ab_experiment(
        self,
        name: str,
        variants: List[Dict[str, Any]],
        description: str = "",
    ) -> Optional[ABExperiment]:
        """Create an A/B testing experiment."""
        if not self.ab_testing:
            return None

        ab_variants = [
            ABVariant(
                name=v["name"],
                model_name=v["model_name"],
                traffic_share=v.get("traffic_share", 0.5),
                description=v.get("description", ""),
            )
            for v in variants
        ]
        return self.ab_testing.create_experiment(name, ab_variants, description)

    # ---- status APIs ----

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive serving status."""
        monitor_stats = self.monitor.get_stats()
        loaded_models = self.loader.list_loaded()
        active_versions = self.rollout.list_active()
        routing_rules = self.router.list_rules()
        cache_stats = self.cache.get_stats() if self.cache else {}

        return {
            "mode": self.mode.value,
            "started": self._started,
            "monitor": monitor_stats,
            "models_loaded": len(loaded_models),
            "models": [m.to_dict() for m in loaded_models],
            "active_versions": active_versions,
            "routing_rules": len(routing_rules),
            "routes": [{"market": r.market, "model": r.model_name, "priority": r.priority} for r in routing_rules],
            "cache": cache_stats,
            "canary": self.canary.status.__dict__ if self.canary else None,
            "ab_experiments": len(self.ab_testing.list_experiments()) if self.ab_testing else 0,
        }

    def health(self) -> HealthStatus:
        """Health check for the serving service."""
        return self.monitor.check_health()

    def get_monitor_stats(self) -> Dict[str, Any]:
        """Get detailed monitoring statistics."""
        return self.monitor.get_stats()

    # ---- model management ----

    def register_model(self, model_name: str, model: Any, route_rule: Optional[RouteRule] = None) -> None:
        """Register a model with optional routing rule."""
        self.router.register_model(model_name, model)
        if route_rule:
            self.router.add_rule(route_rule)

    def register_route(self, rule: RouteRule) -> None:
        """Add a routing rule."""
        self.router.add_rule(rule)

    def register_model_features(self, model_name: str, feature_names: List[str]) -> None:
        """Register required features for a model."""
        self.joiner.register_model_features(model_name, feature_names)
