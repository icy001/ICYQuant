"""
Timeout Manager — unified timeout control for tasks, stages, and workflows.

Supports:
- Task-level timeout (per node)
- Stage-level timeout (per execution stage)
- Workflow-level timeout (global)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """Timeout configuration."""

    task_timeout_seconds: Optional[float] = 300.0   # Per-node default
    stage_timeout_seconds: Optional[float] = None    # Per-stage
    workflow_timeout_seconds: Optional[float] = 3600.0  # Global
    grace_period_seconds: float = 5.0


@dataclass
class TimeoutState:
    """State for a running timeout."""

    node_id: str
    timeout_seconds: float
    start_time: float
    deadline: float
    timer_task: Optional[asyncio.Task] = None
    callback: Optional[Callable] = None


class TimeoutManager:
    """
    Manages timeouts for workflow execution.

    Tracks deadlines for tasks, stages, and workflows.
    Fires callbacks when timeouts are exceeded.
    """

    def __init__(self, config: Optional[TimeoutConfig] = None):
        self.config = config or TimeoutConfig()
        self._node_timeouts: Dict[str, float] = {}
        self._stage_timeouts: Dict[int, float] = {}
        self._active_timers: Dict[str, TimeoutState] = {}
        self._workflow_deadline: Optional[float] = None
        self._workflow_start: Optional[float] = None

    def set_node_timeout(self, node_id: str, timeout_seconds: float) -> None:
        """Set timeout for a specific node."""
        self._node_timeouts[node_id] = timeout_seconds

    def set_stage_timeout(self, stage_id: int, timeout_seconds: float) -> None:
        """Set timeout for a specific stage."""
        self._stage_timeouts[stage_id] = timeout_seconds

    def get_timeout(self, node_id: str, stage_id: Optional[int] = None) -> Optional[float]:
        """
        Get the effective timeout for a node.

        Priority: node-specific > stage-specific > task default
        """
        if node_id in self._node_timeouts:
            return self._node_timeouts[node_id]
        if stage_id is not None and stage_id in self._stage_timeouts:
            return self._stage_timeouts[stage_id]
        return self.config.task_timeout_seconds

    def start_workflow_timer(self) -> None:
        """Start the global workflow timer."""
        import time
        self._workflow_start = time.monotonic()
        if self.config.workflow_timeout_seconds:
            self._workflow_deadline = (
                self._workflow_start + self.config.workflow_timeout_seconds
            )

    def is_workflow_expired(self) -> bool:
        """Check if the workflow has exceeded its global timeout."""
        if self._workflow_deadline is None:
            return False
        import time
        return time.monotonic() > self._workflow_deadline

    def get_remaining_workflow_time(self) -> Optional[float]:
        """Get remaining time for the workflow."""
        if self._workflow_deadline is None:
            return None
        import time
        remaining = self._workflow_deadline - time.monotonic()
        return max(0, remaining)

    async def start_node_timer(
        self,
        node_id: str,
        timeout_seconds: float,
        callback: Optional[Callable] = None,
    ) -> TimeoutState:
        """Start a timer for a specific node."""
        import time
        now = time.monotonic()

        state = TimeoutState(
            node_id=node_id,
            timeout_seconds=timeout_seconds,
            start_time=now,
            deadline=now + timeout_seconds,
            callback=callback,
        )

        async def _timeout_handler():
            await asyncio.sleep(timeout_seconds)
            if node_id in self._active_timers:
                logger.warning(f"Node {node_id} timed out after {timeout_seconds}s")
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(node_id)
                    else:
                        callback(node_id)
                self._active_timers.pop(node_id, None)

        state.timer_task = asyncio.create_task(_timeout_handler())
        self._active_timers[node_id] = state
        return state

    async def cancel_node_timer(self, node_id: str) -> None:
        """Cancel the timer for a specific node."""
        state = self._active_timers.pop(node_id, None)
        if state and state.timer_task:
            state.timer_task.cancel()
            try:
                await state.timer_task
            except asyncio.CancelledError:
                pass

    async def cancel_all(self) -> None:
        """Cancel all active timers."""
        for state in list(self._active_timers.values()):
            if state.timer_task:
                state.timer_task.cancel()
        self._active_timers.clear()

    def get_stats(self) -> Dict[str, Any]:
        import time
        return {
            "active_timers": len(self._active_timers),
            "workflow_elapsed": (
                time.monotonic() - self._workflow_start
                if self._workflow_start
                else 0
            ),
            "workflow_remaining": self.get_remaining_workflow_time(),
            "node_timeouts_configured": len(self._node_timeouts),
        }
