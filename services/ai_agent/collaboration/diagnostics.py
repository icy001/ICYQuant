"""Collaboration Diagnostics — performance analysis and health insights for multi-agent coordination.

Provides:
    - Latency analysis per agent (p50/p95/p99)
    - Error rate tracking per agent
    - Consensus failure and conflict rate analysis
    - Slow agent detection
    - Queue depth trends
    - Recovery rate tracking
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Diagnostic Records ──

@dataclass
class AgentLatencyStats:
    """Latency statistics for a single agent.

    Attributes:
        agent_id: Agent identifier.
        samples: Number of observations.
        p50_ms: 50th percentile latency (ms).
        p95_ms: 95th percentile latency (ms).
        p99_ms: 99th percentile latency (ms).
        avg_ms: Average latency (ms).
        min_ms: Minimum latency (ms).
        max_ms: Maximum latency (ms).
    """

    agent_id: str
    samples: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    avg_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0


@dataclass
class DiagnosticReport:
    """Aggregated diagnostic report for the collaboration system.

    Attributes:
        agent_stats: Per-agent latency statistics.
        error_rates: Per-agent error rate (0.0-1.0).
        slow_agents: Agents exceeding the slow threshold.
        conflict_rate: Overall conflict rate.
        consensus_success_rate: Overall consensus success rate.
        recovery_rate: Recovery attempts per hour.
        issues: Detected issues with severity.
    """

    agent_stats: List[AgentLatencyStats] = field(default_factory=list)
    error_rates: Dict[str, float] = field(default_factory=dict)
    slow_agents: List[str] = field(default_factory=list)
    conflict_rate: float = 0.0
    consensus_success_rate: float = 1.0
    recovery_rate: float = 0.0
    issues: List[Dict[str, Any]] = field(default_factory=list)


# ── Diagnostics Engine ──

class CollaborationDiagnostics:
    """Performance diagnostics for the multi-agent collaboration subsystem.

    Collects latency, error, consensus, and recovery data and generates
    diagnostic reports with issue detection.

    Usage:
        diag = CollaborationDiagnostics()
        diag.record_agent_latency("market_agent", 42.5)
        diag.record_agent_error("research_agent")
        diag.record_consensus_failure()
        report = diag.generate_report()
    """

    def __init__(
        self,
        slow_threshold_ms: float = 2000.0,
        error_rate_threshold: float = 0.1,
        max_samples_per_agent: int = 1000,
    ) -> None:
        """Initialize diagnostics.

        Args:
            slow_threshold_ms: Latency threshold for slow agent detection.
            error_rate_threshold: Error rate to flag.
            max_samples_per_agent: Max latency samples per agent.
        """
        self._slow_threshold_ms = slow_threshold_ms
        self._error_rate_threshold = error_rate_threshold
        self._max_samples = max_samples_per_agent

        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._errors: Dict[str, int] = defaultdict(int)
        self._total_calls: Dict[str, int] = defaultdict(int)
        self._consensus_success: int = 0
        self._consensus_failure: int = 0
        self._conflict_count: int = 0
        self._recovery_count: int = 0
        self._total_decisions: int = 0

        logger.info(
            "CollaborationDiagnostics initialized (slow_threshold=%dms, error_threshold=%.2f)",
            slow_threshold_ms, error_rate_threshold,
        )

    # ── Data Collection ──

    def record_agent_latency(self, agent_id: str, latency_ms: float) -> None:
        """Record a latency observation for an agent.

        Args:
            agent_id: Agent identifier.
            latency_ms: Observed latency in milliseconds.
        """
        self._latencies[agent_id].append(latency_ms)
        # Trim old samples
        if len(self._latencies[agent_id]) > self._max_samples:
            self._latencies[agent_id] = self._latencies[agent_id][-self._max_samples:]

    def record_agent_call(self, agent_id: str, success: bool = True) -> None:
        """Record a completed agent call.

        Args:
            agent_id: Agent identifier.
            success: Whether the call succeeded.
        """
        self._total_calls[agent_id] = self._total_calls.get(agent_id, 0) + 1
        if not success:
            self._errors[agent_id] = self._errors.get(agent_id, 0) + 1

    def record_agent_error(self, agent_id: str) -> None:
        """Shortcut to record an error for an agent.

        Args:
            agent_id: Agent identifier.
        """
        self._errors[agent_id] = self._errors.get(agent_id, 0) + 1

    def record_consensus_success(self) -> None:
        """Record a successful consensus decision."""
        self._consensus_success += 1
        self._total_decisions += 1

    def record_consensus_failure(self) -> None:
        """Record a failed consensus attempt."""
        self._consensus_failure += 1
        self._total_decisions += 1

    def record_conflict(self) -> None:
        """Record a detected agent conflict."""
        self._conflict_count += 1

    def record_recovery(self) -> None:
        """Record an agent recovery attempt."""
        self._recovery_count += 1

    # ── Analysis ──

    @staticmethod
    def _calc_percentiles(sorted_values: List[float]) -> Tuple[float, float, float]:
        """Calculate p50, p95, p99 from sorted values.

        Args:
            sorted_values: Ascending sorted list of values.

        Returns:
            (p50, p95, p99) tuple.
        """
        if not sorted_values:
            return (0.0, 0.0, 0.0)

        def _p(p: float) -> float:
            idx = int(p / 100.0 * (len(sorted_values) - 1))
            return sorted_values[min(idx, len(sorted_values) - 1)]

        return (_p(50), _p(95), _p(99))

    def compute_agent_stats(self) -> List[AgentLatencyStats]:
        """Compute latency statistics for each agent.

        Returns:
            List of AgentLatencyStats.
        """
        stats: List[AgentLatencyStats] = []

        for agent_id, values in self._latencies.items():
            if not values:
                continue

            sorted_vals = sorted(values)
            p50, p95, p99 = self._calc_percentiles(sorted_vals)

            stats.append(AgentLatencyStats(
                agent_id=agent_id,
                samples=len(values),
                p50_ms=round(p50, 2),
                p95_ms=round(p95, 2),
                p99_ms=round(p99, 2),
                avg_ms=round(sum(values) / len(values), 2),
                min_ms=round(min(values), 2),
                max_ms=round(max(values), 2),
            ))

        return stats

    def compute_error_rates(self) -> Dict[str, float]:
        """Compute error rate for each agent.

        Returns:
            Dict mapping agent_id to error rate (0.0-1.0).
        """
        rates: Dict[str, float] = {}
        all_agents = set(self._total_calls.keys()) | set(self._errors.keys())

        for agent_id in all_agents:
            errors = self._errors.get(agent_id, 0)
            total = self._total_calls.get(agent_id, 0)
            rates[agent_id] = errors / total if total > 0 else 0.0

        return rates

    def detect_slow_agents(self) -> List[str]:
        """Detect agents with p95 latency exceeding the slow threshold.

        Returns:
            List of slow agent IDs.
        """
        slow: List[str] = []
        for agent_id, values in self._latencies.items():
            if not values:
                continue
            sorted_vals = sorted(values)
            _, p95, _ = self._calc_percentiles(sorted_vals)
            if p95 > self._slow_threshold_ms:
                slow.append(agent_id)
        return slow

    def compute_conflict_rate(self) -> float:
        """Compute the conflict rate.

        Returns:
            Conflict rate (0.0-1.0). Returns 0 if no decisions recorded.
        """
        if self._total_decisions == 0:
            return 0.0
        return self._conflict_count / self._total_decisions

    def compute_consensus_success_rate(self) -> float:
        """Compute the consensus success rate.

        Returns:
            Success rate (0.0-1.0). Returns 1.0 if no decisions recorded.
        """
        total = self._consensus_success + self._consensus_failure
        if total == 0:
            return 1.0
        return self._consensus_success / total

    # ── Report Generation ──

    def generate_report(self) -> DiagnosticReport:
        """Generate a comprehensive diagnostic report.

        Returns:
            DiagnosticReport with full analysis.
        """
        agent_stats = self.compute_agent_stats()
        error_rates = self.compute_error_rates()
        slow_agents = self.detect_slow_agents()

        conflict_rate = self.compute_conflict_rate()
        consensus_rate = self.compute_consensus_success_rate()

        # Detect issues
        issues: List[Dict[str, Any]] = []

        for agent_id, rate in error_rates.items():
            if rate > self._error_rate_threshold:
                issues.append({
                    "severity": "WARNING",
                    "type": "high_error_rate",
                    "agent": agent_id,
                    "error_rate": round(rate, 3),
                    "detail": f"Error rate {rate:.1%} exceeds threshold {self._error_rate_threshold:.1%}",
                })

        for agent_id in slow_agents:
            issues.append({
                "severity": "WARNING",
                "type": "slow_agent",
                "agent": agent_id,
                "detail": f"Agent {agent_id} p95 latency exceeds {self._slow_threshold_ms}ms",
            })

        if consensus_rate < 0.8:
            issues.append({
                "severity": "ERROR",
                "type": "low_consensus_success",
                "consensus_success_rate": round(consensus_rate, 3),
                "detail": f"Consensus success rate {consensus_rate:.1%} below 80%",
            })

        return DiagnosticReport(
            agent_stats=agent_stats,
            error_rates=error_rates,
            slow_agents=slow_agents,
            conflict_rate=round(conflict_rate, 4),
            consensus_success_rate=round(consensus_rate, 4),
            recovery_rate=self._recovery_count,
            issues=issues,
        )

    # ── Query ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of current diagnostics state.

        Returns:
            Dict with key diagnostic metrics.
        """
        report = self.generate_report()
        return {
            "agents_tracked": len(self._latencies),
            "total_calls": sum(self._total_calls.values()),
            "total_errors": sum(self._errors.values()),
            "consensus_success_rate": report.consensus_success_rate,
            "conflict_rate": report.conflict_rate,
            "recovery_count": self._recovery_count,
            "slow_agents": report.slow_agents,
            "issue_count": len(report.issues),
        }

    # ── Reset ──

    def reset(self) -> None:
        """Reset all collected diagnostic data."""
        self._latencies.clear()
        self._errors.clear()
        self._total_calls.clear()
        self._consensus_success = 0
        self._consensus_failure = 0
        self._conflict_count = 0
        self._recovery_count = 0
        self._total_decisions = 0
        logger.info("CollaborationDiagnostics reset")
