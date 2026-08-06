"""Integration Metrics — Prometheus-compatible metrics for platform integrations.

Metrics collected:
* icyquant_workflow_platform_total — total platform operations
* icyquant_workflow_api_total — total API calls
* icyquant_workflow_sdk_total — total SDK operations
* icyquant_workflow_trigger_total — total scheduled triggers
* icyquant_workflow_eventbus_total — total EventBus events
* icyquant_workflow_strategy_total — total strategy signals processed
* icyquant_workflow_ai_total — total AI invocations
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class IntegrationCounter:
    name: str
    help: str
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def value(self) -> int:
        with self._lock:
            return self._value


@dataclass
class IntegrationGauge:
    name: str
    help: str
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def value(self) -> float:
        with self._lock:
            return self._value


class IntegrationMetrics:
    """Collector for platform integration metrics."""

    def __init__(self) -> None:
        self._platform_total = IntegrationCounter(name="icyquant_workflow_platform_total", help="Total platform operations")
        self._api_total = IntegrationCounter(name="icyquant_workflow_api_total", help="Total API calls")
        self._sdk_total = IntegrationCounter(name="icyquant_workflow_sdk_total", help="Total SDK operations")
        self._trigger_total = IntegrationCounter(name="icyquant_workflow_trigger_total", help="Total scheduled triggers")
        self._eventbus_total = IntegrationCounter(name="icyquant_workflow_eventbus_total", help="Total EventBus events")
        self._strategy_total = IntegrationCounter(name="icyquant_workflow_strategy_total", help="Total strategy signals")
        self._ai_total = IntegrationCounter(name="icyquant_workflow_ai_total", help="Total AI invocations")
        self._active_connections = IntegrationGauge(name="icyquant_workflow_platform_connections", help="Active platform connections")

    def increment_platform_total(self) -> None:
        self._platform_total.inc()

    def increment_api_total(self) -> None:
        self._api_total.inc()

    def increment_sdk_total(self) -> None:
        self._sdk_total.inc()

    def increment_trigger_total(self) -> None:
        self._trigger_total.inc()

    def increment_eventbus_total(self) -> None:
        self._eventbus_total.inc()

    def increment_strategy_total(self) -> None:
        self._strategy_total.inc()

    def increment_ai_total(self) -> None:
        self._ai_total.inc()

    def set_active_connections(self, count: float) -> None:
        self._active_connections.set(count)

    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "counters": {
                "icyquant_workflow_platform_total": self._platform_total.value(),
                "icyquant_workflow_api_total": self._api_total.value(),
                "icyquant_workflow_sdk_total": self._sdk_total.value(),
                "icyquant_workflow_trigger_total": self._trigger_total.value(),
                "icyquant_workflow_eventbus_total": self._eventbus_total.value(),
                "icyquant_workflow_strategy_total": self._strategy_total.value(),
                "icyquant_workflow_ai_total": self._ai_total.value(),
            },
            "gauges": {
                "icyquant_workflow_platform_connections": self._active_connections.value(),
            },
        }
