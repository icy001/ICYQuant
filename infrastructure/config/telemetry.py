"""
Configuration telemetry.

Provides unified telemetry for the configuration
platform, automatically generating audit logs,
trace spans, and metrics for every configuration
change.

Telemetry Flow:
    Configuration Change
        ↓
    Logging
        ↓
    Tracing
        ↓
    Monitoring
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceSpan:
    """
    A trace span for a configuration operation.

    Records timing and context for a single
    configuration operation.

    Attributes:
        span_id: Unique span identifier.
        operation: Operation name.
        start_time: Start timestamp.
        end_time: End timestamp.
        duration: Duration in seconds.
        attributes: Span attributes.
        status: Span status (ok, error).
        error: Error message if failed.
    """

    def __init__(
        self,
        operation: str,
        trace_id: Optional[str] = None,
    ) -> None:
        self.span_id = uuid.uuid4().hex[:16]
        self.trace_id = trace_id or uuid.uuid4().hex[:16]
        self.operation = operation
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.duration: float = 0.0
        self.attributes: Dict[str, Any] = {}
        self.status: str = "ok"
        self.error: Optional[str] = None

    def set_attribute(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def finish(
        self,
        status: str = "ok",
        error: Optional[str] = None,
    ) -> None:
        """Finish the span."""
        self.end_time = datetime.utcnow()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.status = status
        self.error = error

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "attributes": self.attributes,
            "status": self.status,
            "error": self.error,
        }


class ConfigurationTelemetry:
    """
    Configuration telemetry manager.

    Automatically generates:
    - Audit logs for every configuration change
    - Trace spans for every configuration operation
    - Metrics for every configuration event

    Usage:
        telemetry = ConfigurationTelemetry()

        # Record a configuration change
        telemetry.record_change(
            operation="reload",
            operator="admin",
            changed_keys=["server.port"],
            old_values={"server.port": 8080},
            new_values={"server.port": 9090},
        )

        # Start a trace span
        with telemetry.trace("reload") as span:
            span.set_attribute("source", "file")
            # ... do reload ...
    """

    def __init__(
        self,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize telemetry.

        Args:
            log_level: Logging level.
        """
        self._logger = logging.getLogger("config.telemetry")
        self._logger.setLevel(log_level)

        self._trace_history: List[Dict[str, Any]] = []
        self._max_trace_history = 1000
        self._lock = threading.Lock()

    # ── Logging ──

    def log_change(
        self,
        operation: str,
        operator: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a configuration change."""
        self._logger.info(
            "Configuration change: %s by %s - %s",
            operation,
            operator,
            details or {},
        )

    def log_error(
        self,
        operation: str,
        error: str,
        operator: str = "system",
    ) -> None:
        """Log a configuration error."""
        self._logger.error(
            "Configuration error in %s by %s: %s",
            operation,
            operator,
            error,
        )

    # ── Tracing ──

    def trace(
        self,
        operation: str,
    ) -> "TraceSpan":
        """
        Start a trace span.

        Args:
            operation: Operation name.

        Returns:
            TraceSpan context manager.
        """
        span = TraceSpan(operation)
        return span

    def record_trace(
        self,
        span: TraceSpan,
    ) -> None:
        """
        Record a completed trace span.

        Args:
            span: Completed span.
        """
        with self._lock:
            self._trace_history.append(span.to_dict())
            if len(self._trace_history) > self._max_trace_history:
                self._trace_history.pop(0)

    # ── Combined Recording ──

    def record_change(
        self,
        operation: str,
        operator: str = "system",
        changed_keys: Optional[List[str]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        source: str = "system",
        reason: str = "",
        duration: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a complete configuration change event.

        Generates audit log, trace span, and metrics
        for the change.

        Args:
            operation: Operation type (reload, rollback, etc.).
            operator: Who triggered the change.
            changed_keys: Keys that changed.
            old_values: Previous values.
            new_values: New values.
            source: Source of the change.
            reason: Reason for the change.
            duration: Operation duration.
            success: Whether operation succeeded.
            error: Error message if failed.

        Returns:
            Complete event record.
        """
        span = self.trace(operation)
        span.set_attribute("operator", operator)
        span.set_attribute("source", source)
        span.set_attribute("success", success)

        if changed_keys:
            span.set_attribute("changed_keys", changed_keys)

        span.finish(
            status="ok" if success else "error",
            error=error,
        )

        self.record_trace(span)

        if success:
            self.log_change(
                operation=operation,
                operator=operator,
                details={
                    "changed_keys": changed_keys or [],
                    "source": source,
                    "reason": reason,
                    "duration": duration,
                },
            )
        else:
            self.log_error(
                operation=operation,
                error=error or "Unknown error",
                operator=operator,
            )

        return {
            "operation": operation,
            "operator": operator,
            "changed_keys": changed_keys or [],
            "old_values": old_values or {},
            "new_values": new_values or {},
            "source": source,
            "reason": reason,
            "duration": duration,
            "success": success,
            "error": error,
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Export ──

    def get_traces(
        self,
        operation: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get trace history.

        Args:
            operation: Filter by operation.
            limit: Max results.

        Returns:
            List of trace spans.
        """
        with self._lock:
            traces = self._trace_history
            if operation:
                traces = [t for t in traces if t["operation"] == operation]
            return traces[-limit:]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get telemetry statistics."""
        with self._lock:
            total = len(self._trace_history)
            if total == 0:
                return {"total_traces": 0}

            operations: Dict[str, int] = {}
            for trace in self._trace_history:
                op = trace["operation"]
                operations[op] = operations.get(op, 0) + 1

            return {
                "total_traces": total,
                "operations": operations,
                "trace_history_size": len(self._trace_history),
            }
