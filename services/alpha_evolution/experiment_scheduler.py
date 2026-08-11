"""Experiment Scheduler — Schedules evolution experiments and backtests."""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExperimentPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ExperimentScheduler:
    """Priority-based experiment scheduler for evolution workloads."""

    def __init__(self, max_concurrent: int = 16, max_queue_size: int = 1000):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._max_concurrent = max_concurrent
        self._max_queue = max_queue_size
        self._active = 0
        self._completed = 0
        self._failed = 0

    async def schedule(self, experiment_id: str, priority: ExperimentPriority, payload: Dict[str, Any]) -> None:
        await self._queue.put((-priority.value, experiment_id, payload))

    async def run_worker(self) -> None:
        """Run the scheduler worker loop."""
        while True:
            try:
                _, exp_id, payload = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                self._active += 1
                await asyncio.sleep(0.01)  # placeholder for actual execution
                self._completed += 1
                self._active -= 1
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._failed += 1
                logger.error("Experiment %s failed: %s", exp_id, e)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queue_size": self._queue.qsize(),
            "active": self._active,
            "completed": self._completed,
            "failed": self._failed,
            "max_concurrent": self._max_concurrent,
        }
