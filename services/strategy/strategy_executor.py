"""
Production strategy executor.

Executes strategy logic within a controlled runtime environment,
managing context, timing, error handling, and result collection.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from .strategy_context import StrategyExecutionContext
from .strategy_state import StrategyLifecycleState

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Status of a strategy execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    """Result of a single strategy execution."""

    execution_id: str
    strategy_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Output
    signals_generated: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    error_type: str = ""

    # Observability
    trace_id: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "signals_generated": self.signals_generated,
            "error": self.error,
            "error_type": self.error_type,
            "trace_id": self.trace_id,
            "metrics": self.metrics,
        }


class StrategyExecutor:
    """Executes strategy logic in a controlled environment.

    The executor is responsible for:
        - Context provisioning
        - Timeout enforcement
        - Error boundary
        - Result collection
        - Execution metrics

    Note: This is the lifecycle executor. The signal pipeline execution
    will be handled by the Signal Engine (Part 1.2).
    """

    def __init__(self) -> None:
        # Store registered execution functions
        self._executors: Dict[str, Any] = {}

        self._running_executions: Dict[str, ExecutionResult] = {}
        self._completed_executions: Dict[str, List[ExecutionResult]] = {}
        self._max_history: int = 500

        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyExecutor initialized")

    async def shutdown(self) -> None:
        self._executors.clear()
        self._running_executions.clear()
        self._completed_executions.clear()
        self._initialized = False
        logger.info("StrategyExecutor shut down")

    # ── Registration ──

    def register_executor(
        self,
        strategy_id: str,
        executor_fn,
    ) -> None:
        """Register an execution function for a strategy."""
        self._executors[strategy_id] = executor_fn

    def unregister_executor(self, strategy_id: str) -> None:
        self._executors.pop(strategy_id, None)

    # ── Execution ──

    async def execute(
        self,
        strategy_id: str,
        context: StrategyExecutionContext,
    ) -> ExecutionResult:
        """Execute a strategy with the given context.

        Args:
            strategy_id: The strategy to execute.
            context: The execution context.

        Returns:
            An ExecutionResult capturing the outcome.
        """
        import uuid

        execution_id = uuid.uuid4().hex[:12]
        result = ExecutionResult(
            execution_id=execution_id,
            strategy_id=strategy_id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            trace_id=context.trace_id,
        )

        self._running_executions[execution_id] = result

        try:
            start = time.monotonic()

            executor_fn = self._executors.get(strategy_id)
            if executor_fn is None:
                raise RuntimeError(f"No executor registered for strategy: {strategy_id}")

            # Timeout logic
            import asyncio

            try:
                output = await asyncio.wait_for(
                    executor_fn(context),
                    timeout=context.timeout_seconds,
                )
            except asyncio.TimeoutError:
                result.status = ExecutionStatus.TIMEOUT
                result.error = f"Execution timed out after {context.timeout_seconds}s"
                result.error_type = "TimeoutError"
                result.duration_ms = (time.monotonic() - start) * 1000
                result.completed_at = datetime.now(timezone.utc)
                self._archive_result(strategy_id, result)
                return result

            elapsed = (time.monotonic() - start) * 1000

            result.status = ExecutionStatus.COMPLETED
            result.duration_ms = elapsed
            result.completed_at = datetime.now(timezone.utc)

            if isinstance(output, dict):
                result.signals_generated = output.get("signals_generated", 0)
                result.data = output
                result.metrics = {
                    "execution_latency_ms": elapsed,
                    "context": context.to_dict(),
                }

            logger.info(
                "Execution complete: %s/%s status=%s signals=%d duration=%.1fms",
                strategy_id,
                execution_id,
                result.status.value,
                result.signals_generated,
                elapsed,
            )

        except Exception as e:
            elapsed = (time.monotonic() - time.monotonic())  # approximate
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            result.error_type = type(e).__name__
            result.completed_at = datetime.now(timezone.utc)
            logger.exception(
                "Execution failed: %s/%s - %s: %s",
                strategy_id,
                execution_id,
                type(e).__name__,
                e,
            )
        finally:
            self._running_executions.pop(execution_id, None)

        self._archive_result(strategy_id, result)
        return result

    async def execute_batch(
        self,
        executions: List[tuple[str, StrategyExecutionContext]],
    ) -> List[ExecutionResult]:
        """Execute multiple strategies in parallel."""
        import asyncio

        tasks = [
            self.execute(strategy_id, context)
            for strategy_id, context in executions
        ]
        return await asyncio.gather(*tasks, return_exceptions=False)

    # ── Lookup ──

    def get_running(self) -> List[ExecutionResult]:
        return list(self._running_executions.values())

    def get_history(
        self,
        strategy_id: str,
        limit: int = 50,
    ) -> List[ExecutionResult]:
        history = self._completed_executions.get(strategy_id, [])
        return history[-limit:]

    def get_execution(self, execution_id: str) -> Optional[ExecutionResult]:
        if execution_id in self._running_executions:
            return self._running_executions[execution_id]
        for history in self._completed_executions.values():
            for result in history:
                if result.execution_id == execution_id:
                    return result
        return None

    # ── Internals ──

    def _archive_result(
        self,
        strategy_id: str,
        result: ExecutionResult,
    ) -> None:
        self._completed_executions.setdefault(strategy_id, []).append(result)
        history = self._completed_executions[strategy_id]
        if len(history) > self._max_history:
            self._completed_executions[strategy_id] = history[-self._max_history:]

    def get_summary(self) -> Dict[str, Any]:
        total_completed = sum(
            len(h) for h in self._completed_executions.values()
        )
        return {
            "running": len(self._running_executions),
            "total_completed": total_completed,
            "registered_executors": len(self._executors),
            "initialized": self._initialized,
        }
