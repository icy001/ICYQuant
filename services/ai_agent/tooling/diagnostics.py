"""Tool Diagnostics — performance profiling and error tracking for the tooling subsystem.

Tracks:
    - Execution latency distributions
    - Error rate by tool and error type
    - Slow tool detection
    - Memory usage estimates
    - Call depth violations
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── DiagnosticsSnapshot ──

@dataclass
class DiagnosticsSnapshot:
    """A single diagnostics snapshot."""

    tool_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = 0.0
    success: bool = True
    error_type: str = ""
    error_message: str = ""
    from_cache: bool = False
    retry_count: int = 0
    permission_denied: bool = False


# ── ErrorSummary ──

@dataclass
class ErrorSummary:
    """Aggregated error statistics for a tool."""

    tool_name: str
    total_errors: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None

    def record_error(self, error_type: str, error_message: str) -> None:
        """Record an error occurrence."""
        self.total_errors += 1
        self.by_type[error_type] = self.by_type.get(error_type, 0) + 1
        self.last_error = error_message
        self.last_error_at = datetime.now(timezone.utc)


# ── ToolDiagnostics ──

class ToolDiagnostics:
    """Performance profiling and error tracking for the tooling subsystem.

    Collects execution snapshots and computes latency percentiles,
    error rates, slow-tool detection, and other diagnostic information.

    Supports:
        - Per-tool latency tracking (p50/p95/p99)
        - Error rate and error-type distribution
        - Slow tool detection
        - Cache hit/miss tracking
        - Permission denial tracking

    Usage:
        diag = ToolDiagnostics(max_snapshots=10000)
        diag.record_execution(tool_name, latency_ms, success=True)
        slow_tools = diag.get_slow_tools(threshold_ms=5000)
    """

    def __init__(self, max_snapshots: int = 10000) -> None:
        """Initialize diagnostics.

        Args:
            max_snapshots: Maximum number of snapshots to retain.
        """
        self._max_snapshots = max_snapshots
        self._snapshots: List[DiagnosticsSnapshot] = []
        self._errors: Dict[str, ErrorSummary] = {}
        self._permission_denials: Dict[str, int] = {}
        self._cache_stats: Dict[str, Dict[str, int]] = {}  # tool_name -> {hits, misses}

        self._initialized: bool = False
        logger.info(f"ToolDiagnostics created (max_snapshots={max_snapshots})")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize diagnostics."""
        self._initialized = True
        logger.info("ToolDiagnostics initialized")

    async def shutdown(self) -> None:
        """Shutdown diagnostics."""
        self._snapshots.clear()
        self._errors.clear()
        self._permission_denials.clear()
        self._cache_stats.clear()
        self._initialized = False
        logger.info("ToolDiagnostics shutdown complete")

    # ── Recording ──

    def record_execution(
        self,
        tool_name: str,
        latency_ms: float,
        success: bool = True,
        error_type: str = "",
        error_message: str = "",
        from_cache: bool = False,
        retry_count: int = 0,
        permission_denied: bool = False,
    ) -> None:
        """Record a tool execution snapshot.

        Args:
            tool_name: The tool name.
            latency_ms: Execution latency in milliseconds.
            success: Whether execution succeeded.
            error_type: Error classification if failed.
            error_message: Error message if failed.
            from_cache: Whether result came from cache.
            retry_count: Number of retries performed.
            permission_denied: Whether permission was denied.
        """
        snapshot = DiagnosticsSnapshot(
            tool_name=tool_name,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
            error_message=error_message,
            from_cache=from_cache,
            retry_count=retry_count,
            permission_denied=permission_denied,
        )
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        # Track errors
        if not success:
            if tool_name not in self._errors:
                self._errors[tool_name] = ErrorSummary(tool_name=tool_name)
            self._errors[tool_name].record_error(error_type or "unknown", error_message)

        # Track permission denials
        if permission_denied:
            self._permission_denials[tool_name] = self._permission_denials.get(tool_name, 0) + 1

        # Track cache
        if tool_name not in self._cache_stats:
            self._cache_stats[tool_name] = {"hits": 0, "misses": 0}
        if from_cache:
            self._cache_stats[tool_name]["hits"] += 1
        else:
            self._cache_stats[tool_name]["misses"] += 1

    # ── Analysis ──

    def get_latency_stats(self, tool_name: str) -> Dict[str, float]:
        """Get latency statistics for a tool.

        Args:
            tool_name: The tool name.

        Returns:
            Dict with avg, p50, p95, p99, min, max latency in ms.
        """
        latencies = [s.latency_ms for s in self._snapshots if s.tool_name == tool_name]
        if not latencies:
            return {"avg": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}

        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        return {
            "avg": round(sum(latencies) / n, 2),
            "p50": round(sorted_lat[int(n * 0.50)], 2),
            "p95": round(sorted_lat[int(n * 0.95)], 2),
            "p99": round(sorted_lat[int(n * 0.99)], 2),
            "min": round(sorted_lat[0], 2),
            "max": round(sorted_lat[-1], 2),
            "count": n,
        }

    def get_error_rate(self, tool_name: str) -> Dict[str, Any]:
        """Get error rate for a tool.

        Args:
            tool_name: The tool name.

        Returns:
            Dict with error rate and breakdown.
        """
        total = len([s for s in self._snapshots if s.tool_name == tool_name])
        errors = len([s for s in self._snapshots if s.tool_name == tool_name and not s.success])
        error_rate = errors / total if total > 0 else 0.0

        return {
            "total_calls": total,
            "errors": errors,
            "error_rate": round(error_rate, 4),
            "by_type": (
                self._errors[tool_name].by_type if tool_name in self._errors else {}
            ),
        }

    def get_slow_tools(self, threshold_ms: float = 5000.0) -> List[Dict[str, Any]]:
        """Get tools with executions exceeding a latency threshold.

        Args:
            threshold_ms: Latency threshold in milliseconds.

        Returns:
            List of slow tool summaries.
        """
        tool_latencies: Dict[str, List[float]] = {}
        for s in self._snapshots:
            if s.tool_name not in tool_latencies:
                tool_latencies[s.tool_name] = []
            tool_latencies[s.tool_name].append(s.latency_ms)

        slow_tools = []
        for tool_name, latencies in tool_latencies.items():
            avg = sum(latencies) / len(latencies)
            if avg > threshold_ms:
                slow_tools.append({
                    "tool": tool_name,
                    "avg_latency_ms": round(avg, 2),
                    "max_latency_ms": round(max(latencies), 2),
                    "call_count": len(latencies),
                })

        slow_tools.sort(key=lambda t: -t["avg_latency_ms"])
        return slow_tools

    def get_cache_hit_ratio(self, tool_name: str) -> float:
        """Get cache hit ratio for a tool.

        Args:
            tool_name: The tool name.

        Returns:
            Cache hit ratio (0.0 to 1.0).
        """
        stats = self._cache_stats.get(tool_name, {"hits": 0, "misses": 0})
        total = stats["hits"] + stats["misses"]
        if total == 0:
            return 0.0
        return stats["hits"] / total

    # ── Reports ──

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive diagnostics report."""
        unique_tools = set(s.tool_name for s in self._snapshots)

        tool_reports = {}
        for tool_name in sorted(unique_tools):
            tool_reports[tool_name] = {
                "latency": self.get_latency_stats(tool_name),
                "errors": self.get_error_rate(tool_name),
                "cache_hit_ratio": round(self.get_cache_hit_ratio(tool_name), 4),
                "permission_denials": self._permission_denials.get(tool_name, 0),
            }

        return {
            "total_snapshots": len(self._snapshots),
            "unique_tools": len(unique_tools),
            "tools": tool_reports,
            "slow_tools": self.get_slow_tools(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get diagnostics summary."""
        return {
            "snapshots": len(self._snapshots),
            "unique_tools": len(set(s.tool_name for s in self._snapshots)),
            "tools_with_errors": len(self._errors),
            "total_errors": sum(e.total_errors for e in self._errors.values()),
            "permission_denials": sum(self._permission_denials.values()),
            "initialized": self._initialized,
        }
