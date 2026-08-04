"""
Secrets telemetry module.

Provides tracing and metrics telemetry for
secret operations, auto-generating audit logs,
trace spans, and metrics for all secret CRUD
operations. Integrates with the existing audit
and metrics components.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .constants import AuditAction

logger = logging.getLogger(__name__)


@dataclass
class SecretTraceSpan:
    """
    A single trace span for a secret operation.

    Captures the full lifecycle of a secret
    operation including timing, status, and
    correlation identifiers for distributed
    tracing.

    Attributes:
        span_id: Unique span identifier.
        trace_id: Correlation trace identifier.
        parent_id: Parent span identifier.
        operation: Operation type (get, set, etc.).
        key: Secret key involved.
        namespace: Namespace.
        provider: Provider used.
        start_time: Span start timestamp.
        end_time: Span end timestamp.
        duration_ms: Operation duration in ms.
        status: Operation status (ok, error).
        error: Error message if failed.
        metadata: Additional context.
    """

    span_id: str = ""
    trace_id: str = ""
    parent_id: str = ""
    operation: str = ""
    key: str = ""
    namespace: str = "default"
    provider: str = ""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    status: str = "ok"
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(
        self,
        status: str = "ok",
        error: str = "",
    ) -> None:
        """
        Finish the trace span.

        Args:
            status: Final status ("ok" or "error").
            error: Error message if failed.
        """
        self.end_time = datetime.utcnow()
        self.status = status
        self.error = error
        self.duration_ms = (
            (self.end_time - self.start_time).total_seconds()
            * 1000
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "operation": self.operation,
            "key": self.key,
            "namespace": self.namespace,
            "provider": self.provider,
            "start_time": self.start_time.isoformat() + "Z",
            "end_time": (
                self.end_time.isoformat() + "Z"
                if self.end_time
                else None
            ),
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "error": self.error,
            "metadata": self.metadata,
        }


class SecretsTelemetry:
    """
    Secrets telemetry collector.

    Provides unified tracing, audit, and metrics
    for all secret operations. Automatically
    generates trace spans, audit log entries,
    and metric records for get/set/update/delete/
    rotate operations.

    Integration:
        - SecretsAudit: Auto-logs audit entries
        - SecretsMetrics: Auto-records metrics
        - SecretTraceSpan: Creates trace spans

    Usage:
        telemetry = SecretsTelemetry(
            audit=audit,
            metrics=metrics,
        )
        span = telemetry.start_span(
            operation="get",
            key="db/password",
        )
        # ... do work ...
        telemetry.end_span(span)
        traces = telemetry.get_traces()
    """

    MAX_TRACES = 10000

    def __init__(
        self,
        audit: Optional[Any] = None,
        metrics: Optional[Any] = None,
        enabled: bool = True,
    ) -> None:
        """
        Initialize telemetry.

        Args:
            audit: SecretsAudit instance.
            metrics: SecretsMetrics instance.
            enabled: Whether telemetry is enabled.
        """
        self._audit = audit
        self._metrics = metrics
        self._enabled = enabled
        self._lock = threading.RLock()
        self._traces: List[SecretTraceSpan] = []
        self._trace_id = uuid.uuid4().hex
        self._operations: Dict[str, int] = {}
        self._total_duration_ms: Dict[str, float] = {}
        self._errors: Dict[str, int] = {}
        self._listeners: List[Callable] = []

    # ── Span Management ──

    def start_span(
        self,
        operation: str,
        key: str = "",
        namespace: str = "default",
        provider: str = "",
        parent_id: str = "",
        **metadata: Any,
    ) -> SecretTraceSpan:
        """
        Start a new trace span for an operation.

        Args:
            operation: Operation type.
            key: Secret key.
            namespace: Namespace.
            provider: Provider name.
            parent_id: Parent span ID.
            **metadata: Additional context.

        Returns:
            The created SecretTraceSpan.
        """
        span = SecretTraceSpan(
            span_id=uuid.uuid4().hex[:16],
            trace_id=self._trace_id,
            parent_id=parent_id,
            operation=operation,
            key=key,
            namespace=namespace,
            provider=provider,
            start_time=datetime.utcnow(),
            metadata=metadata,
        )
        return span

    def end_span(
        self,
        span: SecretTraceSpan,
        status: str = "ok",
        error: str = "",
    ) -> None:
        """
        End a trace span and record it.

        Args:
            span: The span to end.
            status: Final status.
            error: Error message if failed.
        """
        span.finish(status=status, error=error)

        if not self._enabled:
            return

        with self._lock:
            self._traces.append(span)

            # Trim if over limit
            if len(self._traces) > self.MAX_TRACES:
                self._traces = self._traces[-self.MAX_TRACES:]

            # Update operation counters
            op = span.operation
            self._operations[op] = self._operations.get(op, 0) + 1
            self._total_duration_ms[op] = (
                self._total_duration_ms.get(op, 0.0)
                + span.duration_ms
            )

            if status != "ok":
                self._errors[op] = self._errors.get(op, 0) + 1

        # Notify listeners
        self._notify_listeners(span)

    # ── High-Level Operations ──

    def record_operation(
        self,
        operation: str,
        key: str,
        namespace: str = "default",
        provider: str = "",
        success: bool = True,
        latency_ms: float = 0.0,
        operator: str = "system",
        source: str = "",
        cache_hit: bool = False,
        **details: Any,
    ) -> SecretTraceSpan:
        """
        Record a complete secret operation.

        Automatically generates an audit entry,
        records metrics, and creates a trace span
        for the operation.

        Args:
            operation: Operation type (get, set, update, delete, rotate).
            key: Secret key.
            namespace: Namespace.
            provider: Provider name.
            success: Whether the operation succeeded.
            latency_ms: Operation latency in ms.
            operator: Who performed the operation.
            source: Source of the operation.
            cache_hit: Whether value came from cache.
            **details: Additional context.

        Returns:
            The created SecretTraceSpan.
        """
        now = datetime.utcnow()
        span = SecretTraceSpan(
            span_id=uuid.uuid4().hex[:16],
            trace_id=self._trace_id,
            operation=operation,
            key=key,
            namespace=namespace,
            provider=provider,
            start_time=now,
            status="ok" if success else "error",
            metadata=details,
        )
        span.end_time = now
        span.duration_ms = latency_ms

        if not self._enabled:
            return span

        with self._lock:
            self._traces.append(span)
            if len(self._traces) > self.MAX_TRACES:
                self._traces = self._traces[-self.MAX_TRACES:]

            op = span.operation
            self._operations[op] = self._operations.get(op, 0) + 1
            self._total_duration_ms[op] = (
                self._total_duration_ms.get(op, 0.0)
                + latency_ms
            )
            if not success:
                self._errors[op] = self._errors.get(op, 0) + 1

        # Audit integration
        self._record_audit(
            operation=operation,
            key=key,
            namespace=namespace,
            operator=operator,
            source=source,
            success=success,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            trace_id=span.span_id,
            details=details,
        )

        # Metrics integration
        self._record_metrics(
            operation=operation,
            provider=provider,
            namespace=namespace,
            success=success,
            latency_ms=latency_ms,
            cache_hit=cache_hit,
        )

        return span

    def _record_audit(
        self,
        operation: str,
        key: str,
        namespace: str,
        operator: str,
        source: str,
        success: bool,
        cache_hit: bool,
        latency_ms: float,
        trace_id: str,
        details: Dict[str, Any],
    ) -> None:
        """Record an audit entry via the audit component."""
        if self._audit is None:
            return

        try:
            if operation == AuditAction.READ.value:
                self._audit.log_access(
                    key=key,
                    namespace=namespace,
                    operator=operator,
                    allowed=success,
                    cache_hit=cache_hit,
                    latency_ms=latency_ms,
                    source=source,
                    trace_id=trace_id,
                    **details,
                )
            elif operation in (
                AuditAction.SET.value,
                AuditAction.UPDATE.value,
                AuditAction.DELETE.value,
                AuditAction.ROTATE.value,
                AuditAction.CREATE.value,
                AuditAction.WRITE.value,
            ):
                self._audit.log_change(
                    key=key,
                    action=operation,
                    namespace=namespace,
                    operator=operator,
                    source=source,
                    trace_id=trace_id,
                    **details,
                )
            elif not success:
                self._audit.log_error(
                    key=key,
                    error=details.get("error", operation),
                    namespace=namespace,
                    operator=operator,
                    trace_id=trace_id,
                    **details,
                )
        except Exception as e:
            logger.warning("Audit recording failed: %s", e)

    def _record_metrics(
        self,
        operation: str,
        provider: str,
        namespace: str,
        success: bool,
        latency_ms: float,
        cache_hit: bool,
    ) -> None:
        """Record metrics via the metrics component."""
        if self._metrics is None:
            return

        try:
            if operation == AuditAction.READ.value:
                self._metrics.record_read(
                    provider=provider or "local",
                    namespace=namespace,
                )
                if cache_hit:
                    self._metrics.record_cache_hit(
                        provider=provider or "local",
                        namespace=namespace,
                    )
                else:
                    self._metrics.record_cache_miss(
                        provider=provider or "local",
                        namespace=namespace,
                    )

            if latency_ms > 0:
                self._metrics.record_provider_latency(
                    provider=provider or "local",
                    operation=operation,
                    latency=latency_ms / 1000.0,
                )
        except Exception as e:
            logger.warning("Metrics recording failed: %s", e)

    # ── Query ──

    def get_traces(
        self,
        operation: Optional[str] = None,
        key_pattern: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get recorded trace spans.

        Args:
            operation: Filter by operation type.
            key_pattern: Filter by key pattern.
            limit: Max spans to return.

        Returns:
            List of trace span dictionaries.
        """
        import fnmatch

        with self._lock:
            results = list(reversed(self._traces))

            if operation:
                results = [
                    s for s in results if s.operation == operation
                ]
            if key_pattern:
                results = [
                    s
                    for s in results
                    if fnmatch.fnmatch(s.key, key_pattern)
                ]

            return [s.to_dict() for s in results[:limit]]

    def get_recent_traces(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get most recent trace spans."""
        return self.get_traces(limit=limit)

    def get_trace_for_key(
        self,
        key: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get trace spans for a specific key."""
        return self.get_traces(key_pattern=key, limit=limit)

    # ── Listeners ──

    def add_listener(
        self,
        listener: Callable,
    ) -> None:
        """
        Add a trace event listener.

        Args:
            listener: Callable(SecretTraceSpan) to invoke.
        """
        with self._lock:
            self._listeners.append(listener)

    def remove_listener(
        self,
        listener: Callable,
    ) -> None:
        """Remove a trace event listener."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify_listeners(self, span: SecretTraceSpan) -> None:
        """Notify all listeners of a new span."""
        for listener in self._listeners:
            try:
                listener(span)
            except Exception as e:
                logger.warning(
                    "Trace listener error: %s", e,
                )

    # ── Management ──

    @property
    def enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable/disable telemetry."""
        self._enabled = value

    @property
    def trace_id(self) -> str:
        """Get the current trace ID."""
        return self._trace_id

    def new_trace(self) -> str:
        """
        Start a new trace ID for correlation.

        Returns:
            The new trace ID.
        """
        with self._lock:
            self._trace_id = uuid.uuid4().hex
            return self._trace_id

    def clear(self) -> None:
        """Clear all recorded traces."""
        with self._lock:
            self._traces.clear()
            self._operations.clear()
            self._total_duration_ms.clear()
            self._errors.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get telemetry statistics.

        Returns:
            Statistics dictionary with operation
            counts, durations, and error rates.
        """
        with self._lock:
            total_ops = sum(self._operations.values())
            avg_duration: Dict[str, float] = {}
            for op, count in self._operations.items():
                total_dur = self._total_duration_ms.get(op, 0.0)
                avg_duration[op] = (
                    total_dur / count if count > 0 else 0.0
                )

            error_counts = dict(self._errors)
            success_counts = {
                op: self._operations.get(op, 0)
                - error_counts.get(op, 0)
                for op in self._operations
            }

            return {
                "enabled": self._enabled,
                "total_traces": len(self._traces),
                "total_operations": total_ops,
                "operations": dict(self._operations),
                "success_by_operation": success_counts,
                "errors_by_operation": error_counts,
                "avg_duration_ms": {
                    k: round(v, 2)
                    for k, v in avg_duration.items()
                },
                "total_duration_ms": {
                    k: round(v, 2)
                    for k, v in self._total_duration_ms.items()
                },
                "active_trace_id": self._trace_id,
                "listeners": len(self._listeners),
            }