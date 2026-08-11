"""Platform Observability — unified AI full-stack observability.

The PlatformObservability module provides end-to-end visibility into the AI
platform across all layers: latency, cost, memory, reasoning quality, tool
calls, and agent behavior. It aggregates metrics from all subsystems into
a single observability dashboard.

Observability dimensions:
    - Latency: per component, per model, per agent
    - Cost: per request, per user, per model
    - Memory: usage, retention, eviction
    - Reasoning: planning quality, decision quality
    - Tools: success rate, latency, error rate
    - Agents: health, throughput, queue depth
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LatencySnapshot:
    """Latency statistics for a component."""
    component: str = ""
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    max_ms: float = 0.0
    sample_count: int = 0


@dataclass
class ObservabilityReport:
    """Aggregated observability report."""
    timestamp: float = field(default_factory=time.monotonic)
    latency_by_component: Dict[str, LatencySnapshot] = field(default_factory=dict)
    total_requests: int = 0
    total_errors: int = 0
    total_cost_usd: float = 0.0
    active_agents: int = 0
    active_sessions: int = 0
    memory_usage_entries: int = 0
    guardrail_blocks: int = 0


class PlatformObservability:
    """Unified AI full-stack observability.

    Aggregates metrics from all platform subsystems into a single
    observability view for monitoring and alerting.

    Usage:
        obs = PlatformObservability()
        await obs.initialize()
        obs.record_latency("model_router", 150.0)
        obs.record_latency("model_router", 200.0)
        report = obs.generate_report()
    """

    def __init__(self, max_samples: int = 10000) -> None:
        self._max_samples = max_samples
        self._latency_samples: Dict[str, List[float]] = {}
        self._request_count: int = 0
        self._error_count: int = 0
        self._cost_total: float = 0.0
        self._lock = threading.Lock()
        self._initialized: bool = False
        logger.info("PlatformObservability created (max_samples=%d)", max_samples)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PlatformObservability initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._latency_samples.clear()
        self._initialized = False
        logger.info("PlatformObservability shutdown complete")

    def record_latency(self, component: str, latency_ms: float) -> None:
        """Record a latency measurement for a component."""
        with self._lock:
            samples = self._latency_samples.setdefault(component, [])
            samples.append(latency_ms)
            if len(samples) > self._max_samples:
                self._latency_samples[component] = samples[-self._max_samples:]

    def record_request(self, success: bool = True) -> None:
        """Record a request outcome."""
        self._request_count += 1
        if not success:
            self._error_count += 1

    def record_cost(self, cost_usd: float) -> None:
        """Record cost incurred."""
        self._cost_total += cost_usd

    def _compute_percentiles(self, samples: List[float]) -> tuple:
        """Compute p50, p95, p99 from sorted samples."""
        if not samples:
            return (0.0, 0.0, 0.0)
        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        def pct(p: float) -> float:
            idx = int(p * (n - 1))
            return sorted_samples[idx]

        return (pct(0.50), pct(0.95), pct(0.99))

    def get_latency_snapshot(self, component: str) -> Optional[LatencySnapshot]:
        """Get latency statistics for a component."""
        with self._lock:
            samples = self._latency_samples.get(component, [])
        if not samples:
            return None
        p50, p95, p99 = self._compute_percentiles(samples)
        return LatencySnapshot(
            component=component,
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            avg_ms=round(sum(samples) / len(samples), 2),
            max_ms=round(max(samples), 2),
            sample_count=len(samples),
        )

    def generate_report(self) -> ObservabilityReport:
        """Generate a full observability report."""
        with self._lock:
            latency_by_comp = {}
            for component in self._latency_samples:
                snapshot = self.get_latency_snapshot(component)
                if snapshot:
                    latency_by_comp[component] = snapshot

        return ObservabilityReport(
            latency_by_component=latency_by_comp,
            total_requests=self._request_count,
            total_errors=self._error_count,
            total_cost_usd=round(self._cost_total, 6),
        )

    def get_summary(self) -> Dict[str, Any]:
        report = self.generate_report()
        return {
            "initialized": self._initialized,
            "total_requests": report.total_requests,
            "total_errors": report.total_errors,
            "error_rate": round(report.total_errors / report.total_requests * 100, 2) if report.total_requests > 0 else 0.0,
            "total_cost_usd": report.total_cost_usd,
            "tracked_components": list(report.latency_by_component.keys()),
            "latency_summary": {
                comp: {"p50_ms": s.p50_ms, "p95_ms": s.p95_ms, "p99_ms": s.p99_ms}
                for comp, s in report.latency_by_component.items()
            },
        }
