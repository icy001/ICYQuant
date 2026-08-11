"""
Prometheus-style metrics for the AI Agent Platform.

Tracks:
    - Agent request throughput and latency
    - Session counts and durations
    - Plan creation and execution
    - Reasoning operations
    - Memory hits and misses
    - Runtime performance
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Metric Types ──


@dataclass
class Counter:
    """Monotonically increasing counter."""

    name: str
    help_text: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    _value: int = 0

    def inc(self, amount: int = 1) -> None:
        """Increment counter."""
        self._value += amount

    @property
    def value(self) -> int:
        """Current counter value."""
        return self._value


@dataclass
class Gauge:
    """Up-down gauge value."""

    name: str
    help_text: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    _value: float = 0.0

    def set(self, value: float) -> None:
        """Set gauge value."""
        self._value = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge."""
        self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge."""
        self._value -= amount

    @property
    def value(self) -> float:
        """Current gauge value."""
        return self._value


@dataclass
class Histogram:
    """Histogram for distributions."""

    name: str
    help_text: str = ""
    buckets: List[float] = field(default_factory=lambda: [0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0])
    labels: Dict[str, str] = field(default_factory=dict)
    _observations: List[float] = field(default_factory=list)

    def observe(self, value: float) -> None:
        """Record an observation."""
        self._observations.append(value)

    @property
    def count(self) -> int:
        """Total observations."""
        return len(self._observations)

    @property
    def sum(self) -> float:
        """Sum of observations."""
        return sum(self._observations)

    @property
    def avg(self) -> float:
        """Average of observations."""
        if not self._observations:
            return 0.0
        return self.sum / self.count


# ── Agent Metrics ──


class AgentMetrics:
    """Metrics collection for the AI Agent Platform.

    Exposes counters, gauges, and histograms for monitoring
    and observability.

    Metrics:
        icyquant_agent_requests_total
        icyquant_agent_sessions_total
        icyquant_agent_plans_total
        icyquant_agent_reasoning_total
        icyquant_agent_memory_hits
        icyquant_agent_runtime_seconds
    """

    def __init__(self) -> None:
        # ── Counters ──
        self.agent_requests_total = Counter(
            name="icyquant_agent_requests_total",
            help_text="Total number of agent requests processed",
        )
        self.agent_sessions_total = Counter(
            name="icyquant_agent_sessions_total",
            help_text="Total number of agent sessions created",
        )
        self.agent_plans_total = Counter(
            name="icyquant_agent_plans_total",
            help_text="Total number of plans created",
        )
        self.agent_reasoning_total = Counter(
            name="icyquant_agent_reasoning_total",
            help_text="Total number of reasoning operations",
        )
        self.agent_memory_hits = Counter(
            name="icyquant_agent_memory_hits",
            help_text="Total memory cache hits",
        )

        # ── Gauges ──
        self.active_sessions = Gauge(
            name="icyquant_agent_active_sessions",
            help_text="Number of currently active sessions",
        )
        self.active_tasks = Gauge(
            name="icyquant_agent_active_tasks",
            help_text="Number of currently active tasks",
        )

        # ── Histograms ──
        self.agent_runtime_seconds = Histogram(
            name="icyquant_agent_runtime_seconds",
            help_text="Agent execution duration in seconds",
        )
        self.planning_duration_seconds = Histogram(
            name="icyquant_agent_planning_duration_seconds",
            help_text="Planning phase duration in seconds",
        )
        self.reasoning_duration_seconds = Histogram(
            name="icyquant_agent_reasoning_duration_seconds",
            help_text="Reasoning phase duration in seconds",
        )

        # ── Error metrics ──
        self.errors_by_type: Dict[str, int] = defaultdict(int)

        logger.info("AgentMetrics initialized")

    # ── Tracking Methods ──

    def track_request(self, duration_seconds: float, success: bool = True) -> None:
        """Track a completed agent request.

        Args:
            duration_seconds: Execution duration.
            success: Whether the request succeeded.
        """
        self.agent_requests_total.inc()
        self.agent_runtime_seconds.observe(duration_seconds)
        if not success:
            self.errors_by_type["request_failure"] += 1

    def track_session_created(self) -> None:
        """Track a new session creation."""
        self.agent_sessions_total.inc()
        self.active_sessions.inc()

    def track_session_closed(self) -> None:
        """Track session closure."""
        self.active_sessions.dec()

    def track_plan_created(self) -> None:
        """Track plan creation."""
        self.agent_plans_total.inc()

    def track_reasoning(self, duration_seconds: float) -> None:
        """Track a reasoning operation.

        Args:
            duration_seconds: Reasoning duration.
        """
        self.agent_reasoning_total.inc()
        self.reasoning_duration_seconds.observe(duration_seconds)

    def track_memory_hit(self) -> None:
        """Track a memory cache hit."""
        self.agent_memory_hits.inc()

    def track_error(self, error_type: str) -> None:
        """Track an error occurrence.

        Args:
            error_type: Classification of the error.
        """
        self.errors_by_type[error_type] += 1

    # ── Export ──

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics in a dictionary format."""
        return {
            # Counters
            "icyquant_agent_requests_total": self.agent_requests_total.value,
            "icyquant_agent_sessions_total": self.agent_sessions_total.value,
            "icyquant_agent_plans_total": self.agent_plans_total.value,
            "icyquant_agent_reasoning_total": self.agent_reasoning_total.value,
            "icyquant_agent_memory_hits": self.agent_memory_hits.value,
            # Gauges
            "icyquant_agent_active_sessions": self.active_sessions.value,
            "icyquant_agent_active_tasks": self.active_tasks.value,
            # Histograms
            "icyquant_agent_runtime_seconds_avg": self.agent_runtime_seconds.avg,
            "icyquant_agent_runtime_seconds_count": self.agent_runtime_seconds.count,
            "icyquant_agent_planning_duration_seconds_avg": self.planning_duration_seconds.avg,
            "icyquant_agent_reasoning_duration_seconds_avg": self.reasoning_duration_seconds.avg,
            # Errors
            "icyquant_agent_errors_by_type": dict(self.errors_by_type),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "total_requests": self.agent_requests_total.value,
            "active_sessions": self.active_sessions.value,
            "total_plans": self.agent_plans_total.value,
            "avg_runtime_seconds": self.agent_runtime_seconds.avg,
            "error_count": sum(self.errors_by_type.values()),
        }
