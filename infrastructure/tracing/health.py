"""
Tracing health check.

Provides health monitoring for the
tracing infrastructure, reporting on
active traces, exporter status, and
sampler configuration.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .config import TracingConfig
from .registry import TraceRegistry


class TracingHealth:
    """
    Tracing health checker.

    Usage:
        health = TracingHealth(config=config, registry=registry)
        status = await health.check()
    """

    def __init__(
        self,
        config: Optional[TracingConfig] = None,
        registry: Optional[TraceRegistry] = None,
    ) -> None:
        """Initialize health checker."""

        self._config = config or TracingConfig()
        self._registry = registry

    async def check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary.
        """

        active_traces = 0
        finished_traces = 0
        total_spans = 0

        if self._registry is not None:
            stats = self._registry.get_stats()
            active_traces = stats["active"]
            finished_traces = stats["finished"]
            total_spans = stats["spans"]

        return {
            "healthy": True,
            "enabled": self._config.enabled,
            "active_traces": active_traces,
            "finished_traces": finished_traces,
            "total_spans": total_spans,
            "exporter": self._config.exporter,
            "sample_ratio": self._config.sample_ratio,
            "service_name": self._config.service_name,
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get static status."""

        return {
            "enabled": self._config.enabled,
            "exporter": self._config.exporter,
            "service_name": self._config.service_name,
        }
