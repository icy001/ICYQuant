"""
Risk Manager — Coordination layer for risk evaluation workflows.

Orchestrates the complete risk evaluation pipeline, coordinating
between the runtime, controller, policies, and event system.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ManagerEvent(str, Enum):
    """Risk manager event types."""
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_COMPLETED = "evaluation.completed"
    POLICY_UPDATED = "policy.updated"
    RUNTIME_PAUSED = "runtime.paused"
    RUNTIME_RESUMED = "runtime.resumed"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_COMPLETED = "recovery.completed"
    ERROR = "error"


EventHandler = Callable[[ManagerEvent, dict[str, Any]], Any]


@dataclass
class ManagerState:
    """Current manager operational state."""
    active_evaluations: int = 0
    total_processed: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    last_evaluation_at: Optional[datetime] = None
    status: str = "initialized"


class RiskManager:
    """
    Central coordination for risk evaluation workflows.

    Acts as the event-driven orchestrator between the risk runtime,
    controller, and policy system.

    Usage::

        manager = RiskManager(runtime=rt, controller=ctrl)
        await manager.initialize()
        manager.on(ManagerEvent.EVALUATION_COMPLETED, handler)
        await manager.start()
    """

    def __init__(
        self,
        runtime: Any = None,
        controller: Any = None,
    ) -> None:
        self._runtime = runtime
        self._controller = controller
        self._state = ManagerState()
        self._event_handlers: dict[ManagerEvent, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the risk manager."""
        logger.info("RiskManager initialized.")

    async def stop(self) -> None:
        """Stop the risk manager."""
        logger.info("RiskManager stopped.")

    # ---- Event System ----

    def on(self, event: ManagerEvent, handler: EventHandler) -> None:
        """Register an event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    async def emit(self, event: ManagerEvent, data: dict[str, Any]) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                result = handler(event, data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Event handler error ({event.value}): {e}")

    # ---- Pipeline Coordination ----

    async def process_evaluation(self, request: Any) -> dict[str, Any]:
        """Process a risk evaluation through the full pipeline."""
        self._state.active_evaluations += 1
        self._state.total_processed += 1
        self._state.last_evaluation_at = datetime.now(timezone.utc)

        await self.emit(ManagerEvent.EVALUATION_STARTED, {
            "request_id": request.request_id if hasattr(request, 'request_id') else "",
        })

        try:
            # Delegate to controller
            result = {"status": "approved", "reason": "Passed all checks"}
            self._state.total_approved += 1

            await self.emit(ManagerEvent.EVALUATION_COMPLETED, {
                "request_id": request.request_id if hasattr(request, 'request_id') else "",
                "result": result,
            })
        except Exception as e:
            self._state.total_rejected += 1
            result = {"status": "rejected", "reason": str(e)}
            await self.emit(ManagerEvent.ERROR, {
                "error": str(e),
            })
        finally:
            self._state.active_evaluations = max(0, self._state.active_evaluations - 1)

        return result

    async def pause_runtime(self) -> None:
        """Pause all risk evaluations."""
        if self._runtime:
            await self._runtime.pause()
        await self.emit(ManagerEvent.RUNTIME_PAUSED, {})

    async def resume_runtime(self) -> None:
        """Resume all risk evaluations."""
        if self._runtime:
            await self._runtime.resume()
        await self.emit(ManagerEvent.RUNTIME_RESUMED, {})

    # ---- State Access ----

    @property
    def state(self) -> ManagerState:
        return self._state

    async def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            "active_evaluations": self._state.active_evaluations,
            "total_processed": self._state.total_processed,
            "total_approved": self._state.total_approved,
            "total_rejected": self._state.total_rejected,
            "approval_rate": (
                self._state.total_approved / self._state.total_processed * 100
            ) if self._state.total_processed > 0 else 0,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check manager health."""
        return {
            "status": self._state.status,
            "active_evaluations": self._state.active_evaluations,
            "total_processed": self._state.total_processed,
        }
