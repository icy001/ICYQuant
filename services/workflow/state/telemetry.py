"""State telemetry — unified tracing, logging, and metrics for state operations.

Records:
  - State transitions
  - Checkpoint timeline
  - Recovery timeline
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from .metrics import StateMetricsCollector

logger = logging.getLogger(__name__)


class StateTelemetry:
    """Unified telemetry for workflow state operations.

    Integrates:
      - Workflow State → Tracing
      - Logging → Structured
      - Metrics → Collection
      - Audit → Event store
    """

    def __init__(self, metrics: Optional[StateMetricsCollector] = None):
        self._metrics = metrics or StateMetricsCollector()

    # ---- Operation tracing --------------------------------------------------

    @asynccontextmanager
    async def trace_operation(
        self,
        operation: str,
        execution_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Trace an operation with timing and metrics."""
        start = time.perf_counter()
        context = {
            "operation": operation,
            "execution_id": execution_id,
            "metadata": metadata or {},
        }
        logger.info("State operation started: %s (exec=%s)", operation, execution_id)
        try:
            yield context
        except Exception as e:
            logger.exception("State operation failed: %s (exec=%s)", operation, execution_id)
            raise
        finally:
            elapsed = time.perf_counter() - start
            logger.info("State operation completed: %s (exec=%s) in %.3fs", operation, execution_id, elapsed)
            context["duration_seconds"] = elapsed

    # ---- State change logging -----------------------------------------------

    def log_transition(
        self,
        execution_id: str,
        from_status: str,
        to_status: str,
        node_id: Optional[str] = None,
    ) -> None:
        """Log a state transition with structured logging."""
        if node_id:
            logger.info(
                "State transition: exec=%s node=%s %s→%s",
                execution_id, node_id, from_status, to_status,
            )
        else:
            logger.info(
                "State transition: exec=%s %s→%s",
                execution_id, from_status, to_status,
            )
        self._metrics.record_transition()

    def log_checkpoint(
        self, execution_id: str, version: int, trigger: str
    ) -> None:
        """Log a checkpoint creation."""
        logger.info("Checkpoint: exec=%s v=%d trigger=%s", execution_id, version, trigger)
        self._metrics.record_checkpoint()

    def log_recovery(
        self, execution_id: str, duration_seconds: float, success: bool
    ) -> None:
        """Log a recovery operation."""
        status = "success" if success else "failed"
        logger.info("Recovery %s: exec=%s duration=%.3fs", status, execution_id, duration_seconds)
        self._metrics.record_recovery()
        self._metrics.set_recovery_duration(duration_seconds)

    # ---- Metrics access -----------------------------------------------------

    @property
    def metrics(self) -> StateMetricsCollector:
        return self._metrics
