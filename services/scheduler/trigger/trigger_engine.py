"""Unified Trigger Engine — normalizes every trigger source into a single pipeline.

The :class:`TriggerEngine` is the *when* layer of the distributed scheduler.
It accepts trigger registrations from any source (cron, interval, calendar,
event, webhook, manual, dependency), evaluates them on a shared loop, ranks
by priority, and dispatches to the scheduler runtime.

Pipeline::

    Registration → Evaluation → PriorityQueue → Dispatch → SchedulerRuntime
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .trigger_manager import TriggerManager
from .trigger_registry import TriggerRegistry
from .trigger_dispatcher import TriggerDispatcher, DispatchResult
from .priority_queue import PriorityQueue
from .misfire_handler import MisfireHandler, MisfirePolicy

logger = logging.getLogger(__name__)


class TriggerEngineState:
    """Trigger engine lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class TriggerEngine:
    """Unified entry point for trigger evaluation and dispatch.

    The engine owns the evaluation loop, priority queue, misfire handler,
    and dispatcher.  All trigger sources register through the manager and
    are polled on a configurable interval.

    Usage::

        engine = TriggerEngine()
        await engine.start()
        await engine.register(cron_trigger)
        await engine.schedule(schedule_id)
        await engine.shutdown()
    """

    def __init__(
        self,
        *,
        poll_interval_ms: int = 250,
        queue_max_size: int = 100_000,
        misfire_policy: MisfirePolicy = MisfirePolicy.FIRE_IMMEDIATELY,
    ) -> None:
        self._lock = threading.RLock()
        self._state: str = TriggerEngineState.UNINITIALIZED

        self._poll_interval_ms = poll_interval_ms
        self._queue_max_size = queue_max_size

        self._manager = TriggerManager()
        self._registry = TriggerRegistry()
        self._queue = PriorityQueue(max_size=queue_max_size)
        self._misfire_handler = MisfireHandler(default_policy=misfire_policy)
        self._dispatcher = TriggerDispatcher()

        self._eval_task: Optional[asyncio.Task] = None
        self._dispatch_task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime] = None

        # Stats
        self._total_evaluated: int = 0
        self._total_fired: int = 0
        self._total_dispatched: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the trigger engine evaluation and dispatch loops."""
        with self._lock:
            if self._state == TriggerEngineState.RUNNING:
                return
            self._state = TriggerEngineState.INITIALIZING

        logger.info("TriggerEngine: starting …")
        await self._manager.start()
        self._dispatcher.start()
        self._misfire_handler.start()

        self._eval_task = asyncio.create_task(self._evaluation_loop())
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())

        self._started_at = datetime.now(timezone.utc)
        with self._lock:
            self._state = TriggerEngineState.RUNNING
        logger.info("TriggerEngine: running (poll=%dms)", self._poll_interval_ms)

    async def stop(self) -> None:
        """Gracefully stop the trigger engine."""
        with self._lock:
            if self._state in (TriggerEngineState.STOPPED, TriggerEngineState.STOPPING):
                return
            self._state = TriggerEngineState.STOPPING

        logger.info("TriggerEngine: stopping …")
        for task in (self._eval_task, self._dispatch_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._dispatcher.stop()
        self._misfire_handler.stop()
        await self._manager.stop()

        with self._lock:
            self._state = TriggerEngineState.STOPPED
        logger.info("TriggerEngine: stopped")

    async def pause(self) -> None:
        """Pause trigger evaluation (dispatch continues draining)."""
        with self._lock:
            self._state = TriggerEngineState.PAUSED
        logger.info("TriggerEngine: paused")

    async def resume(self) -> None:
        """Resume trigger evaluation."""
        with self._lock:
            self._state = TriggerEngineState.RUNNING
        logger.info("TriggerEngine: resumed")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(self, trigger: Any) -> str:
        """Register a trigger instance.

        Returns the trigger_id so callers can later enable/disable/remove.
        """
        trigger_id = self._registry.register(trigger)
        await self._manager.register(trigger)
        logger.debug("TriggerEngine: registered trigger_id=%s", trigger_id)
        return trigger_id

    async def unregister(self, trigger_id: str) -> bool:
        """Remove a trigger by id."""
        await self._manager.unregister(trigger_id)
        return self._registry.unregister(trigger_id)

    async def enable(self, trigger_id: str) -> None:
        await self._manager.enable(trigger_id)

    async def disable(self, trigger_id: str) -> None:
        await self._manager.disable(trigger_id)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_triggers(self) -> List[Dict[str, Any]]:
        return self._manager.list_triggers()

    def get_queue_depth(self) -> int:
        return len(self._queue)

    def is_running(self) -> bool:
        return self._state == TriggerEngineState.RUNNING

    # ------------------------------------------------------------------
    # Internal loops
    # ------------------------------------------------------------------

    async def _evaluation_loop(self) -> None:
        """Background loop: evaluate all active triggers each tick."""
        while True:
            try:
                if self._state != TriggerEngineState.RUNNING:
                    await asyncio.sleep(self._poll_interval_ms / 1000.0)
                    continue

                active = await self._manager.get_active_triggers()
                for trigger in active:
                    try:
                        result = await trigger.evaluate()
                        if result.should_fire:
                            self._queue.push(
                                trigger_id=trigger.trigger_id,
                                schedule_id=getattr(trigger, "schedule_id", ""),
                                payload=result.payload,
                                priority=getattr(trigger, "priority", 100),
                                fire_at=result.fire_at,
                            )
                            self._total_fired += 1
                        elif result.is_misfire:
                            await self._misfire_handler.handle(trigger, result)
                    except Exception:
                        logger.exception(
                            "TriggerEngine: evaluation failed for trigger_id=%s",
                            getattr(trigger, "trigger_id", "?"),
                        )
                    self._total_evaluated += 1

                await asyncio.sleep(self._poll_interval_ms / 1000.0)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TriggerEngine: evaluation loop error")
                await asyncio.sleep(1.0)

    async def _dispatch_loop(self) -> None:
        """Background loop: pop from priority queue and dispatch."""
        while True:
            try:
                if self._queue.is_empty():
                    await asyncio.sleep(self._poll_interval_ms / 1000.0)
                    continue

                item = self._queue.pop()
                if item is None:
                    await asyncio.sleep(0.01)
                    continue

                result: DispatchResult = await self._dispatcher.dispatch(item)
                if not result.success:
                    logger.warning(
                        "TriggerEngine: dispatch failed trigger_id=%s error=%s",
                        item.trigger_id,
                        result.error,
                    )
                    await self._misfire_handler.handle_dispatch_failure(item, result)
                else:
                    self._total_dispatched += 1

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TriggerEngine: dispatch loop error")
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "queue_depth": len(self._queue),
            "queue_max": self._queue_max_size,
            "total_evaluated": self._total_evaluated,
            "total_fired": self._total_fired,
            "total_dispatched": self._total_dispatched,
            "manager": self._manager.health_report(),
            "misfire": self._misfire_handler.health_report(),
            "dispatcher": self._dispatcher.health_report(),
        }
