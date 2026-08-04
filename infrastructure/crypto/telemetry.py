"""
Crypto telemetry.

Provides unified telemetry for the crypto
platform, automatically generating audit logs,
trace spans, and metrics for every cryptographic
operation.

Telemetry Flow:
    Crypto Operation
        ↓
    Logging
        ↓
    Tracing
        ↓
    Metrics

Usage:
    telemetry = CryptoTelemetry()

    telemetry.record_operation(
        "encrypt", "aes-256-gcm",
        key_id="k1", success=True, duration_ms=5.0,
    )
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .metrics import CryptoMetrics
from .diagnostics import CryptoDiagnostics

logger = logging.getLogger(__name__)


class CryptoTraceSpan:
    """
    A trace span for a crypto operation.

    Records timing and context for a single
    cryptographic operation.

    Attributes:
        span_id: Unique span identifier.
        trace_id: Trace identifier for correlation.
        operation: Operation name (encrypt, decrypt, sign, etc.).
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
        self.duration = (
            self.end_time - self.start_time
        ).total_seconds()
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
            "end_time": (
                self.end_time.isoformat()
                if self.end_time
                else None
            ),
            "duration": self.duration,
            "attributes": self.attributes,
            "status": self.status,
            "error": self.error,
        }


class CryptoTelemetry:
    """
    Crypto telemetry manager.

    Automatically generates:
    - Audit logs for every crypto operation
    - Trace spans for every crypto operation
    - Metrics for every crypto event

    Integrates with CryptoMetrics and
    CryptoDiagnostics for comprehensive
    observability.

    Thread-safe with RLock for concurrent
    access from multiple crypto pipelines.

    Usage:
        telemetry = CryptoTelemetry()

        # Record a crypto operation
        telemetry.record_operation(
            "encrypt", "aes-256-gcm",
            key_id="k1",
            success=True,
            duration_ms=5.0,
        )

        # Start a trace span
        with telemetry.trace("encrypt") as span:
            span.set_attribute("algorithm", "aes-256-gcm")
            # ... do encryption ...
    """

    def __init__(
        self,
        metrics: Optional[CryptoMetrics] = None,
        diagnostics: Optional[CryptoDiagnostics] = None,
        log_level: int = logging.INFO,
        max_trace_history: int = 1000,
    ) -> None:
        """
        Initialize telemetry.

        Args:
            metrics: CryptoMetrics instance.
            diagnostics: CryptoDiagnostics instance.
            log_level: Logging level.
            max_trace_history: Maximum trace history size.
        """
        self._logger = logging.getLogger(
            "crypto.telemetry"
        )
        self._logger.setLevel(log_level)

        self._metrics = metrics or CryptoMetrics()
        self._diagnostics = diagnostics or CryptoDiagnostics()

        self._trace_history: List[Dict[str, Any]] = []
        self._max_trace_history = max_trace_history
        self._lock = threading.RLock()

    # ── Logging ──

    def log_operation(
        self,
        operation: str,
        algorithm: str = "",
        key_id: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a crypto operation."""
        self._logger.info(
            "Crypto operation: %s (%s) key=%s success=%s duration=%.3fms - %s",
            operation,
            algorithm,
            key_id,
            success,
            duration_ms,
            details or {},
        )

    def log_error(
        self,
        operation: str,
        algorithm: str = "",
        key_id: str = "",
        error: str = "",
    ) -> None:
        """Log a crypto error."""
        self._logger.error(
            "Crypto error in %s (%s) key=%s: %s",
            operation,
            algorithm,
            key_id,
            error,
        )

    # ── Tracing ──

    def trace(
        self,
        operation: str,
    ) -> CryptoTraceSpan:
        """
        Start a trace span.

        Args:
            operation: Operation name.

        Returns:
            CryptoTraceSpan instance.
        """
        return CryptoTraceSpan(operation)

    def record_trace(
        self,
        span: CryptoTraceSpan,
    ) -> None:
        """
        Record a completed trace span.

        Args:
            span: Completed span.
        """
        with self._lock:
            self._trace_history.append(span.to_dict())
            if len(self._trace_history) > (
                self._max_trace_history
            ):
                self._trace_history.pop(0)

    # ── Metrics Integration ──

    def _record_metrics(
        self,
        operation: str,
        algorithm: str,
        success: bool,
        duration_ms: float,
        key_id: str,
    ) -> None:
        """Record operation metrics via CryptoMetrics."""
        duration_s = duration_ms / 1000.0

        if operation == "encrypt":
            self._metrics.record_encrypt(
                algorithm=algorithm,
                success=success,
                duration=duration_s,
            )
        elif operation == "decrypt":
            self._metrics.record_decrypt(
                algorithm=algorithm,
                success=success,
                duration=duration_s,
            )
        elif operation == "sign":
            self._metrics.record_sign(
                algorithm=algorithm,
                success=success,
                duration=duration_s,
            )
        elif operation == "verify":
            self._metrics.record_verify(
                algorithm=algorithm,
                duration=duration_s,
            )
        elif operation == "hash":
            self._metrics.record_hash(
                algorithm=algorithm,
                duration=duration_s,
            )

    def _record_diagnostics(
        self,
        operation: str,
        algorithm: str,
        success: bool,
        duration_ms: float,
        key_id: str,
        error: str,
    ) -> None:
        """Record operation diagnostics."""
        self._diagnostics.record_operation(
            operation=operation,
            algorithm=algorithm,
            success=success,
            duration_ms=duration_ms,
            key_id=key_id,
            error=error,
        )

    # ── Combined Recording ──

    def record_operation(
        self,
        operation: str,
        algorithm: str = "",
        key_id: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
        error: str = "",
        **attributes: Any,
    ) -> Dict[str, Any]:
        """
        Record a complete crypto operation.

        Combines logging, tracing, metrics, and
        diagnostics into a single call.

        Args:
            operation: Operation name
                (encrypt, decrypt, sign, etc.).
            algorithm: Algorithm used
                (aes-256-gcm, rsa-2048, etc.).
            key_id: Key identifier.
            success: Whether operation succeeded.
            duration_ms: Operation duration
                in milliseconds.
            error: Error message if failed.
            **attributes: Additional span
                attributes.

        Returns:
            Complete event record with
            trace and span IDs.
        """
        span = self.trace(operation)
        span.set_attribute("algorithm", algorithm)
        span.set_attribute("key_id", key_id)
        span.set_attribute("success", success)

        for key, value in attributes.items():
            span.set_attribute(key, value)

        span.finish(
            status="ok" if success else "error",
            error=error if not success else None,
        )

        self.record_trace(span)

        if success:
            self.log_operation(
                operation=operation,
                algorithm=algorithm,
                key_id=key_id,
                success=success,
                duration_ms=duration_ms,
                details=attributes,
            )
        else:
            self.log_error(
                operation=operation,
                algorithm=algorithm,
                key_id=key_id,
                error=error,
            )

        self._record_metrics(
            operation=operation,
            algorithm=algorithm,
            success=success,
            duration_ms=duration_ms,
            key_id=key_id,
        )

        self._record_diagnostics(
            operation=operation,
            algorithm=algorithm,
            success=success,
            duration_ms=duration_ms,
            key_id=key_id,
            error=error,
        )

        return {
            "operation": operation,
            "algorithm": algorithm,
            "key_id": key_id,
            "success": success,
            "duration_ms": duration_ms,
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
                traces = [
                    t
                    for t in traces
                    if t["operation"] == operation
                ]
            return traces[-limit:]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """
        Get telemetry statistics.

        Returns:
            Statistics including trace
            counts and operation breakdown.
        """
        with self._lock:
            total = len(self._trace_history)
            if total == 0:
                return {
                    "total_traces": 0,
                    "metrics": self._metrics.get_stats(),
                    "diagnostics": self._diagnostics.get_stats(),
                }

            operations: Dict[str, int] = {}
            for trace in self._trace_history:
                op = trace["operation"]
                operations[op] = (
                    operations.get(op, 0) + 1
                )

            return {
                "total_traces": total,
                "operations": operations,
                "trace_history_size": len(
                    self._trace_history
                ),
                "max_trace_history": (
                    self._max_trace_history
                ),
                "metrics": self._metrics.get_stats(),
                "diagnostics": (
                    self._diagnostics.get_stats()
                ),
            }

    def clear_history(
        self,
    ) -> None:
        """Clear all trace history."""
        with self._lock:
            self._trace_history.clear()