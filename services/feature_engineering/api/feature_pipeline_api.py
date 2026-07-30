"""Feature Pipeline REST API.

Provides HTTP endpoints for managing and executing feature engineering
pipelines in the ICYQuant platform.

Endpoints:
    POST   /api/v1/feature-pipeline              Create pipeline
    GET    /api/v1/feature-pipeline/{name}        Get pipeline config
    DELETE /api/v1/feature-pipeline/{name}        Delete pipeline
    POST   /api/v1/feature-pipeline/run           Execute pipeline
    GET    /api/v1/feature-pipeline/status/{name} Get run status
    GET    /api/v1/features/importance             Get feature importance
    GET    /api/v1/feature-pipeline/schedules      List schedules
    POST   /api/v1/feature-pipeline/schedule       Create schedule
    GET    /api/v1/feature-pipeline/cache/stats    Cache statistics
    POST   /api/v1/feature-pipeline/cache/clear    Clear cache
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from services.feature_engineering.pipeline import (
    FeaturePipeline,
    PipelineConfig,
    PipelineResult,
    PipelineStatus,
)
from services.feature_engineering.orchestrator import (
    OrchestratorConfig,
    PipelineOrchestrator,
    RetryPolicy,
    RunStatus,
)
from services.feature_engineering.scheduler import (
    PipelineScheduler,
    ScheduleConfig,
    TriggerType,
)
from services.feature_engineering.cache import (
    CachePolicy,
    FeatureCache,
)
from services.feature_engineering.validator import (
    PipelineValidationRule,
    PipelineValidator,
)
from services.feature_engineering.selector import (
    CorrelationFilter,
    FeatureSelector,
    MutualInfoFilter,
    VarianceFilter,
)
from services.feature_engineering.importance import (
    FeatureImportanceAnalyzer,
    ImportanceMethod,
    ImportanceReport,
)


class FeaturePipelineAPI:
    """REST API controller for feature engineering pipelines.

    Encapsulates the business logic for all pipeline endpoints.
    Can be used with any web framework (FastAPI, Flask, etc.).

    Example::

        api = FeaturePipelineAPI()
        result = api.create_pipeline("alpha_daily", {...})
        status = api.run_pipeline("alpha_daily", raw_data)
    """

    def __init__(self) -> None:
        self._orchestrator = PipelineOrchestrator(
            OrchestratorConfig(
                max_retries=3,
                retry_policy=RetryPolicy.EXPONENTIAL,
                checkpoint_enabled=True,
            )
        )
        self._scheduler = PipelineScheduler(orchestrator=self._orchestrator)
        self._cache = FeatureCache(policy=CachePolicy.HASH, ttl=86400)
        self._validator = PipelineValidator()
        self._selector = FeatureSelector()
        self._importance_analyzer = FeatureImportanceAnalyzer()

        # Built-in transform registry
        self._transform_registry: Dict[str, Callable] = {}

    # ---- Pipeline CRUD ----

    def create_pipeline(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and register a new feature pipeline.

        Args:
            name: Pipeline name identifier.
            config: Optional configuration dict.

        Returns:
            Status and pipeline info.
        """
        cfg = PipelineConfig(name=name, **(config or {}))
        pipeline = FeaturePipeline(cfg)
        pipeline.register_transforms(self._transform_registry)
        self._orchestrator.register(pipeline)
        return {
            "status": "created",
            "pipeline": name,
            "config": pipeline.to_dict(),
        }

    def get_pipeline(self, name: str) -> Optional[Dict[str, Any]]:
        """Get pipeline configuration by name."""
        pipeline = self._orchestrator.get_pipeline(name)
        if pipeline is None:
            return None
        return pipeline.to_dict()

    def delete_pipeline(self, name: str) -> Dict[str, Any]:
        """Delete a registered pipeline."""
        self._orchestrator.unregister(name)
        self._scheduler.unschedule(name)
        return {"status": "deleted", "pipeline": name}

    def list_pipelines(self) -> List[Dict[str, Any]]:
        """List all registered pipelines."""
        result = []
        for name in self._orchestrator.list_pipelines():
            pipeline = self._orchestrator.get_pipeline(name)
            if pipeline:
                status = self._orchestrator.get_status(name)
                result.append({
                    "name": name,
                    "status": pipeline.status.value,
                    "run_status": status.value if status else "unknown",
                    "transforms": pipeline.config.transforms,
                })
        return result

    # ---- Pipeline execution ----

    def run_pipeline(
        self,
        pipeline_name: str,
        raw_data: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline with the given data.

        Args:
            pipeline_name: Name of the pipeline to execute.
            raw_data: Input data dict (column -> values).

        Returns:
            Execution result summary.
        """
        if pipeline_name not in self._orchestrator.list_pipelines():
            return {"error": f"Pipeline '{pipeline_name}' not found"}

        data = raw_data or {}
        result = self._orchestrator.run(pipeline_name, data)

        return {
            "pipeline": pipeline_name,
            "status": result.status.value,
            "progress": self._compute_progress(result),
            "features_generated": result.feature_count,
            "feature_names": result.feature_names[:20],  # first 20
            "elapsed_seconds": round(result.elapsed_seconds, 3),
            "warnings": result.warnings,
            "errors": result.errors if result.status == PipelineStatus.FAILED else [],
        }

    def get_pipeline_status(self, pipeline_name: str) -> Dict[str, Any]:
        """Get current execution status of a pipeline."""
        run_status = self._orchestrator.get_status(pipeline_name)
        history = self._orchestrator.get_history(pipeline_name)
        result = history.get(pipeline_name) if history else None

        return {
            "pipeline": pipeline_name,
            "run_status": run_status.value if run_status else "unknown",
            "last_run": {
                "status": result.status.value if result else "none",
                "features": result.feature_count if result else 0,
                "elapsed": round(result.elapsed_seconds, 3) if result else 0,
            } if result else None,
        }

    # ---- Feature Importance ----

    def get_feature_importance(
        self,
        feature_names: Optional[List[str]] = None,
        method: str = "tree_gain",
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """Get feature importance rankings.

        Args:
            feature_names: Optional list of feature names to filter.
            method: Importance computation method.
            top_n: Number of top features to return.

        Returns:
            Ranked feature importance dict.
        """
        imp_method = ImportanceMethod(method)
        report = ImportanceReport(
            importances=self._mock_importances(feature_names),
            method=imp_method,
        )

        return {
            "method": method,
            "total_features": len(report.importances),
            "top_features": [
                {"feature": name, "importance": round(score, 4)}
                for name, score in report.top_features(top_n)
            ],
            "cumulative_importance": round(report.cumulative_importance(), 4),
        }

    def _mock_importances(self, feature_names: Optional[List[str]] = None) -> Dict[str, float]:
        """Generate mock importance data for API demo."""
        if feature_names:
            import random
            random.seed(42)
            return {f: round(random.random(), 4) for f in feature_names}
        return {
            "momentum_20": 0.312,
            "order_imbalance": 0.208,
            "rsi_14": 0.082,
            "atr_14": 0.061,
            "volatility_20": 0.054,
            "volume_ratio_20": 0.048,
            "ema_20": 0.042,
            "return_5d": 0.038,
            "bb_upper": 0.031,
            "zscore_20": 0.028,
        }

    # ---- Schedules ----

    def list_schedules(self) -> Dict[str, Any]:
        """List all scheduled pipelines."""
        return {
            "running": self._scheduler.is_running,
            "schedules": [
                {
                    "pipeline": e.pipeline_name,
                    "trigger": e.config.trigger.value,
                    "expression": e.config.expression,
                    "enabled": e.config.enabled,
                    "last_run": e.last_run,
                    "next_run": e.next_run,
                    "run_count": e.run_count,
                }
                for e in self._scheduler.list_schedules()
            ],
        }

    def create_schedule(
        self,
        pipeline_name: str,
        trigger: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Create or update a schedule for a pipeline.

        Args:
            pipeline_name: Pipeline to schedule.
            trigger: Trigger string (e.g. "cron:0 3 * * *").
            enabled: Whether schedule is active.

        Returns:
            Schedule entry info.
        """
        entry = self._scheduler.schedule(
            pipeline_name,
            config=ScheduleConfig(enabled=enabled),
            trigger=trigger,
        )
        return {
            "status": "created",
            "pipeline": entry.pipeline_name,
            "trigger": entry.config.trigger.value,
            "expression": entry.config.expression,
            "enabled": entry.config.enabled,
            "next_run": entry.next_run,
        }

    # ---- Cache ----

    def cache_stats(self) -> Dict[str, Any]:
        """Get feature cache statistics."""
        return self._cache.stats()

    def clear_cache(self, feature_name: Optional[str] = None) -> Dict[str, Any]:
        """Clear feature cache.

        Args:
            feature_name: Optional feature name to selectively clear.

        Returns:
            Number of entries cleared.
        """
        count = self._cache.invalidate(feature_name=feature_name)
        return {"status": "cleared", "entries_removed": count}

    # ---- Helpers ----

    def register_transform(self, name: str, fn: Callable) -> None:
        """Register a transform function globally.

        Args:
            name: Transform name.
            fn: Callable taking (data_dict) -> dict of new features.
        """
        self._transform_registry[name] = fn

    def _compute_progress(self, result: PipelineResult) -> str:
        """Compute progress percentage from pipeline stages."""
        stage_map = {"load": 15, "clean": 30, "transform": 60, "validate": 80, "select": 90, "publish": 100, "done": 100}
        if not result.stages_completed:
            return "0%"
        last_stage = result.stages_completed[-1].value
        pct = stage_map.get(last_stage, 100)
        return f"{pct}%"

    def __repr__(self) -> str:
        return f"FeaturePipelineAPI(pipelines={len(self._orchestrator.list_pipelines())})"
