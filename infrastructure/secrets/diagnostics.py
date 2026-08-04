"""
Secrets diagnostics.

Provides diagnostic capabilities for
the secrets platform including operation
tracing, error reporting, and performance
analysis.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretOperationRecord:
    """
    Record of a secrets operation.

    Attributes:
        operation: Operation name (encrypt_secret, decrypt_secret, etc.).
        secret_key: Secret key involved.
        namespace: Namespace of the secret.
        success: Whether operation succeeded.
        duration_ms: Operation duration in milliseconds.
        timestamp: Operation timestamp.
        metadata: Additional metadata.
    """

    operation: str = ""
    secret_key: str = ""
    namespace: str = "default"
    success: bool = True
    duration_ms: float = 0.0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation,
            "secret_key": self.secret_key,
            "namespace": self.namespace,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 3),
            "timestamp": (
                self.timestamp.isoformat() + "Z"
                if self.timestamp
                else None
            ),
            "metadata": self.metadata,
        }


@dataclass
class SecretErrorRecord:
    """
    Record of a secrets error.

    Attributes:
        error_type: Error type.
        message: Error message.
        operation: Operation that failed.
        secret_key: Secret key involved.
        timestamp: Error timestamp.
    """

    error_type: str = ""
    message: str = ""
    operation: str = ""
    secret_key: str = ""
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type,
            "message": self.message[:500] if self.message else "",
            "operation": self.operation,
            "secret_key": self.secret_key,
            "timestamp": (
                self.timestamp.isoformat() + "Z"
                if self.timestamp
                else None
            ),
        }


class SecretsDiagnostics:
    """
    Secrets diagnostics collector.

    Collects and reports diagnostic
    information for secrets operations
    including performance metrics, error
    tracking, and operation history.

    Features:
    - Operation tracing with configurable max size
    - Error tracking and aggregation
    - Performance analysis per operation type
    - Thread-safe collection with RLock
    - Clear history support
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
        self._operations: List[SecretOperationRecord] = []
        self._errors: List[SecretErrorRecord] = []
        self._max_history = max_history
        self._max_errors = max_errors

    def record_operation(
        self,
        operation: str,
        secret_key: str = "",
        namespace: str = "default",
        success: bool = True,
        duration_ms: float = 0.0,
        error: str = "",
        **metadata: Any,
    ) -> None:
        """
        Record a secrets operation.

        Args:
            operation: Operation name.
            secret_key: Secret key involved.
            namespace: Namespace of the secret.
            success: Whether operation succeeded.
            duration_ms: Duration in milliseconds.
            error: Error message if failed.
            **metadata: Additional metadata.
        """
        with self._lock:
            record = SecretOperationRecord(
                operation=operation,
                secret_key=secret_key,
                namespace=namespace,
                success=success,
                duration_ms=duration_ms,
                timestamp=datetime.utcnow(),
                metadata=metadata,
            )

            self._operations.append(record)

            if len(self._operations) > self._max_history:
                self._operations = self._operations[-self._max_history:]

            if not success and error:
                self._errors.append(
                    SecretErrorRecord(
                        error_type=type(error).__name__ if error else "Unknown",
                        message=str(error),
                        operation=operation,
                        secret_key=secret_key,
                        timestamp=datetime.utcnow(),
                    )
                )
                if len(self._errors) > self._max_errors:
                    self._errors = self._errors[-self._max_errors:]

    def get_operations(
        self,
        operation: Optional[str] = None,
        secret_key: Optional[str] = None,
        namespace: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get operation history.

        Args:
            operation: Filter by operation type.
            secret_key: Filter by secret key.
            namespace: Filter by namespace.
            success: Filter by success status.
            limit: Maximum entries to return.

        Returns:
            List of operation record dictionaries.
        """
        with self._lock:
            results = list(reversed(self._operations))

            if operation:
                results = [
                    r for r in results if r.operation == operation
                ]
            if secret_key:
                results = [
                    r for r in results if r.secret_key == secret_key
                ]
            if namespace:
                results = [
                    r for r in results if r.namespace == namespace
                ]
            if success is not None:
                results = [
                    r for r in results if r.success == success
                ]

            return [r.to_dict() for r in results[:limit]]

    def get_errors(
        self,
        operation: Optional[str] = None,
        secret_key: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get error history.

        Args:
            operation: Filter by operation type.
            secret_key: Filter by secret key.
            limit: Maximum entries to return.

        Returns:
            List of error record dictionaries.
        """
        with self._lock:
            results = list(reversed(self._errors))

            if operation:
                results = [
                    r for r in results if r.operation == operation
                ]
            if secret_key:
                results = [
                    r for r in results if r.secret_key == secret_key
                ]

            return [r.to_dict() for r in results[:limit]]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get aggregated performance statistics.

        Returns:
            Performance statistics by operation type
            including count, avg, min, max, and p95 latencies.
        """
        with self._lock:
            by_operation: Dict[str, List[float]] = {}
            for op in self._operations:
                if op.duration_ms > 0:
                    by_operation.setdefault(op.operation, []).append(
                        op.duration_ms
                    )

        perf_stats: Dict[str, Any] = {}
        for op_name, durations in by_operation.items():
            sorted_durations = sorted(durations)
            count = len(durations)
            perf_stats[op_name] = {
                "count": count,
                "avg_ms": sum(durations) / count,
                "min_ms": sorted_durations[0],
                "max_ms": sorted_durations[-1],
                "p95_ms": sorted_durations[
                    int(count * 0.95)
                ] if count > 0 else 0,
            }

        return perf_stats

    def clear_history(self) -> None:
        """Clear all operation and error history."""
        with self._lock:
            self._operations.clear()
            self._errors.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get diagnostics statistics.

        Returns:
            Statistics dictionary with total operations,
            success/failure counts, error counts, and
            performance breakdown.
        """
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