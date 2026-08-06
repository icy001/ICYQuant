"""Platform Runtime — unified runtime for the workflow platform.

The :class:`PlatformRuntime` is the common execution substrate that all
integration adapters run on. It provides:

* Lifecycle management (start / stop / health)
* Shared context for cross-adapter communication
* Runtime health & metrics aggregation
* Graceful shutdown coordination

Architecture::

    Business Request
          │
    Workflow Engine
          │
    Platform Runtime ←── Service Mesh
          │               EventBus
    Business Services     AI Runtime
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformRuntimeState(str, Enum):
    """Runtime lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RuntimeContext:
    """Shared context available to all integration adapters."""

    runtime_id: str = "default"
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None


class PlatformRuntime:
    """Unified runtime for the workflow integration platform.

    Usage::

        runtime = PlatformRuntime()
        await runtime.start()
        ctx = runtime.create_context(trace_id="...")
        await runtime.stop()
    """

    def __init__(self, *, name: str = "default") -> None:
        self._name = name
        self._state = PlatformRuntimeState.STOPPED
        self._lock = threading.RLock()
        self._contexts: Dict[str, RuntimeContext] = {}
        self._started_at: Optional[datetime] = None

        # Background maintenance
        self._started = False
        self._maintenance_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> PlatformRuntimeState:
        with self._lock:
            return self._state

    @property
    def is_active(self) -> bool:
        return self._state == PlatformRuntimeState.ACTIVE

    @property
    def context_count(self) -> int:
        with self._lock:
            return len(self._contexts)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        with self._lock:
            if self._state == PlatformRuntimeState.ACTIVE:
                return
            self._state = PlatformRuntimeState.STARTING
            self._started_at = datetime.utcnow()

        self._started = True
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())

        with self._lock:
            self._state = PlatformRuntimeState.ACTIVE

        logger.info("PlatformRuntime(%s): active", self._name)

    async def stop(self) -> None:
        with self._lock:
            if self._state == PlatformRuntimeState.STOPPED:
                return
            self._state = PlatformRuntimeState.STOPPING

        self._started = False
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass

        with self._lock:
            self._state = PlatformRuntimeState.STOPPED

        logger.info("PlatformRuntime(%s): stopped", self._name)

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def create_context(self, *, trace_id: Optional[str] = None) -> RuntimeContext:
        """Create a new runtime context for an execution."""
        ctx = RuntimeContext(
            runtime_id=self._name,
            trace_id=trace_id,
            started_at=datetime.utcnow(),
        )
        with self._lock:
            self._contexts[trace_id or ctx.runtime_id] = ctx
        return ctx

    def get_context(self, trace_id: str) -> Optional[RuntimeContext]:
        with self._lock:
            return self._contexts.get(trace_id)

    def remove_context(self, trace_id: str) -> None:
        with self._lock:
            self._contexts.pop(trace_id, None)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def emit_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        *,
        trace_id: Optional[str] = None,
    ) -> None:
        """Emit a platform-level event."""
        logger.debug("PlatformRuntime(%s): event %s (trace=%s)", self._name, event_type, trace_id)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def _maintenance_loop(self) -> None:
        """Periodic runtime maintenance."""
        while self._started:
            try:
                await asyncio.sleep(60.0)
                # Cleanup stale contexts, etc.
                logger.debug("PlatformRuntime(%s): maintenance tick", self._name)
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "state": self._state.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "context_count": self.context_count,
        }
