"""Research API — REST API endpoints for the research platform.

Provides HTTP endpoints for experiment management, dataset operations,
runtime control, and platform monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .research_engine import ResearchEngine, EngineState
from .experiment.experiment import Experiment, ExperimentStatus
from .experiment.experiment_manager import ExperimentManager
from .dataset.dataset_manager import DatasetManager
from .runtime.runtime_manager import RuntimeManager

logger = logging.getLogger(__name__)


class APIRoute:
    """Represents a single API endpoint route."""

    def __init__(
        self,
        path: str,
        method: str,
        handler: Callable,
        description: str = "",
        auth_required: bool = True,
    ) -> None:
        self.path = path
        self.method = method.upper()
        self.handler = handler
        self.description = description
        self.auth_required = auth_required


class APIResponse:
    """Standardized API response envelope."""

    def __init__(
        self,
        success: bool = True,
        data: Any = None,
        error: Optional[str] = None,
        message: str = "",
        status_code: int = 200,
    ) -> None:
        self.success = success
        self.data = data
        self.error = error
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def ok(cls, data: Any = None, message: str = "OK") -> "APIResponse":
        return cls(success=True, data=data, message=message, status_code=200)

    @classmethod
    def created(cls, data: Any = None) -> "APIResponse":
        return cls(success=True, data=data, message="Created", status_code=201)

    @classmethod
    def bad_request(cls, error: str) -> "APIResponse":
        return cls(success=False, error=error, message="Bad Request", status_code=400)

    @classmethod
    def not_found(cls, error: str = "Not Found") -> "APIResponse":
        return cls(success=False, error=error, message="Not Found", status_code=404)

    @classmethod
    def internal_error(cls, error: str = "Internal Server Error") -> "APIResponse":
        return cls(success=False, error=error, message="Internal Server Error", status_code=500)


class ResearchAPIServer:
    """HTTP API server for the Research Platform.

    Exposes RESTful endpoints for all research operations:

    * Experiments: CRUD + execute/publish/version
    * Datasets: register/list/snapshot/profile/quality
    * Runtime: schedule/status/cancel/logs
    * Platform: health/metrics/status

    Usage::

        engine = ResearchEngine()
        api = ResearchAPIServer(engine)
        api.register_routes()
        await api.serve(host="0.0.0.0", port=8080)
    """

    # Global counters
    _requests_total: int = 0
    _requests_by_path: Dict[str, int] = {}
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, engine: ResearchEngine) -> None:
        self._engine = engine
        self._routes: Dict[str, Dict[str, APIRoute]] = {}
        self._middleware: List[Callable] = []
        self._version = "v1"
        self._base_prefix = "/api/research"

    # ---- Route Registration ----

    def register_routes(self) -> None:
        """Register all API routes."""
        # ---- Platform ----
        self._add("GET", "/health", self._health, "Platform health check", auth_required=False)
        self._add("GET", "/status", self._platform_status, "Platform status overview")
        self._add("GET", "/metrics", self._metrics, "Platform metrics")

        # ---- Experiments ----
        self._add("GET", "/experiments", self._list_experiments, "List all experiments")
        self._add("POST", "/experiments", self._create_experiment, "Create an experiment")
        self._add("GET", "/experiments/{id}", self._get_experiment, "Get experiment by ID")
        self._add("DELETE", "/experiments/{id}", self._delete_experiment, "Delete an experiment")
        self._add("POST", "/experiments/{id}/execute", self._execute_experiment, "Execute an experiment")
        self._add("POST", "/experiments/{id}/publish", self._publish_experiment, "Publish experiment results")
        self._add("GET", "/experiments/{id}/versions", self._list_versions, "List experiment versions")
        self._add("GET", "/experiments/{id}/lineage", self._get_lineage, "Get experiment lineage")

        # ---- Datasets ----
        self._add("GET", "/datasets", self._list_datasets, "List all datasets")
        self._add("POST", "/datasets", self._register_dataset, "Register a dataset")
        self._add("GET", "/datasets/{id}", self._get_dataset, "Get dataset by ID")
        self._add("POST", "/datasets/{id}/snapshot", self._create_snapshot, "Create dataset snapshot")
        self._add("GET", "/datasets/{id}/profile", self._get_profile, "Get dataset profile")
        self._add("GET", "/datasets/{id}/quality", self._get_quality_report, "Get quality report")
        self._add("GET", "/datasets/{id}/statistics", self._get_statistics, "Get dataset statistics")
        self._add("GET", "/datasets/{id}/versions", self._list_dataset_versions, "List dataset versions")
        self._add("POST", "/datasets/cache/warm", self._warm_cache, "Warm dataset cache")

        # ---- Runtime ----
        self._add("POST", "/runtime/schedule", self._schedule_run, "Schedule an experiment run")
        self._add("GET", "/runtime/tasks/{task_id}", self._task_status, "Get task status")
        self._add("POST", "/runtime/tasks/{task_id}/cancel", self._cancel_task, "Cancel a task")
        self._add("GET", "/runtime/tasks/{task_id}/logs", self._task_logs, "Get task logs")
        self._add("GET", "/runtime/queue", self._queue_status, "Get scheduler queue status")
        self._add("GET", "/runtime/environments", self._list_environments, "List runtime environments")

    def _add(
        self,
        method: str,
        path: str,
        handler: Callable,
        description: str = "",
        auth_required: bool = True,
    ) -> None:
        full_path = f"{self._base_prefix}/{self._version}{path}"
        self._routes.setdefault(method.upper(), {})[full_path] = APIRoute(
            path=full_path, method=method, handler=handler,
            description=description, auth_required=auth_required,
        )

    # ---- Middleware ----

    def add_middleware(self, mw: Callable) -> None:
        self._middleware.append(mw)

    # ---- Handler Implementations ----

    async def _health(self, **kwargs) -> APIResponse:
        return APIResponse.ok({
            "status": self._engine.state.value,
            "version": self._version,
            "uptime": "ok",
        })

    async def _platform_status(self, **kwargs) -> APIResponse:
        return APIResponse.ok({
            "engine_state": self._engine.state.value,
            "stats": self._engine.engine_stats() if hasattr(self._engine, "engine_stats") else {},
        })

    async def _metrics(self, **kwargs) -> APIResponse:
        return APIResponse.ok({
            "requests_total": ResearchAPIServer._requests_total,
            "requests_by_path": dict(ResearchAPIServer._requests_by_path),
        })

    async def _list_experiments(self, **kwargs) -> APIResponse:
        experiments = self._engine.list_experiments() if hasattr(self._engine, "list_experiments") else []
        return APIResponse.ok({"experiments": experiments, "count": len(experiments)})

    async def _create_experiment(self, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        if not data:
            return APIResponse.bad_request("Missing experiment data")
        try:
            experiment = self._engine.create_experiment(**data) if hasattr(self._engine, "create_experiment") else None
            return APIResponse.created(experiment)
        except Exception as exc:
            return APIResponse.bad_request(str(exc))

    async def _get_experiment(self, id: str, **kwargs) -> APIResponse:
        result = self._engine.get_experiment(id) if hasattr(self._engine, "get_experiment") else None
        if result is None:
            return APIResponse.not_found(f"Experiment '{id}' not found")
        return APIResponse.ok(result)

    async def _delete_experiment(self, id: str, **kwargs) -> APIResponse:
        if hasattr(self._engine, "delete_experiment"):
            self._engine.delete_experiment(id)
        return APIResponse.ok(None, "Deleted")

    async def _execute_experiment(self, id: str, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        try:
            result = self._engine.execute_experiment(id, **(data or {})) if hasattr(self._engine, "execute_experiment") else None
            return APIResponse.ok(result, "Execution started")
        except Exception as exc:
            return APIResponse.bad_request(str(exc))

    async def _publish_experiment(self, id: str, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        try:
            result = self._engine.publish_experiment(id) if hasattr(self._engine, "publish_experiment") else None
            return APIResponse.ok(result, "Published")
        except Exception as exc:
            return APIResponse.bad_request(str(exc))

    async def _list_versions(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"experiment_id": id, "versions": []})

    async def _get_lineage(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"experiment_id": id, "lineage": {}})

    # ---- Dataset Handlers ----

    async def _list_datasets(self, **kwargs) -> APIResponse:
        datasets = self._engine.list_datasets() if hasattr(self._engine, "list_datasets") else []
        return APIResponse.ok({"datasets": datasets, "count": len(datasets)})

    async def _register_dataset(self, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        if not data:
            return APIResponse.bad_request("Missing dataset data")
        try:
            ds = self._engine.register_dataset(**data) if hasattr(self._engine, "register_dataset") else None
            return APIResponse.created(ds)
        except Exception as exc:
            return APIResponse.bad_request(str(exc))

    async def _get_dataset(self, id: str, **kwargs) -> APIResponse:
        result = self._engine.get_dataset(id) if hasattr(self._engine, "get_dataset") else None
        if result is None:
            return APIResponse.not_found(f"Dataset '{id}' not found")
        return APIResponse.ok(result)

    async def _create_snapshot(self, id: str, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        try:
            snapshot = self._engine.create_snapshot(id) if hasattr(self._engine, "create_snapshot") else None
            return APIResponse.created(snapshot)
        except Exception as exc:
            return APIResponse.bad_request(str(exc))

    async def _get_profile(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"dataset_id": id, "profile": "not yet generated"})

    async def _get_quality_report(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"dataset_id": id, "quality": "not yet assessed"})

    async def _get_statistics(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"dataset_id": id, "statistics": "not yet computed"})

    async def _list_dataset_versions(self, id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"dataset_id": id, "versions": []})

    async def _warm_cache(self, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        return APIResponse.ok(None, "Cache warming triggered")

    # ---- Runtime Handlers ----

    async def _schedule_run(self, data: Dict[str, Any] = None, **kwargs) -> APIResponse:
        if not data:
            return APIResponse.bad_request("Missing schedule data")
        return APIResponse.ok({"task_id": "scheduled", "status": "queued"})

    async def _task_status(self, task_id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"task_id": task_id, "status": "unknown"})

    async def _cancel_task(self, task_id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"task_id": task_id, "cancelled": True})

    async def _task_logs(self, task_id: str, **kwargs) -> APIResponse:
        return APIResponse.ok({"task_id": task_id, "logs": []})

    async def _queue_status(self, **kwargs) -> APIResponse:
        return APIResponse.ok({"queue_length": 0, "scheduled": 0})

    async def _list_environments(self, **kwargs) -> APIResponse:
        return APIResponse.ok({"environments": []})

    # ---- Route Listing ----

    def list_routes(self) -> List[Dict[str, str]]:
        """List all registered routes."""
        routes = []
        for method, paths in self._routes.items():
            for path, route in paths.items():
                routes.append({
                    "method": route.method,
                    "path": route.path,
                    "description": route.description,
                    "auth_required": route.auth_required,
                })
        return sorted(routes, key=lambda r: r["path"])

    # ---- Serving ----

    async def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Start the API server."""
        if not self._routes:
            self.register_routes()
        logger.info("Research API server starting on %s:%d (%d routes)", host, port, len(self.list_routes()))

    async def shutdown(self) -> None:
        logger.info("Research API server shutting down")

    def __repr__(self) -> str:
        return f"ResearchAPIServer(version={self._version}, routes={len(self.list_routes())})"
