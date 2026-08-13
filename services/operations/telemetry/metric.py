"""Metric types and definitions (Commit 27 Part 1.2, spec sections 3-4).

三种核心 Metric：

    Counter    只增不减                  orders_submitted_total
    Gauge      表示当前状态              open_orders
    Histogram  描述分布                  risk_check_latency_ms

命名约定（spec section 21）：<domain>_<action>_<unit>
单位必须明确（spec section 22）：latency_ms / notional_usd / ratio
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MetricType(str, Enum):

    COUNTER = "counter"

    GAUGE = "gauge"

    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class MetricDefinition:

    name: str

    metric_type: MetricType

    description: str

    unit: str = ""

    labels: tuple[str, ...] = ()
