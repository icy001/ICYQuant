"""
Instrumentation metrics.

Tracks metrics about the instrumentation
framework itself, including:
- Active instrumentations
- Install/uninstall counts
- Per-instrumentation span counts
"""

from __future__ import annotations

from typing import Any, Dict

from .base import Instrumentation


class InstrumentationMetrics:
    """
    Instrumentation metrics collector.

    Tracks operational metrics about the
    instrumentation framework itself.

    Usage:
        metrics = InstrumentationMetrics()
        metrics.record_span("fastapi")
        stats = metrics.get_stats()
    """

    def __init__(self) -> None:
        self._span_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._install_count: int = 0
        self._uninstall_count: int = 0

    def record_span(self, instrumentation_name: str) -> None:
        self._span_counts[instrumentation_name] = (
            self._span_counts.get(instrumentation_name, 0) + 1
        )

    def record_error(self, instrumentation_name: str) -> None:
        self._error_counts[instrumentation_name] = (
            self._error_counts.get(instrumentation_name, 0) + 1
        )

    def record_install(self) -> None:
        self._install_count += 1

    def record_uninstall(self) -> None:
        self._uninstall_count += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "span_counts": dict(self._span_counts),
            "error_counts": dict(self._error_counts),
            "total_spans": sum(self._span_counts.values()),
            "total_errors": sum(self._error_counts.values()),
            "install_count": self._install_count,
            "uninstall_count": self._uninstall_count,
        }
