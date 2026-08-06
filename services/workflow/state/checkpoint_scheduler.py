"""Checkpoint scheduler — periodic background tasks for checkpoint lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CheckpointScheduler:
    """Schedules automatic checkpoint creation at defined intervals.

    Triggers:
      - periodic: every N seconds
      - node_finish: after each node execution
      - critical: before critical steps
    """

    def __init__(
        self,
        checkpoint_manager: "CheckpointManager",  # type: ignore[name-defined]
        lifecycle_manager: "LifecycleManager",  # type: ignore[name-defined]
        interval_seconds: float = 30.0,
    ):
        self._checkpoint_manager = checkpoint_manager
        self._lifecycle_manager = lifecycle_manager
        self._interval = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start periodic checkpoint scheduler."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Checkpoint scheduler started (interval=%.1fs)", self._interval)

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Checkpoint scheduler stopped")

    async def checkpoint_on_node_finish(
        self, execution_id: str
    ) -> None:
        """Create checkpoint after a node completes."""
        state = self._lifecycle_manager.get_state(execution_id)
        if state is None:
            return
        await self._checkpoint_manager.create_checkpoint(state, trigger="node_finish")

    async def checkpoint_before_critical(
        self, execution_id: str
    ) -> None:
        """Create checkpoint before a critical step."""
        state = self._lifecycle_manager.get_state(execution_id)
        if state is None:
            return
        await self._checkpoint_manager.create_checkpoint(state, trigger="critical")

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                active = self._lifecycle_manager.get_active_instances()
                for eid, state in active.items():
                    await self._checkpoint_manager.create_checkpoint(state, trigger="periodic")
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Checkpoint scheduler loop error")
