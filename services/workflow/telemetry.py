"""Workflow Telemetry — unified tracing, logging, and metrics pipeline.

The :class:`WorkflowTelemetry` integrates three observability pillars:
* **Tracing** — distributed trace context propagation across workflow nodes
* **Logging** — structured logging with correlation IDs
* **Metrics** — Prometheus-compatible metric collection

All workflow lifecycle events flow through this pipeline, ensuring
consistent observability across the entire workflow execution.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, Optional

from .metrics import WorkflowMetrics

logger = logging.getLogger(__name__)


class WorkflowTelemetry:
    """Unified observability for workflow execution.

    Integrates tracing, logging, and metrics into a single pipeline.
    Each workflow execution gets a trace context that propagates through
    all nodes, enabling end-to-end visibility.
    """

    def __init__(self, *, metrics: Optional[WorkflowMetrics] = None) -> None:
        self._metrics = metrics or WorkflowMetrics()
        self._active_traces: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Trace management
    # ------------------------------------------------------------------

    def start_trace(
        self,
        workflow_id: str,
        execution_id: str,
        *,
        trace_id: Optional[str] = None,
    ) -> str:
        """Start a new trace for a workflow execution.

        Returns the trace_id.
        """
        trace_id = trace_id or str(uuid.uuid4())
        self._active_traces[execution_id] = {
            "trace_id": trace_id,
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "started_at": datetime.utcnow(),
            "spans": [],
        }
        self._metrics.increment_execution_total("started")
        logger.info(
            "Trace started: workflow=%s execution=%s trace=%s",
            workflow_id, execution_id, trace_id,
        )
        return trace_id

    def end_trace(self, execution_id: str, *, status: str = "completed") -> None:
        """End a trace for a workflow execution."""
        trace = self._active_traces.pop(execution_id, None)
        if trace:
            duration = (datetime.utcnow() - trace["started_at"]).total_seconds()
            self._metrics.observe_execution_duration(duration)
            self._metrics.increment_execution_total(status)
            logger.info(
                "Trace ended: execution=%s status=%s duration=%.3fs spans=%d",
                execution_id, status, duration, len(trace["spans"]),
            )

    def get_trace(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return the trace context for an execution."""
        return self._active_traces.get(execution_id)

    # ------------------------------------------------------------------
    # Span management
    # ------------------------------------------------------------------

    @contextmanager
    def span(
        self,
        execution_id: str,
        node_id: str,
        *,
        node_type: str = "task",
    ) -> Iterator[Dict[str, Any]]:
        """Context manager for a workflow node execution span.

        Usage::

            with telemetry.span(execution_id, "validate_order") as span_ctx:
                result = await do_work()
                span_ctx["result"] = "success"
        """
        span_id = str(uuid.uuid4())[:8]
        span_data: Dict[str, Any] = {
            "span_id": span_id,
            "node_id": node_id,
            "node_type": node_type,
            "started_at": time.time(),
            "result": None,
            "error": None,
        }

        trace = self._active_traces.get(execution_id)
        if trace:
            trace["spans"].append(span_data)

        logger.debug("Span start: execution=%s node=%s span=%s", execution_id, node_id, span_id)

        try:
            yield span_data
            span_data["result"] = "success"
        except Exception as exc:
            span_data["result"] = "error"
            span_data["error"] = str(exc)
            logger.error("Span error: execution=%s node=%s span=%s: %s", execution_id, node_id, span_id, exc)
            raise
        finally:
            span_data["duration_seconds"] = time.time() - span_data["started_at"]
            if span_data["duration_seconds"] is not None:
                self._metrics.observe_node_duration(float(span_data["duration_seconds"]))
            logger.debug(
                "Span end: execution=%s node=%s span=%s duration=%.3fs result=%s",
                execution_id, node_id, span_id,
                span_data.get("duration_seconds", 0),
                span_data.get("result"),
            )

    # ------------------------------------------------------------------
    # Lifecycle event logging
    # ------------------------------------------------------------------

    def log_workflow_started(self, workflow_id: str, execution_id: str) -> None:
        logger.info("Workflow started: workflow=%s execution=%s", workflow_id, execution_id)
        self._metrics.increment_execution_total("started")

    def log_workflow_completed(self, workflow_id: str, execution_id: str, duration: float) -> None:
        logger.info("Workflow completed: workflow=%s execution=%s duration=%.3fs", workflow_id, execution_id, duration)
        self._metrics.increment_execution_total("completed")
        self._metrics.observe_execution_duration(duration)

    def log_workflow_failed(self, workflow_id: str, execution_id: str, error: str) -> None:
        logger.error("Workflow failed: workflow=%s execution=%s error=%s", workflow_id, execution_id, error)
        self._metrics.increment_execution_total("failed")

    def log_workflow_cancelled(self, workflow_id: str, execution_id: str) -> None:
        logger.warning("Workflow cancelled: workflow=%s execution=%s", workflow_id, execution_id)
        self._metrics.increment_execution_total("cancelled")

    def log_node_started(self, execution_id: str, node_id: str, node_type: str) -> None:
        logger.debug("Node started: execution=%s node=%s type=%s", execution_id, node_id, node_type)

    def log_node_completed(self, execution_id: str, node_id: str, duration: float) -> None:
        logger.debug("Node completed: execution=%s node=%s duration=%.3fs", execution_id, node_id, duration)

    def log_node_failed(self, execution_id: str, node_id: str, error: str) -> None:
        logger.error("Node failed: execution=%s node=%s error=%s", execution_id, node_id, error)

    def log_registration(self, workflow_id: str, version: str) -> None:
        logger.info("Workflow registered: workflow=%s version=%s", workflow_id, version)
        self._metrics.increment_registration_total()

    def log_snapshot(self, execution_id: str, snapshot_id: str) -> None:
        logger.debug("Snapshot taken: execution=%s snapshot=%s", execution_id, snapshot_id)
        self._metrics.increment_snapshot_total()

    # ------------------------------------------------------------------
    # Metrics access
    # ------------------------------------------------------------------

    @property
    def metrics(self) -> WorkflowMetrics:
        return self._metrics

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Return current metrics values."""
        return self._metrics.get_all_metrics()
