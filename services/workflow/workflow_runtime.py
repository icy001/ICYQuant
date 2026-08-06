"""Workflow Runtime — manages runtime instances and their lifecycle.

The :class:`WorkflowRuntime` provides the execution environment for workflow
instances. It tracks active instances, manages their lifecycle (start → run →
pause → resume → stop), and integrates with the runtime context and variable
management subsystems.

Architecture::

    WorkflowRuntime
          │
    RuntimeManager
          │
    ┌──────────┼──────────┐
    Context    State      Variables   Events
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime.runtime_manager import RuntimeManager
from .runtime.runtime_state import RuntimeStateManager, RuntimeState
from .runtime.runtime_context import RuntimeContext
from .runtime.runtime_variables import RuntimeVariables
from .runtime.runtime_events import RuntimeEventBus
from .runtime.runtime_metrics import RuntimeMetricsCollector
from .runtime.runtime_health import RuntimeHealthChecker
from .workflow_context import WorkflowContext

logger = logging.getLogger(__name__)


class WorkflowRuntime:
    """Manages the runtime environment for workflow execution.

    The Runtime owns the lifecycle of all active workflow instances, providing
    the infrastructure for context management, variable scoping, event
    publishing, and health monitoring.
    """

    def __init__(self, *, name: str = "default") -> None:
        self._name = name
        self._state_manager = RuntimeStateManager()
        self._manager = RuntimeManager()
        self._variables = RuntimeVariables()
        self._event_bus = RuntimeEventBus()
        self._metrics = RuntimeMetricsCollector()
        self._health = RuntimeHealthChecker()
        self._lock = threading.RLock()
        self._active_instances: Dict[str, WorkflowContext] = {}
        self._started_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> RuntimeState:
        return self._state_manager.get_state()

    @property
    def is_ready(self) -> bool:
        return self._state_manager.get_state() == RuntimeState.READY

    @property
    def active_instance_count(self) -> int:
        with self._lock:
            return len(self._active_instances)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise the runtime and transition to READY."""
        if not self._state_manager.set_state(RuntimeState.INITIALIZING):
            logger.warning("WorkflowRuntime(%s): cannot transition to INITIALIZING from %s",
                           self._name, self._state_manager.get_state())
            return

        self._started_at = datetime.utcnow()
        logger.info("WorkflowRuntime(%s): starting …", self._name)

        await self._manager.start()
        self._event_bus.start()
        self._metrics.start()

        self._state_manager.set_state(RuntimeState.READY)
        logger.info("WorkflowRuntime(%s): ready", self._name)

    async def shutdown(self) -> None:
        """Gracefully shut down the runtime, draining active instances."""
        self._state_manager.set_state(RuntimeState.STOPPING)
        logger.info("WorkflowRuntime(%s): shutting down …", self._name)

        await self._manager.shutdown()
        self._event_bus.shutdown()
        self._metrics.shutdown()
        self._health.shutdown()

        self._active_instances.clear()
        self._state_manager.set_state(RuntimeState.STOPPED)
        logger.info("WorkflowRuntime(%s): stopped", self._name)

    # ------------------------------------------------------------------
    # Instance management
    # ------------------------------------------------------------------

    def register_instance(self, context: WorkflowContext) -> None:
        """Register an active workflow instance."""
        with self._lock:
            self._active_instances[context.execution_id] = context
        self._metrics.increment_active_instances()
        logger.debug("WorkflowRuntime(%s): registered instance %s", self._name, context.execution_id)

    def unregister_instance(self, execution_id: str) -> None:
        """Remove a completed/failed workflow instance."""
        with self._lock:
            self._active_instances.pop(execution_id, None)
        self._metrics.decrement_active_instances()
        logger.debug("WorkflowRuntime(%s): unregistered instance %s", self._name, execution_id)

    def get_instance(self, execution_id: str) -> Optional[WorkflowContext]:
        """Return a registered instance by execution id."""
        with self._lock:
            return self._active_instances.get(execution_id)

    def list_instances(self) -> List[str]:
        """Return execution ids of all active instances."""
        with self._lock:
            return list(self._active_instances.keys())

    # ------------------------------------------------------------------
    # Sub-system accessors
    # ------------------------------------------------------------------

    @property
    def event_bus(self) -> RuntimeEventBus:
        return self._event_bus

    @property
    def variables(self) -> RuntimeVariables:
        return self._variables

    @property
    def metrics(self) -> RuntimeMetricsCollector:
        return self._metrics

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "state": self._state_manager.get_state().value,
            "is_ready": self.is_ready,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "active_instances": self.active_instance_count,
            "state_manager": self._state_manager.get_history()[-5:] if self._state_manager.get_history() else [],
        }
