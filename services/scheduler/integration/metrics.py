"""Integration Metrics — Prometheus-compatible metrics for platform integration.

Exports metrics for:
* Platform operation counts
* Workflow dispatch totals
* EventBus publish/receive counts
* Strategy and AI execution counts
* Dashboard API request counts
"""

from __future__ import annotations

import threading
from typing import Any, Dict


class _Counter:
    """Simple thread-safe counter."""

    def __init__(self) -> None:
        self._value: int = 0
        self._lock = threading.Lock()

    def inc(self, delta: int = 1) -> None:
        with self._lock:
            self._value += delta

    def get(self) -> int:
        with self._lock:
            return self._value


class _Gauge:
    """Simple thread-safe gauge."""

    def __init__(self, initial: float = 0.0) -> None:
        self._value = initial
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def get(self) -> float:
        with self._lock:
            return self._value


class IntegrationMetrics:
    """Prometheus-compatible metrics for platform integration.

    Exports:
    * icyquant_scheduler_platform_total — platform operations
    * icyquant_scheduler_workflow_total — workflow dispatch count
    * icyquant_scheduler_eventbus_total — event publish/receive
    * icyquant_scheduler_strategy_total — strategy execution count
    * icyquant_scheduler_ai_total — AI execution count
    * icyquant_scheduler_dashboard_requests — dashboard API requests
    """

    def __init__(self) -> None:
        # Counters
        self.platform_operations = _Counter()
        self.workflow_launched = _Counter()
        self.workflow_completed = _Counter()
        self.workflow_failed = _Counter()
        self.eventbus_published = _Counter()
        self.eventbus_received = _Counter()
        self.strategy_executions = _Counter()
        self.ai_executions = _Counter()
        self.research_executions = _Counter()
        self.dashboard_requests = _Counter()
        self.notifications_sent = _Counter()
        self.webhooks_sent = _Counter()
        self.errors_total = _Counter()

        # Gauges
        self.active_workflows = _Gauge()
        self.active_strategies = _Gauge()
        self.active_ai_jobs = _Gauge()
        self.eventbus_subscriptions = _Gauge()
        self.dashboard_request_latency = _Gauge()

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def record_workflow_launched(self) -> None:
        self.workflow_launched.inc()
        self.platform_operations.inc()

    def record_workflow_completed(self) -> None:
        self.workflow_completed.inc()
        self.active_workflows.set(max(0, self.active_workflows.get() - 1))

    def record_workflow_failed(self) -> None:
        self.workflow_failed.inc()
        self.errors_total.inc()

    def record_event_published(self) -> None:
        self.eventbus_published.inc()

    def record_event_received(self) -> None:
        self.eventbus_received.inc()

    def record_strategy_execution(self) -> None:
        self.strategy_executions.inc()

    def record_ai_execution(self) -> None:
        self.ai_executions.inc()

    def record_research_execution(self) -> None:
        self.research_executions.inc()

    def record_dashboard_request(self, latency_ms: float = 0) -> None:
        self.dashboard_requests.inc()
        self.dashboard_request_latency.set(latency_ms)

    def record_notification_sent(self) -> None:
        self.notifications_sent.inc()

    def record_webhook_sent(self) -> None:
        self.webhooks_sent.inc()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all metric values."""
        return {
            "counters": {
                "icyquant_scheduler_platform_total": self.platform_operations.get(),
                "icyquant_scheduler_workflow_launched_total": self.workflow_launched.get(),
                "icyquant_scheduler_workflow_completed_total": self.workflow_completed.get(),
                "icyquant_scheduler_workflow_failed_total": self.workflow_failed.get(),
                "icyquant_scheduler_eventbus_published_total": self.eventbus_published.get(),
                "icyquant_scheduler_eventbus_received_total": self.eventbus_received.get(),
                "icyquant_scheduler_strategy_total": self.strategy_executions.get(),
                "icyquant_scheduler_ai_total": self.ai_executions.get(),
                "icyquant_scheduler_research_total": self.research_executions.get(),
                "icyquant_scheduler_dashboard_requests": self.dashboard_requests.get(),
                "icyquant_scheduler_notifications_sent": self.notifications_sent.get(),
                "icyquant_scheduler_webhooks_sent": self.webhooks_sent.get(),
                "icyquant_scheduler_errors_total": self.errors_total.get(),
            },
            "gauges": {
                "icyquant_scheduler_active_workflows": self.active_workflows.get(),
                "icyquant_scheduler_active_strategies": self.active_strategies.get(),
                "icyquant_scheduler_active_ai_jobs": self.active_ai_jobs.get(),
                "icyquant_scheduler_eventbus_subscriptions": self.eventbus_subscriptions.get(),
                "icyquant_scheduler_dashboard_request_latency_ms": self.dashboard_request_latency.get(),
            },
        }
