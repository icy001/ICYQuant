"""Runtime Manager — manages research execution environments and lifecycle.

Coordinates environment provisioning, resource allocation, and lifecycle
for research experiment runtimes.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .runtime_state import RuntimeState

logger = logging.getLogger(__name__)


class RuntimeEnvironment(str, Enum):
    """Supported execution environments."""

    LOCAL = "local"           # Local process
    DOCKER = "docker"         # Docker container
    KUBERNETES = "kubernetes" # K8s pod
    VENV = "venv"             # Python virtualenv
    CONDA = "conda"           # Conda environment
    CUSTOM = "custom"         # Custom provider


class RuntimeMode(str, Enum):
    """Runtime execution modes."""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    INTERACTIVE = "interactive"  # Notebook-style


class RuntimeManagerState(str, Enum):
    """Runtime manager lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"


class RuntimeManager:
    """Central manager for research execution environments.

    Responsibilities:
    * Provision and teardown execution environments
    * Track environment lifecycle and resource usage
    * Handle environment health and recovery
    * Interface with distributed scheduler for resource allocation

    Usage::

        manager = RuntimeManager()
        env = await manager.provision(
            experiment_id="exp-001",
            environment=RuntimeEnvironment.DOCKER,
            image="python:3.11",
        )
        await manager.run(env.id)
        await manager.collect(env.id)
        await manager.teardown(env.id)
    """

    # Global counters
    _provisions: int = 0
    _teardowns: int = 0
    _errors: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        self._state = RuntimeManagerState.UNINITIALIZED
        self._environments: Dict[str, Dict[str, Any]] = {}
        self._states: Dict[str, RuntimeState] = {}
        self._active_count: int = 0
        self._max_concurrent: int = 10

    @property
    def state(self) -> RuntimeManagerState:
        return self._state

    @property
    def active_count(self) -> int:
        return self._active_count

    async def initialize(self) -> None:
        self._state = RuntimeManagerState.INITIALIZING
        logger.info("RuntimeManager initializing...")
        self._state = RuntimeManagerState.READY
        logger.info("RuntimeManager ready (max_concurrent=%d)", self._max_concurrent)

    async def provision(
        self,
        experiment_id: str,
        environment: RuntimeEnvironment = RuntimeEnvironment.LOCAL,
        mode: RuntimeMode = RuntimeMode.ASYNCHRONOUS,
        resources: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Provision a new execution environment for an experiment.

        Args:
            experiment_id: The experiment this runtime belongs to.
            environment: Target execution environment type.
            mode: Synchronous, asynchronous, or interactive execution.
            resources: Resource specification (cpu, memory, gpu).
            image: Container image (for Docker/K8s).

        Returns:
            Environment configuration dict.
        """
        async with self._lock:
            if self._active_count >= self._max_concurrent:
                raise RuntimeError(
                    f"Max concurrent environments ({self._max_concurrent}) reached"
                )
            env_id = str(uuid4())
            env = {
                "id": env_id,
                "experiment_id": experiment_id,
                "environment": environment.value,
                "mode": mode.value,
                "resources": resources or {"cpu": 1, "memory_mb": 512},
                "image": image,
                "created_at": datetime.now(timezone.utc),
                "metadata": kwargs,
            }
            self._environments[env_id] = env
            rs = RuntimeState(env_id=env_id, experiment_id=experiment_id)
            self._states[env_id] = rs
            self._active_count += 1
            RuntimeManager._provisions += 1
            logger.info(
                "Provisioned environment %s for experiment %s (type=%s)",
                env_id[:8], experiment_id[:8], environment.value,
            )
            return env

    async def teardown(self, env_id: str) -> bool:
        """Tear down an execution environment."""
        async with self._lock:
            env = self._environments.pop(env_id, None)
            self._states.pop(env_id, None)
            if env:
                self._active_count -= 1
                RuntimeManager._teardowns += 1
                logger.info("Torn down environment %s", env_id[:8])
                return True
            return False

    async def status(self, env_id: str) -> Optional[RuntimeState]:
        """Get the current state of an environment."""
        return self._states.get(env_id)

    async def snapshot(self, env_id: str) -> Dict[str, Any]:
        """Snapshot environment state for reproducibility."""
        state = self._states.get(env_id)
        if state is None:
            return {"error": "not_found", "env_id": env_id}
        return {
            "env_id": env_id,
            "state": state.to_dict(),
            "active_count": self._active_count,
        }

    def list_environments(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": eid,
                "experiment_id": env["experiment_id"],
                "environment": env["environment"],
                "state": self._states[eid].to_dict() if eid in self._states else None,
            }
            for eid, env in self._environments.items()
        ]

    async def shutdown(self) -> None:
        """Gracefully shutdown all environments."""
        self._state = RuntimeManagerState.DRAINING
        env_ids = list(self._environments.keys())
        for eid in env_ids:
            await self.teardown(eid)
        self._state = RuntimeManagerState.STOPPED

    @property
    def provision_count(self) -> int:
        return RuntimeManager._provisions

    @property
    def teardown_count(self) -> int:
        return RuntimeManager._teardowns

    def __repr__(self) -> str:
        return (
            f"RuntimeManager(state={self._state.value}, "
            f"active={self._active_count}/{self._max_concurrent})"
        )
