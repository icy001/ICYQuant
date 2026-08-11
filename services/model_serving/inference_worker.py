"""
ICYQuant Inference Worker — Async worker that consumes the inference queue.

Continuously dequeues requests and dispatches to the inference engine.
Supports multiple concurrent workers with graceful shutdown.

Features:
  - Pool of workers with configurable concurrency
  - Per-worker health monitoring
  - Graceful shutdown with in-flight request completion
  - Worker metrics aggregation
  - Backpressure awareness
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .inference_queue import InferenceQueue
    from .inference_engine import InferenceEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class WorkerState(str, Enum):
    """Worker lifecycle state."""
    IDLE = "idle"
    RUNNING = "running"
    DRAINING = "draining"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class WorkerStats:
    """Per-worker statistics."""
    worker_id: int
    state: WorkerState = WorkerState.IDLE
    processed: int = 0
    errors: int = 0
    timeouts: int = 0
    avg_processing_ms: float = 0.0
    total_processing_ms: float = 0.0
    last_processed_at: Optional[str] = None
    current_model_id: Optional[str] = None


@dataclass
class WorkerConfig:
    """Worker pool configuration."""
    num_workers: int = 4
    max_requests_per_worker: int = 0  # 0 = unlimited
    idle_timeout_seconds: int = 300
    shutdown_timeout_seconds: int = 30
    metrics_interval: int = 100  # Log stats every N requests


# ---------------------------------------------------------------------------
# Inference Worker
# ---------------------------------------------------------------------------

class InferenceWorkerPool:
    """Pool of async inference workers.

    Each worker dequeues from the inference queue and dispatches
    to the inference engine.

    Usage::

        pool = InferenceWorkerPool(queue, engine)
        await pool.start()  # Starts num_workers workers

        # Workers process queue automatically

        await pool.stop()  # Graceful shutdown
    """

    def __init__(
        self,
        queue: "InferenceQueue",
        engine: "InferenceEngine",
        config: Optional[WorkerConfig] = None,
    ):
        self.queue = queue
        self.engine = engine
        self.config = config or WorkerConfig()
        self._initialized = False

        # Worker management
        self._workers: List[asyncio.Task] = []
        self._worker_stats: Dict[int, WorkerStats] = {}
        self._running = False

        # Aggregate stats
        self._total_processed: int = 0
        self._total_errors: int = 0
        self._start_time: Optional[float] = None

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("InferenceWorkerPool initialized — workers=%d",
                    self.config.num_workers)

    async def start(self) -> None:
        """Start the worker pool."""
        if not self._initialized:
            await self.initialize()

        self._running = True
        self._start_time = time.time()

        for i in range(self.config.num_workers):
            worker_id = i
            task = asyncio.create_task(
                self._run_worker(worker_id),
                name=f"inference_worker_{worker_id}",
            )
            self._workers.append(task)
            self._worker_stats[worker_id] = WorkerStats(
                worker_id=worker_id,
                state=WorkerState.RUNNING,
            )

        logger.info("Worker pool started: %d workers", self.config.num_workers)

    async def stop(self, drain: bool = True) -> None:
        """Gracefully stop all workers.

        Args:
            drain: If True, wait for in-flight requests to complete.
        """
        if not self._running:
            return

        logger.info("Stopping worker pool (drain=%s)", drain)
        self._running = False

        if drain:
            # Workers will complete current request and stop
            await asyncio.sleep(0.1)  # Let workers notice shutdown

        # Cancel remaining workers
        for task in self._workers:
            if not task.done():
                task.cancel()

        # Wait for workers to finish with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=self.config.shutdown_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("Worker shutdown timed out")

        # Log final stats
        elapsed = time.time() - (self._start_time or time.time())
        throughput = self._total_processed / max(elapsed, 0.001)
        logger.info(
            "Worker pool stopped: processed=%d, errors=%d, throughput=%.1f/s",
            self._total_processed, self._total_errors, throughput,
        )

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _run_worker(self, worker_id: int) -> None:
        """Main worker loop — dequeue and process."""
        stats = self._worker_stats[worker_id]
        logger.info("Worker %d started", worker_id)

        processed_count = 0

        try:
            while self._running:
                try:
                    # Check max requests limit
                    if (self.config.max_requests_per_worker > 0 and
                            processed_count >= self.config.max_requests_per_worker):
                        logger.info("Worker %d reached max requests, stopping", worker_id)
                        break

                    # Dequeue with timeout (allows checking running flag)
                    stats.state = WorkerState.IDLE
                    try:
                        request = await asyncio.wait_for(
                            self.queue.dequeue(),
                            timeout=1.0,
                        )
                    except asyncio.TimeoutError:
                        continue

                    # Process
                    stats.state = WorkerState.RUNNING
                    stats.current_model_id = request.model_id

                    start = time.perf_counter()
                    try:
                        result = await self.engine.predict(
                            model_id=request.model_id,
                            features=request.features,
                            version=request.version,
                        )

                        if not request.future.done():
                            request.future.set_result(result)

                        stats.processed += 1
                        self._total_processed += 1

                    except Exception as exc:
                        stats.errors += 1
                        self._total_errors += 1
                        if not request.future.done():
                            request.future.set_exception(exc)
                        logger.debug("Worker %d inference error: %s", worker_id, exc)

                    # Update timing
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    stats.total_processing_ms += elapsed_ms
                    stats.avg_processing_ms = (
                        stats.total_processing_ms / max(stats.processed, 1)
                    )
                    stats.last_processed_at = datetime.now(timezone.utc).isoformat()

                    processed_count += 1

                    # Periodic stats logging
                    if processed_count % self.config.metrics_interval == 0:
                        logger.debug(
                            "Worker %d: processed=%d, avg=%.1fms",
                            worker_id, stats.processed, stats.avg_processing_ms,
                        )

                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Worker %d unexpected error", worker_id)
                    stats.errors += 1
                    await asyncio.sleep(0.1)  # Avoid tight error loop

        finally:
            stats.state = WorkerState.STOPPED
            logger.info(
                "Worker %d stopped: processed=%d, errors=%d, avg=%.1fms",
                worker_id, stats.processed, stats.errors, stats.avg_processing_ms,
            )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_worker_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all workers."""
        return [
            {
                "worker_id": s.worker_id,
                "state": s.state.value,
                "processed": s.processed,
                "errors": s.errors,
                "timeouts": s.timeouts,
                "avg_processing_ms": round(s.avg_processing_ms, 2),
                "last_processed_at": s.last_processed_at,
                "current_model": s.current_model_id,
            }
            for s in self._worker_stats.values()
        ]

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get aggregate pool statistics."""
        elapsed = time.time() - (self._start_time or time.time())
        return {
            "num_workers": self.config.num_workers,
            "active_workers": sum(
                1 for t in self._workers if not t.done()
            ),
            "total_processed": self._total_processed,
            "total_errors": self._total_errors,
            "error_rate": round(
                self._total_errors / max(self._total_processed, 1), 6
            ),
            "throughput_per_sec": round(
                self._total_processed / max(elapsed, 0.001), 2
            ),
            "uptime_seconds": round(elapsed, 1),
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        error_rate = self._total_errors / max(self._total_processed, 1)
        return {
            "status": "degraded" if error_rate > 0.05 else "healthy",
            "running": self._running,
            "pool": self.get_pool_stats(),
            "workers": self.get_worker_stats(),
        }

    def __repr__(self) -> str:
        return (
            f"InferenceWorkerPool(workers={self.config.num_workers}, "
            f"processed={self._total_processed})"
        )
