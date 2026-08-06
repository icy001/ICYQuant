"""Runtime Container for the Service Mesh Platform.

Provides ``RuntimeContainer`` for managing isolated runtime
environments for business services, supporting hot reload,
dynamic policy application, and resource isolation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class ContainerState(str, Enum):
    """State of a runtime container."""

    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    RELOADING = "reloading"
    DRAINING = "draining"
    STOPPED = "stopped"
    ERROR = "error"


class RuntimeContainer:
    """Runtime container for isolated service execution."""

    def __init__(
        self,
        container_id: str,
        service_name: str,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._container_id = container_id
        self._service_name = service_name
        self._state = ContainerState.CREATED
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._config: Dict[str, Any] = {}
        self._policies: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}
        self._created_at = datetime.utcnow()
        self._started_at: Optional[datetime] = None
        self._last_reload: Optional[datetime] = None
        self._reload_count = 0
        self._error_count = 0
        self._handlers: Dict[str, Callable] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._max_background_tasks = 100

    @property
    def container_id(self) -> str:
        return self._container_id

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def state(self) -> ContainerState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == ContainerState.RUNNING

    async def initialize(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize the runtime container."""
        with self._lock:
            self._state = ContainerState.INITIALIZING
            if config:
                self._config = config

        self._telemetry.log_runtime(
            "container_initialize", "started",
            {"container_id": self._container_id},
        )

        # Run initialization handlers
        for name, handler in self._handlers.items():
            try:
                result = handler(config)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:
                self._state = ContainerState.ERROR
                self._error_count += 1
                self._telemetry.log_error(
                    "runtime_container",
                    "init_failed",
                    str(exc),
                    {"handler": name},
                )
                return {
                    "success": False,
                    "error": str(exc),
                    "handler": name,
                }

        with self._lock:
            self._state = ContainerState.RUNNING
            self._started_at = datetime.utcnow()

        self._telemetry.log_runtime(
            "container_initialize", "completed",
            {"container_id": self._container_id},
        )
        logger.info(
            "Runtime container '%s' for service '%s' initialized.",
            self._container_id,
            self._service_name,
        )
        return {"success": True, "container_id": self._container_id}

    async def reload(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Hot-reload the runtime container."""
        with self._lock:
            self._state = ContainerState.RELOADING
            self._reload_count += 1
            if config:
                self._config.update(config)

        # Run reload handlers
        results: Dict[str, Any] = {}
        for name, handler in self._handlers.items():
            try:
                result = handler(config)
                if asyncio.iscoroutine(result):
                    result = await result
                results[name] = {"success": True, "result": result}
            except Exception as exc:
                results[name] = {"success": False, "error": str(exc)}

        with self._lock:
            self._state = ContainerState.RUNNING
            self._last_reload = datetime.utcnow()

        self._telemetry.log_runtime(
            "container_reload", "completed",
            {"container_id": self._container_id,
             "reload_count": self._reload_count},
        )
        return {
            "success": True,
            "container_id": self._container_id,
            "reload_count": self._reload_count,
            "handler_results": results,
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop the runtime container."""
        with self._lock:
            self._state = ContainerState.DRAINING

        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(
            *self._background_tasks,
            return_exceptions=True,
        )
        self._background_tasks.clear()

        with self._lock:
            self._state = ContainerState.STOPPED

        self._telemetry.log_runtime(
            "container_stop", "completed",
            {"container_id": self._container_id},
        )
        logger.info(
            "Runtime container '%s' stopped.",
            self._container_id,
        )
        return {"success": True, "container_id": self._container_id}

    async def set_policies(
        self, policies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set runtime policies for the container."""
        with self._lock:
            self._policies = policies

        self._telemetry.log_runtime(
            "container_set_policies", "completed",
            {"container_id": self._container_id,
             "policy_keys": list(policies.keys())},
        )
        return {"success": True}

    async def apply_policy(
        self, policy_name: str, policy_value: Any
    ) -> Dict[str, Any]:
        """Apply a single policy to the container."""
        with self._lock:
            self._policies[policy_name] = policy_value

        return {"success": True, "policy": policy_name}

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._config)

    def get_policies(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._policies)

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self._metadata.get(key)

    def register_handler(
        self,
        name: str,
        handler: Callable,
    ) -> None:
        self._handlers[name] = handler

    def add_background_task(
        self, coro_func: Callable, *args, **kwargs
    ) -> Optional[asyncio.Task]:
        if len(self._background_tasks) >= self._max_background_tasks:
            logger.warning(
                "Container '%s' background task limit reached.",
                self._container_id,
            )
            return None
        task = asyncio.create_task(coro_func(*args, **kwargs))
        with self._lock:
            self._background_tasks.append(task)
        return task

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "container_id": self._container_id,
                "service_name": self._service_name,
                "state": self._state.value,
                "config_keys": list(self._config.keys()),
                "policy_keys": list(self._policies.keys()),
                "reload_count": self._reload_count,
                "error_count": self._error_count,
                "created_at": self._created_at.isoformat(),
                "started_at": (
                    self._started_at.isoformat()
                    if self._started_at
                    else None
                ),
                "last_reload": (
                    self._last_reload.isoformat()
                    if self._last_reload
                    else None
                ),
                "metadata": self._metadata,
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.to_dict()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"RuntimeContainer(id={self._container_id}, "
                f"service={self._service_name}, "
                f"state={self._state.value})"
            )


class RuntimeContainerManager:
    """Manages multiple runtime containers."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._containers: Dict[str, RuntimeContainer] = {}
        self._container_index: Dict[str, str] = {}
        self._next_id = 0

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"container-{self._next_id}"

    async def create_container(
        self,
        service_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> RuntimeContainer:
        """Create and initialize a runtime container."""
        container_id = self._generate_id()
        container = RuntimeContainer(
            container_id, service_name,
            telemetry=self._telemetry,
            metrics=self._metrics,
        )
        await container.initialize(config)

        with self._lock:
            self._containers[container_id] = container
            self._container_index[service_name] = container_id

        self._metrics.increment_runtime_total(
            {"service": service_name}
        )
        logger.info(
            "Created runtime container '%s' for '%s'.",
            container_id,
            service_name,
        )
        return container

    async def destroy_container(self, container_id: str) -> Dict[str, Any]:
        """Destroy a runtime container."""
        container = self._containers.get(container_id)
        if container is None:
            return {"success": False, "error": "Container not found"}

        await container.stop()

        with self._lock:
            self._containers.pop(container_id, None)
            for svc, cid in self._container_index.items():
                if cid == container_id:
                    del self._container_index[svc]
                    break

        logger.info(
            "Destroyed runtime container '%s'.", container_id
        )
        return {"success": True, "container_id": container_id}

    def get_container(self, container_id: str) -> Optional[RuntimeContainer]:
        return self._containers.get(container_id)

    def get_container_by_service(
        self, service_name: str
    ) -> Optional[RuntimeContainer]:
        container_id = self._container_index.get(service_name)
        if container_id:
            return self._containers.get(container_id)
        return None

    def list_containers(
        self, state: Optional[ContainerState] = None
    ) -> List[Dict[str, Any]]:
        containers = list(self._containers.values())
        if state:
            containers = [c for c in containers if c.state == state]
        return [c.to_dict() for c in containers]

    async def reload_all(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reload all runtime containers."""
        results: Dict[str, Any] = {}
        for container_id, container in self._containers.items():
            try:
                result = await container.reload(config)
                results[container_id] = result
            except Exception as exc:
                results[container_id] = {
                    "success": False,
                    "error": str(exc),
                }
        return {"success": True, "results": results}

    async def stop_all(self) -> Dict[str, Any]:
        """Stop all runtime containers."""
        results: Dict[str, Any] = {}
        for container_id, container in list(self._containers.items()):
            try:
                result = await container.stop()
                results[container_id] = result
            except Exception as exc:
                results[container_id] = {
                    "success": False,
                    "error": str(exc),
                }
        return {"success": True, "results": results}

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_containers": len(self._containers),
                "containers_by_state": self._count_by_state(),
                "containers": [
                    c.to_dict() for c in self._containers.values()
                ],
            }

    def _count_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self._containers.values():
            state = c.state.value
            counts[state] = counts.get(state, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"RuntimeContainerManager("
                f"containers={len(self._containers)})"
            )
