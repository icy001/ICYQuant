"""Scheduler Platform Runtime — bridges the scheduler engine with the ICYQuant platform.

The :class:`PlatformRuntime` is the runtime layer that connects the
Distributed Scheduler to the rest of the platform through adapters.
It manages the lifecycle of scheduled jobs as they flow through
the platform integration layer.

Pipeline::

    Scheduler Trigger
           │
    PlatformRuntime
           │
    ┌──────┼──────┐
    Adapter Pipeline
    └──────┼──────┘
    Workflow Engine
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformRuntimePhase(enum.Enum):
    """Phases of the platform runtime lifecycle."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPING = "stopping"
    ERROR = "error"


class PlatformRuntime:
    """Runtime bridge between the Distributed Scheduler and the ICYQuant platform.

    Responsibilities:
    * Manage the adapter pipeline for each scheduled execution
    * Handle pre-execution hooks (validation, authorization, enrichment)
    * Handle post-execution hooks (notification, audit, ledger)
    * Track execution state across platform boundaries

    Usage::

        runtime = PlatformRuntime(integration_manager=manager)
        await runtime.start()
        result = await runtime.execute(context=ctx, adapters=[...])
    """

    def __init__(self, integration_manager: Any = None) -> None:
        self._integration_manager = integration_manager
        self._phase = PlatformRuntimePhase.STOPPED
        self._lock = threading.Lock()
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []
        self._error_hooks: List[Callable] = []
        self._execution_count: int = 0
        self._last_execution_at: Optional[datetime] = None
        self._active_executions: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def phase(self) -> PlatformRuntimePhase:
        return self._phase

    @property
    def execution_count(self) -> int:
        return self._execution_count

    @property
    def active_executions(self) -> int:
        return len(self._active_executions)

    @property
    def last_execution_at(self) -> Optional[datetime]:
        return self._last_execution_at

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the platform runtime."""
        self._set_phase(PlatformRuntimePhase.STARTING)
        logger.info("PlatformRuntime: starting")
        self._set_phase(PlatformRuntimePhase.RUNNING)

    async def stop(self) -> None:
        """Stop the platform runtime gracefully."""
        self._set_phase(PlatformRuntimePhase.STOPPING)
        # Wait for active executions to complete
        drain_timeout = 30.0
        elapsed = 0.0
        while self._active_executions and elapsed < drain_timeout:
            await asyncio.sleep(0.5)
            elapsed += 0.5
        self._set_phase(PlatformRuntimePhase.STOPPED)
        logger.info("PlatformRuntime: stopped")

    async def pause(self) -> None:
        """Pause accepting new executions (drain in-flight)."""
        self._set_phase(PlatformRuntimePhase.PAUSED)
        logger.info("PlatformRuntime: paused")

    async def resume(self) -> None:
        """Resume accepting executions."""
        self._set_phase(PlatformRuntimePhase.RUNNING)
        logger.info("PlatformRuntime: resumed")

    # ------------------------------------------------------------------
    # Hook Registration
    # ------------------------------------------------------------------

    def register_pre_hook(self, hook: Callable) -> None:
        """Register a hook that runs before each execution."""
        self._pre_hooks.append(hook)

    def register_post_hook(self, hook: Callable) -> None:
        """Register a hook that runs after each execution."""
        self._post_hooks.append(hook)

    def register_error_hook(self, hook: Callable) -> None:
        """Register a hook that runs on execution error."""
        self._error_hooks.append(hook)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        context: Dict[str, Any],
        adapters: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a scheduled job through the platform pipeline.

        Pipeline:
        1. Pre-hooks (validation, auth, enrichment)
        2. Adapter chain (workflow → business → notification)
        3. Post-hooks (audit, metrics, ledger)
        """
        execution_id = context.get("execution_id", "")
        self._active_executions[execution_id] = context
        self._execution_count += 1
        self._last_execution_at = datetime.now(timezone.utc)

        result: Dict[str, Any] = {"execution_id": execution_id, "status": "pending"}

        try:
            # Pre-hooks
            for hook in self._pre_hooks:
                try:
                    await hook(context) if asyncio.iscoroutinefunction(hook) else hook(context)
                except Exception as exc:
                    logger.warning("PlatformRuntime: pre-hook error: %s", exc)

            # Adapter chain
            if adapters:
                for adapter in adapters:
                    if hasattr(adapter, "execute"):
                        adapter_result = await adapter.execute(context)
                        result[adapter.__class__.__name__] = adapter_result

            result["status"] = "completed"

            # Post-hooks
            for hook in self._post_hooks:
                try:
                    await hook(context, result) if asyncio.iscoroutinefunction(hook) else hook(context, result)
                except Exception as exc:
                    logger.warning("PlatformRuntime: post-hook error: %s", exc)

        except Exception as exc:
            result["status"] = "error"
            result["error"] = str(exc)
            for hook in self._error_hooks:
                try:
                    await hook(context, exc) if asyncio.iscoroutinefunction(hook) else hook(context, exc)
                except Exception as hook_exc:
                    logger.warning("PlatformRuntime: error-hook error: %s", hook_exc)

        finally:
            self._active_executions.pop(execution_id, None)

        return result

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _set_phase(self, phase: PlatformRuntimePhase) -> None:
        with self._lock:
            self._phase = phase
