"""Tool metadata — extended runtime information for registered tools.

Data flow:
    ToolDefinition (static) + ToolMetadata (dynamic)
        -> ToolRegistry
        -> Discovery / Selection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── ToolMetadata ──

@dataclass
class ToolMetadata:
    """Runtime metadata attached to a tool definition.

    Tracks dynamic information such as usage stats, health status,
    and performance metrics that evolve during the tool's lifetime.

    Supports:
        - Usage tracking (call count, success/failure rate)
        - Health monitoring (last check, status)
        - Performance profiling (avg/p50/p95/p99 latency)
        - Dependency tracking
        - Capability indexing

    Usage:
        meta = ToolMetadata(tool_name="backtest.run")
        meta.record_call(success=True, latency_ms=125.3)
    """

    tool_name: str

    # ── Status ──
    is_enabled: bool = True
    health_status: str = "unknown"  # unknown | healthy | degraded | unhealthy
    last_health_check: Optional[datetime] = None

    # ── Usage Stats ──
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    permission_denied_count: int = 0
    last_called_at: Optional[datetime] = None

    # ── Performance ──
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")

    # ── Latency Samples (for percentile calculation) ──
    _latency_samples: List[float] = field(default_factory=list, repr=False)
    _max_samples: int = field(default=1000, repr=False)

    # ── Dependencies ──
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    # ── Extra ──
    labels: Dict[str, str] = field(default_factory=dict)
    custom_data: Dict[str, Any] = field(default_factory=dict)

    # ── Timestamps ──
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Properties ──

    @property
    def success_rate(self) -> float:
        """Call success rate (0.0 to 1.0)."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def failure_rate(self) -> float:
        """Call failure rate (0.0 to 1.0)."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    # ── Recording ──

    def record_call(
        self,
        success: bool,
        latency_ms: float = 0.0,
        permission_denied: bool = False,
    ) -> None:
        """Record a single tool call with its outcome.

        Args:
            success: Whether the call succeeded.
            latency_ms: Execution latency in milliseconds.
            permission_denied: Whether the call was denied by permission check.
        """
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        if permission_denied:
            self.permission_denied_count += 1

        # Track latency
        if latency_ms > 0:
            self.total_latency_ms += latency_ms
            self.avg_latency_ms = self.total_latency_ms / self.total_calls
            self.max_latency_ms = max(self.max_latency_ms, latency_ms)
            self.min_latency_ms = min(self.min_latency_ms, latency_ms)

            # Maintain sample buffer for percentiles
            self._latency_samples.append(latency_ms)
            if len(self._latency_samples) > self._max_samples:
                self._latency_samples = self._latency_samples[-self._max_samples :]

            # Recalculate percentiles
            sorted_samples = sorted(self._latency_samples)
            n = len(sorted_samples)
            if n > 0:
                self.p50_latency_ms = sorted_samples[int(n * 0.50)]
                self.p95_latency_ms = sorted_samples[int(n * 0.95)]
                self.p99_latency_ms = sorted_samples[int(n * 0.99)]

        self.last_called_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def record_health(self, status: str) -> None:
        """Update the health status of this tool.

        Args:
            status: One of unknown, healthy, degraded, unhealthy.
        """
        self.health_status = status
        self.last_health_check = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to dictionary."""
        return {
            "tool_name": self.tool_name,
            "is_enabled": self.is_enabled,
            "health_status": self.health_status,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "permission_denied_count": self.permission_denied_count,
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "labels": self.labels,
            "last_called_at": self.last_called_at.isoformat() if self.last_called_at else None,
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
        }
