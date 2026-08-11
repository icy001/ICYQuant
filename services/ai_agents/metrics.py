"""
ICYQuant Agent Metrics — Prometheus metrics for multi-agent monitoring.

Exposes metrics for agent lifecycle, task execution, communication,
debate outcomes, and guardrail enforcement. All metrics follow
the Prometheus naming conventions with `icy_agents_` prefix.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """A single metric data point."""
    name: str
    type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    help_text: str = ""


class AgentMetrics:
    """Prometheus-compatible metrics for the multi-agent system.

    Metrics categories:
        - Agent lifecycle: spawns, stops, restarts, errors
        - Task execution: dispatched, completed, failed, duration
        - Communication: messages sent, delivered, dropped, latency
        - Deliberation: debates, votes, consensus rounds
        - Guardrails: evaluations, blocks, warnings
        - Workflow: executions, completions, failures, duration
    """

    def __init__(self) -> None:
        # Counters
        self.agent_spawns: dict[str, int] = {}
        self.agent_stops: dict[str, int] = {}
        self.agent_errors: dict[str, int] = {}

        self.tasks_dispatched: dict[str, int] = {}
        self.tasks_completed: dict[str, int] = {}
        self.tasks_failed: dict[str, int] = {}

        self.messages_sent: dict[str, int] = {}
        self.messages_delivered: dict[str, int] = {}
        self.messages_dropped: dict[str, int] = {}

        self.debates_total: int = 0
        self.consensus_rounds: int = 0

        self.guardrail_evaluations: int = 0
        self.guardrail_blocks: int = 0
        self.policy_evaluations: int = 0
        self.policy_denials: int = 0

        self.workflows_started: int = 0
        self.workflows_completed: int = 0
        self.workflows_failed: int = 0

        # Gauges
        self.active_agents: int = 0
        self.active_tasks: int = 0
        self.queue_depth: int = 0

        # Histogram data (min, max, sum, count, buckets)
        self.task_duration_ms: list[float] = []
        self.message_latency_ms: list[float] = []
        self.workflow_duration_seconds: list[float] = []

        # Agent-specific counters
        self.agent_task_counts: dict[str, int] = {}
        self.agent_error_counts: dict[str, int] = {}

    # ── Increment helpers ──

    def inc_agent_spawn(self, agent_type: str) -> None:
        self.agent_spawns[agent_type] = self.agent_spawns.get(agent_type, 0) + 1
        self.active_agents += 1

    def inc_agent_stop(self, agent_type: str) -> None:
        self.agent_stops[agent_type] = self.agent_stops.get(agent_type, 0) + 1
        self.active_agents = max(0, self.active_agents - 1)

    def inc_agent_error(self, agent_type: str) -> None:
        self.agent_errors[agent_type] = self.agent_errors.get(agent_type, 0) + 1

    def inc_task_dispatched(self, capability: str) -> None:
        self.tasks_dispatched[capability] = self.tasks_dispatched.get(capability, 0) + 1
        self.active_tasks += 1

    def inc_task_completed(self, capability: str, duration_ms: float) -> None:
        self.tasks_completed[capability] = self.tasks_completed.get(capability, 0) + 1
        self.active_tasks = max(0, self.active_tasks - 1)
        self.task_duration_ms.append(duration_ms)

    def inc_task_failed(self, capability: str) -> None:
        self.tasks_failed[capability] = self.tasks_failed.get(capability, 0) + 1
        self.active_tasks = max(0, self.active_tasks - 1)

    def inc_message_sent(self, msg_type: str) -> None:
        self.messages_sent[msg_type] = self.messages_sent.get(msg_type, 0) + 1

    def inc_message_delivered(self, msg_type: str, latency_ms: float) -> None:
        self.messages_delivered[msg_type] = self.messages_delivered.get(msg_type, 0) + 1
        self.message_latency_ms.append(latency_ms)

    def inc_message_dropped(self, msg_type: str) -> None:
        self.messages_dropped[msg_type] = self.messages_dropped.get(msg_type, 0) + 1

    def inc_debate(self) -> None:
        self.debates_total += 1

    def inc_consensus(self) -> None:
        self.consensus_rounds += 1

    def inc_guardrail_block(self) -> None:
        self.guardrail_evaluations += 1
        self.guardrail_blocks += 1

    def inc_policy_denial(self) -> None:
        self.policy_evaluations += 1
        self.policy_denials += 1

    def inc_workflow_start(self) -> None:
        self.workflows_started += 1

    def inc_workflow_complete(self, duration_s: float) -> None:
        self.workflows_completed += 1
        self.workflow_duration_seconds.append(duration_s)

    def inc_workflow_fail(self) -> None:
        self.workflows_failed += 1

    def set_queue_depth(self, depth: int) -> None:
        self.queue_depth = depth

    def record_task_for_agent(self, agent_id: str) -> None:
        self.agent_task_counts[agent_id] = self.agent_task_counts.get(agent_id, 0) + 1

    def record_error_for_agent(self, agent_id: str) -> None:
        self.agent_error_counts[agent_id] = self.agent_error_counts.get(agent_id, 0) + 1

    # ── Snapshot / Export ──

    def snapshot(self) -> dict[str, Any]:
        """Return a full metrics snapshot."""
        return {
            "counters": {
                "agent_spawns": dict(self.agent_spawns),
                "agent_stops": dict(self.agent_stops),
                "agent_errors": dict(self.agent_errors),
                "tasks_dispatched": dict(self.tasks_dispatched),
                "tasks_completed": dict(self.tasks_completed),
                "tasks_failed": dict(self.tasks_failed),
                "messages_sent": dict(self.messages_sent),
                "messages_delivered": dict(self.messages_delivered),
                "messages_dropped": dict(self.messages_dropped),
                "debates_total": self.debates_total,
                "consensus_rounds": self.consensus_rounds,
                "guardrail_evaluations": self.guardrail_evaluations,
                "guardrail_blocks": self.guardrail_blocks,
                "policy_evaluations": self.policy_evaluations,
                "policy_denials": self.policy_denials,
                "workflows_started": self.workflows_started,
                "workflows_completed": self.workflows_completed,
                "workflows_failed": self.workflows_failed,
            },
            "gauges": {
                "active_agents": self.active_agents,
                "active_tasks": self.active_tasks,
                "queue_depth": self.queue_depth,
            },
            "histograms": {
                "task_duration_ms": self._histogram_stats(self.task_duration_ms),
                "message_latency_ms": self._histogram_stats(self.message_latency_ms),
                "workflow_duration_seconds": self._histogram_stats(self.workflow_duration_seconds),
            },
            "per_agent": {
                "task_counts": dict(self.agent_task_counts),
                "error_counts": dict(self.agent_error_counts),
            },
        }

    def _histogram_stats(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }

    def get_agent_load(self, agent_id: str) -> int:
        return self.agent_task_counts.get(agent_id, 0)

    def get_error_rate(self) -> float:
        total = sum(self.tasks_dispatched.values())
        failed = sum(self.tasks_failed.values())
        return failed / total if total > 0 else 0.0

    def get_success_rate(self) -> float:
        return 1.0 - self.get_error_rate()
