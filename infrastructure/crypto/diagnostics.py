"""
Crypto diagnostics.

Provides diagnostic capabilities for
the crypto platform including operation
tracing, error reporting, and performance
analysis.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CryptoOperationRecord:
    """
    Record of a cryptographic operation.

    Attributes:
        operation: Operation name (encrypt, decrypt, sign, etc.).
        algorithm: Algorithm used.
        success: Whether operation succeeded.
        duration_ms: Operation duration.
        key_id: Key identifier.
        error: Error message if failed.
        timestamp: Operation timestamp.
        metadata: Additional metadata.
    """

    operation: str = ""
    algorithm: str = ""
    success: bool = True
    duration_ms: float = 0.0
    key_id: str = ""
    error: str = ""
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "algorithm": self.algorithm,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "key_id": self.key_id,
            "error": self.error,
            "timestamp": (
                self.timestamp.isoformat() + "Z"
                if self.timestamp
                else None
            ),
            "metadata": self.metadata,
        }


@dataclass
class CryptoErrorRecord:
    """
    Record of a crypto error.

    Attributes:
        error_type: Error type.
        message: Error message.
        operation: Operation that failed.
        algorithm: Algorithm used.
        key_id: Key identifier.
        stack_trace: Error stack trace.
        timestamp: Error timestamp.
    """

    error_type: str = ""
    message: str = ""
    operation: str = ""
    algorithm: str = ""
    key_id: str = ""
    stack_trace: str = ""
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "operation": self.operation,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "stack_trace": self.stack_trace[:500] if self.stack_trace else "",
            "timestamp": (
                self.timestamp.isoformat() + "Z"
                if self.timestamp
                else None
            ),
        }


class CryptoDiagnostics:
    """
    Crypto diagnostics collector.

    Collects and reports diagnostic
    information for cryptographic
    operations including performance
    metrics, error tracking, and
    operation history.

    Features:
    - Operation tracing
    - Error tracking and aggregation
    - Performance analysis
    - Operation replay support
    - Thread-safe collection
    """

    def __init__(
        self,
        max_history: int = 1000,
        max_errors: int = 500,
    ) -> None:
        """
        Initialize diagnostics.

        Args:
            max_history: Maximum operation history entries.
            max_errors: Maximum error entries.
        """
        self._lock = threading.RLock()
        self._operations: List[CryptoOperationRecord] = []
        self._errors: List[CryptoErrorRecord] = []
        self._max_history = max_history
        self._max_errors = max_errors

    def record_operation(
        self,
        operation: str,
        algorithm: str = "",
        success: bool = True,
        duration_ms: float = 0.0,
        key_id: str = "",
        error: str = "",
        **metadata: Any,
    ) -> None:
        """
        Record a cryptographic operation.

        Args:
            operation: Operation name.
            algorithm: Algorithm used.
            success: Whether operation succeeded.
            duration_ms: Duration in milliseconds.
            key_id: Key identifier.
            error: Error message if failed.
            **metadata: Additional metadata.
        """
        with self._lock:
            record = CryptoOperationRecord(
                operation=operation,
                algorithm=algorithm,
                success=success,
                duration_ms=duration_ms,
                key_id=key_id,
                error=error,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            )

            self._operations.append(record)

            # Trim history
            if len(self._operations) > self._max_history:
                self._operations = self._operations[-self._max_history:]

            # Record errors separately
            if not success and error:
                self._errors.append(CryptoErrorRecord(
                    error_type=type(error).__name__ if error else "Unknown",
                    message=str(error),
                    operation=operation,
                    algorithm=algorithm,
                    key_id=key_id,
                    stack_trace="",
                    timestamp=datetime.utcnow(),
                ))
                if len(self._errors) > self._max_errors:
                    self._errors = self._errors[-self._max_errors:]

    def get_operations(
        self,
        operation: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get operation history.

        Args:
            operation: Filter by operation type.
            success: Filter by success status.
            limit: Maximum entries to return.

        Returns:
            List of operation records.
        """
        with self._lock:
            results = list(reversed(self._operations))

            if operation:
                results = [
                    r for r in results if r.operation == operation
                ]
            if success is not None:
                results = [
                    r for r in results if r.success == success
                ]

            return [r.to_dict() for r in results[:limit]]

    def get_errors(
        self,
        operation: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get error history."""
        with self._lock:
            results = list(reversed(self._errors))
            if operation:
                results = [
                    r for r in results if r.operation == operation
                ]
            return [r.to_dict() for r in results[:limit]]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get aggregated performance statistics."""
        with self._lock:
            by_operation: Dict[str, List[float]] = {}
            for op in self._operations:
                if op.duration_ms > 0:
                    by_operation.setdefault(op.operation, []).append(
                        op.duration_ms
                    )

            perf_stats = {}
            for op_name, durations in by_operation.items():
                perf_stats[op_name] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "min_ms": min(durations),
                    "max_ms": max(durations),
                    "p95_ms": sorted(durations)[
                        int(len(durations) * 0.95)
                    ] if durations else 0,
                }

            return perf_stats

    def clear_history(self) -> None:
        """Clear all operation history."""
        with self._lock:
            self._operations.clear()
            self._errors.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get diagnostics statistics."""
        with self._lock:
            total_ops = len(self._operations)
            successful = sum(
                1 for r in self._operations if r.success
            )
            failed = total_ops - successful

            return {
                "total_operations": total_ops,
                "successful": successful,
                "failed": failed,
                "success_rate": (
                    successful / total_ops * 100
                    if total_ops > 0
                    else 0
                ),
                "total_errors": len(self._errors),
                "performance": self.get_performance_stats(),
            }
