"""Capacity Planner — long-term resource capacity forecasting.

The :class:`CapacityPlanner` analyzes historical usage trends and projects
future capacity needs, helping operators plan hardware procurement and
cloud resource expansion.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CapacityPlan:
    """A capacity forecast for a future time window."""

    forecast_at: datetime
    cpu_cores_needed: float
    memory_mb_needed: float
    gpu_units_needed: float
    nodes_needed: int
    current_cpu: float
    current_memory_mb: float
    current_nodes: int
    trend: str = "stable"
    confidence: float = 0.5
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_at": self.forecast_at.isoformat(),
            "cpu_cores_needed": self.cpu_cores_needed,
            "memory_mb_needed": self.memory_mb_needed,
            "gpu_units_needed": self.gpu_units_needed,
            "nodes_needed": self.nodes_needed,
            "current_cpu": self.current_cpu,
            "current_memory_mb": self.current_memory_mb,
            "current_nodes": self.current_nodes,
            "trend": self.trend, "confidence": self.confidence,
            "recommendations": self.recommendations,
        }


class CapacityPlanner:
    """Long-term capacity forecasting and planning.

    Usage::

        planner = CapacityPlanner()
        planner.record_usage(cpu=120, memory_mb=256000, nodes=10)
        plan = planner.forecast(days_ahead=30)
        print(plan.recommendations)
    """

    def __init__(self, max_history: int = 8760) -> None:
        """max_history: max data points (e.g., 8760 = 365 days at 1h intervals)."""
        self._lock = threading.RLock()
        self._max_history = max_history
        self._history: List[Tuple[datetime, float, float, int]] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_usage(
        self, cpu: float, memory_mb: float, nodes: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._history.append((now, cpu, memory_mb, nodes))
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------

    def forecast(self, days_ahead: int = 30, cpu_per_node: float = 16.0,
                 memory_per_node_mb: float = 32_768.0) -> CapacityPlan:
        """Forecast capacity needs *days_ahead* from now."""
        with self._lock:
            if len(self._history) < 24:
                return CapacityPlan(
                    forecast_at=datetime.now(timezone.utc) + timedelta(days=days_ahead),
                    cpu_cores_needed=0, memory_mb_needed=0, gpu_units_needed=0,
                    nodes_needed=0, current_cpu=0, current_memory_mb=0,
                    current_nodes=0, trend="unknown", confidence=0.1,
                    recommendations=["Not enough data for forecast"],
                )

            # Current
            _, cur_cpu, cur_mem, cur_nodes = self._history[-1]

            # Simple linear trend on the last 168 points (1 week at hourly)
            window = min(len(self._history), 168)
            recent = self._history[-window:]

            cpu_values = [r[1] for r in recent]
            mem_values = [r[2] for r in recent]

            # Trend: average change per day
            half = window // 2
            recent_half = cpu_values[-half:] if half > 0 else cpu_values
            older_half = cpu_values[:window - half] if half > 0 else cpu_values
            if older_half and recent_half:
                cpu_growth_per_day = (sum(recent_half) / len(recent_half) - sum(older_half) / len(older_half)) / (window / 24)
            else:
                cpu_growth_per_day = 0.0

            # Forecast
            forecast_cpu = cur_cpu + cpu_growth_per_day * days_ahead
            forecast_mem = cur_mem * (forecast_cpu / max(cur_cpu, 0.001))
            forecast_nodes = max(1, int(forecast_cpu / cpu_per_node) + 1)

            # Trend classification
            if cpu_growth_per_day > cur_cpu * 0.02:
                trend = "growing"
            elif cpu_growth_per_day < -cur_cpu * 0.02:
                trend = "shrinking"
            else:
                trend = "stable"

            confidence = min(1.0, len(self._history) / 720.0)

            # Recommendations
            recs: List[str] = []
            if forecast_nodes > cur_nodes:
                recs.append(f"Add {forecast_nodes - cur_nodes} nodes in the next {days_ahead} days")
            if trend == "growing":
                recs.append("Capacity is trending UP — review procurement plan")
            elif trend == "shrinking":
                recs.append("Capacity is trending DOWN — consider scaling in")

            return CapacityPlan(
                forecast_at=datetime.now(timezone.utc) + timedelta(days=days_ahead),
                cpu_cores_needed=forecast_cpu,
                memory_mb_needed=forecast_mem,
                gpu_units_needed=0,
                nodes_needed=forecast_nodes,
                current_cpu=cur_cpu,
                current_memory_mb=cur_mem,
                current_nodes=cur_nodes,
                trend=trend,
                confidence=confidence,
                recommendations=recs if recs else ["Capacity is stable"],
            )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "data_points": len(self._history),
                "days_of_history": len(self._history) / 24.0 if self._history else 0,
            }
