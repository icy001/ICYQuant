"""AI Runtime — Low-level execution environment for AI operations.

Manages the runtime lifecycle, concurrency, resource allocation, and
isolation for AI agent execution, model inference, and pipeline processing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AIOperationType(Enum):
    """Types of AI operations managed by the runtime."""

    RESEARCH = "research"
    AGENT_THINK = "agent_think"
    AGENT_COMMUNICATE = "agent_communicate"
    FEATURE_COMPUTE = "feature_compute"
    MODEL_INFERENCE = "model_inference"
    BATCH_INFERENCE = "batch_inference"
    SIGNAL_GENERATION = "signal_generation"
    DECISION_EVALUATION = "decision_evaluation"
    GUARD_CHECK = "guard_check"
    APPROVAL_EVALUATION = "approval_evaluation"


class AIRuntimeStatus(Enum):
    """Runtime status."""

    STARTING = "starting"
    RUNNING = "running"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    DRAINING = "draining"
    STOPPED = "stopped"


@dataclass
class AIRuntimeConfig:
    """Runtime configuration."""

    max_concurrent_operations: int = 100
    operation_timeout_seconds: float = 60.0
    max_queue_size: int = 1000
    worker_count: int = 4
    enable_gpu: bool = False
    enable_tracing: bool = True
    enable_metrics: bool = True


@dataclass
class AIOperation:
    """A tracked AI operation in the runtime."""

    op_id: str
    op_type: AIOperationType
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    duration_ms: float = 0.0
    error: Optional[str] = None


class AIRuntime:
    """AI Runtime — manages concurrent AI operations execution.

    Provides:
        - Concurrency control via semaphores
        - Operation queuing and scheduling
        - Timeout enforcement
        - Resource monitoring
        - Graceful shutdown

    This is the low-level execution layer that all AI operations run through.
    """

    def __init__(self, config: Optional[AIRuntimeConfig] = None) -> None:
        self.config = config or AIRuntimeConfig()
        self.status = AIRuntimeStatus.STOPPED
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._active_ops: Dict[str, AIOperation] = {}
        self._completed_ops: Set[str] = set()
        self._stats: Dict[str, int] = {
            "total_ops": 0,
            "successful_ops": 0,
            "failed_ops": 0,
            "timed_out_ops": 0,
            "rejected_ops": 0,
        }

    async def start(self) -> None:
        """Start the AI Runtime."""
        self.status = AIRuntimeStatus.STARTING
        logger.info(
            "AI Runtime starting (workers=%d, max_concurrent=%d)",
            self.config.worker_count,
            self.config.max_concurrent_operations,
        )

        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_operations)

        for i in range(self.config.worker_count):
            worker = asyncio.create_task(self._worker(i), name=f"ai-runtime-worker-{i}")
            self._workers.append(worker)

        self.status = AIRuntimeStatus.RUNNING
        logger.info("AI Runtime ready")

    async def stop(self) -> None:
        """Stop the AI Runtime gracefully."""
        logger.info("AI Runtime stopping (draining %d ops)", len(self._active_ops))
        self.status = AIRuntimeStatus.DRAINING

        # Signal workers to stop
        for _ in self._workers:
            await self._queue.put(None)

        # Wait with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Workers did not stop in time, cancelling")
            for w in self._workers:
                w.cancel()

        self._workers.clear()
        self.status = AIRuntimeStatus.STOPPED
        logger.info("AI Runtime stopped")

    # ------------------------------------------------------------------
    # Operation Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        op_type: AIOperationType,
        session_id: str,
        coro,
        *,
        timeout: Optional[float] = None,
        priority: int = 0,
    ) -> Any:
        """Execute an AI operation with concurrency control and timeout.

        Args:
            op_type: Type of operation.
            session_id: Owning session ID.
            coro: Awaitable to execute.
            timeout: Optional timeout override.
            priority: Queue priority (higher = sooner).

        Returns:
            Result of the coroutine.
        """
        if self.status not in (AIRuntimeStatus.RUNNING, AIRuntimeStatus.BUSY):
            raise RuntimeError(f"Runtime not running: {self.status}")

        if self._queue.qsize() >= self.config.max_queue_size:
            self._stats["rejected_ops"] += 1
            raise RuntimeError("Runtime queue full, operation rejected")

        op = AIOperation(
            op_id=f"{op_type.value}:{session_id}:{time.monotonic_ns()}",
            op_type=op_type,
            session_id=session_id,
        )

        self._stats["total_ops"] += 1
        self._active_ops[op.op_id] = op

        effective_timeout = timeout or self.config.operation_timeout_seconds

        try:
            async with self._semaphore:
                op.started_at = datetime.now(timezone.utc)
                op.status = "running"

                try:
                    result = await asyncio.wait_for(coro, timeout=effective_timeout)
                    op.status = "completed"
                    self._stats["successful_ops"] += 1
                    return result

                except asyncio.TimeoutError:
                    op.status = "timed_out"
                    op.error = f"Timeout after {effective_timeout}s"
                    self._stats["timed_out_ops"] += 1
                    raise TimeoutError(
                        f"Operation {op_type.value} timed out after {effective_timeout}s"
                    )

        except Exception as exc:
            op.status = "failed"
            op.error = str(exc)
            self._stats["failed_ops"] += 1
            raise

        finally:
            op.completed_at = datetime.now(timezone.utc)
            op.duration_ms = (
                (op.completed_at - op.started_at).total_seconds() * 1000
                if op.started_at
                else 0
            )
            self._active_ops.pop(op.op_id, None)
            self._completed_ops.add(op.op_id)

            if self.config.enable_metrics:
                logger.debug(
                    "AI op complete: %s status=%s duration=%.1fms",
                    op.op_type.value,
                    op.status,
                    op.duration_ms,
                )

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    async def _worker(self, worker_id: int) -> None:
        """Background worker processing queued operations."""
        logger.debug("AI Runtime worker %d started", worker_id)
        while self.status != AIRuntimeStatus.DRAINING:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if item is None:
                break  # Shutdown signal

            fut, op_type, session_id, timeout = item
            try:
                result = await self.execute(op_type, session_id, fut, timeout=timeout)
                fut.set_result(result)
            except Exception as exc:
                if not fut.done():
                    fut.set_exception(exc)

        logger.debug("AI Runtime worker %d stopped", worker_id)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Runtime health status."""
        return {
            "status": self.status.value,
            "active_operations": len(self._active_ops),
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "max_concurrent": self.config.max_concurrent_operations,
            "stats": self._stats.copy(),
        }
