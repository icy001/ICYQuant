"""
Market Data Runtime — operational runtime for the Market Data Engine.

Manages the execution context, concurrency, back-pressure, and
runtime state of the normalization pipeline.

Commit 16 Part 1.2
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MarketDataRuntimeStatus(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    BACK_PRESSURE = "back_pressure"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"


@dataclass
class MarketDataRuntimeConfig:
    max_concurrency: int = 16
    max_queue_depth: int = 50_000
    back_pressure_threshold: float = 0.80  # 80% queue full triggers back-pressure
    drain_batch_size: int = 500
    consumer_count: int = 4
    task_timeout: float = 5.0
    monitor_interval: float = 1.0


@dataclass
class RuntimeMetrics:
    total_ingested: int = 0
    total_normalized: int = 0
    total_published: int = 0
    total_rejected: int = 0
    queue_depth: int = 0
    active_tasks: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    throughput_per_sec: float = 0.0


class MarketDataRuntime:
    """
    Operational runtime for the Market Data Engine.

    Manages task scheduling, concurrency limits, queue back-pressure,
    and runtime telemetry for the normalization pipeline.
    """

    def __init__(self, config: Optional[MarketDataRuntimeConfig] = None) -> None:
        self.config = config or MarketDataRuntimeConfig()
        self._status = MarketDataRuntimeStatus.CREATED

        self._ingest_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=self.config.max_queue_depth
        )
        self._consumer_tasks: list[asyncio.Task[Any]] = []
        self._monitor_task: Optional[asyncio.Task[Any]] = None
        self._metrics = RuntimeMetrics()

        self._start_time: Optional[datetime] = None
        self._latencies: list[float] = []
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        self._status = MarketDataRuntimeStatus.STARTING
        self._start_time = datetime.now(timezone.utc)
        self._shutdown_event.clear()

        for i in range(self.config.consumer_count):
            task = asyncio.create_task(self._consumer(i), name=f"md-consumer-{i}")
            self._consumer_tasks.append(task)

        self._monitor_task = asyncio.create_task(self._monitor(), name="md-monitor")
        self._status = MarketDataRuntimeStatus.RUNNING
        logger.info("MarketDataRuntime started with %d consumers", self.config.consumer_count)

    async def stop(self) -> None:
        self._status = MarketDataRuntimeStatus.DRAINING
        logger.info("MarketDataRuntime draining (%d items in queue)", self._ingest_queue.qsize())

        self._shutdown_event.set()

        # Cancel monitor first
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()

        # Wait for consumers to drain
        for task in self._consumer_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._consumer_tasks, return_exceptions=True)

        self._status = MarketDataRuntimeStatus.STOPPED
        logger.info("MarketDataRuntime stopped")

    async def enqueue(self, raw_event: dict[str, Any]) -> bool:
        """Enqueue a raw event. Returns False if back-pressure is active."""
        queue_fill = self._ingest_queue.qsize() / max(self.config.max_queue_depth, 1)
        if queue_fill >= self.config.back_pressure_threshold:
            self._status = MarketDataRuntimeStatus.BACK_PRESSURE
            return False
        await self._ingest_queue.put(raw_event)
        self._metrics.queue_depth = self._ingest_queue.qsize()
        return True

    async def _consumer(self, consumer_id: int) -> None:
        """Background consumer that drains the ingest queue."""
        while not self._shutdown_event.is_set():
            try:
                raw = await asyncio.wait_for(
                    self._ingest_queue.get(), timeout=self.config.task_timeout
                )
                self._metrics.total_ingested += 1
            except asyncio.TimeoutError:
                continue

    async def _monitor(self) -> None:
        """Periodic runtime monitoring."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.config.monitor_interval)

                # Calculate throughput
                elapsed = (datetime.now(timezone.utc) - self._start_time).total_seconds()
                if elapsed > 0:
                    self._metrics.throughput_per_sec = self._metrics.total_ingested / elapsed

                # Update queue depth
                self._metrics.queue_depth = self._ingest_queue.qsize()
                self._metrics.active_tasks = sum(
                    1 for t in self._consumer_tasks if not t.done()
                )

                # Latency stats
                if self._latencies:
                    self._metrics.avg_latency_ms = sum(self._latencies) / len(self._latencies)
                    self._metrics.max_latency_ms = max(self._latencies)
                    self._latencies = self._latencies[-1000:]  # Rolling window

                # Auto-clear back-pressure
                fill_pct = self._metrics.queue_depth / max(self.config.max_queue_depth, 1)
                if self._status == MarketDataRuntimeStatus.BACK_PRESSURE and fill_pct < 0.5:
                    self._status = MarketDataRuntimeStatus.RUNNING

            except asyncio.CancelledError:
                break

    def record_latency_ms(self, latency_ms: float) -> None:
        self._latencies.append(latency_ms)

    @property
    def status(self) -> MarketDataRuntimeStatus:
        return self._status

    @property
    def metrics(self) -> RuntimeMetrics:
        return self._metrics
