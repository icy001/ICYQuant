"""
ICYQuant Cloud Native Runtime - Auto Scaler

Provides intelligent auto-scaling with support for:
- CPU-based scaling (HPA)
- Memory-based scaling
- GPU inference queue scaling
- Custom metric scaling
- KEDA event-driven scaling
- Cooldown and stabilization windows
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ScaleDirection(str, Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    NO_CHANGE = "NO_CHANGE"


class ScalingStrategy(str, Enum):
    HPA = "HPA"
    KEDA = "KEDA"
    CUSTOM = "CUSTOM"


@dataclass
class MetricSample:
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "metric": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class ScalingPolicy:
    name: str
    metric_name: str
    target_value: float
    min_replicas: int = 2
    max_replicas: int = 100
    scale_up_threshold: float = 1.2
    scale_down_threshold: float = 0.8
    cooldown_seconds: int = 300
    stabilization_window_seconds: int = 60
    strategy: ScalingStrategy = ScalingStrategy.HPA
    behavior: str = "simple"  # simple, aggressive, conservative

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "metric": self.metric_name,
            "target": self.target_value,
            "minReplicas": self.min_replicas,
            "maxReplicas": self.max_replicas,
            "cooldownSeconds": self.cooldown_seconds,
            "strategy": self.strategy.value,
            "behavior": self.behavior,
        }


@dataclass
class ScaleEvent:
    id: str
    policy_name: str
    direction: ScaleDirection
    current_replicas: int
    new_replicas: int
    reason: str
    metrics: List[MetricSample]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "policy": self.policy_name,
            "direction": self.direction.value,
            "currentReplicas": self.current_replicas,
            "newReplicas": self.new_replicas,
            "reason": self.reason,
            "metrics": [m.to_dict() for m in self.metrics],
            "timestamp": self.timestamp.isoformat(),
        }


class AutoScaler:
    """
    Auto-scaling manager for ICYQuant services.

    Implements multiple scaling strategies:
    - Horizontal Pod Autoscaler (CPU, memory based)
    - KEDA (event-driven scaling based on queue depth)
    - Custom scaling (business metrics)
    """

    def __init__(self):
        self._policies: Dict[str, ScalingPolicy] = {}
        self._current_replicas: Dict[str, int] = {}
        self._cooldown_until: Dict[str, datetime] = {}
        self._metrics_history: Dict[str, List[MetricSample]] = {}
        self._scale_events: List[ScaleEvent] = []
        self._max_events = 1000
        self._custom_scalers: Dict[str, Callable] = {}

    def register_policy(
        self,
        policy: ScalingPolicy,
        current_replicas: int = 2,
    ):
        self._policies[policy.name] = policy
        self._current_replicas[policy.name] = current_replicas

    def remove_policy(self, policy_name: str):
        self._policies.pop(policy_name, None)
        self._current_replicas.pop(policy_name, None)
        self._cooldown_until.pop(policy_name, None)

    def set_replicas(self, policy_name: str, replicas: int):
        self._current_replicas[policy_name] = replicas

    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ):
        sample = MetricSample(
            metric_name=metric_name,
            value=value,
            labels=labels or {},
        )
        if metric_name not in self._metrics_history:
            self._metrics_history[metric_name] = []
        self._metrics_history[metric_name].append(sample)

        if len(self._metrics_history[metric_name]) > 1000:
            self._metrics_history[metric_name] = self._metrics_history[metric_name][-1000:]

    def evaluate_policy(
        self,
        policy_name: str,
    ) -> ScaleEvent:
        policy = self._policies.get(policy_name)
        if not policy:
            return ScaleEvent(
                id=str(uuid.uuid4())[:12],
                policy_name=policy_name,
                direction=ScaleDirection.NO_CHANGE,
                current_replicas=0,
                new_replicas=0,
                reason="Policy not found",
                metrics=[],
            )

        current = self._current_replicas.get(policy_name, policy.min_replicas)

        if self._is_in_cooldown(policy_name):
            return ScaleEvent(
                id=str(uuid.uuid4())[:12],
                policy_name=policy_name,
                direction=ScaleDirection.NO_CHANGE,
                current_replicas=current,
                new_replicas=current,
                reason="In cooldown period",
                metrics=[],
            )

        metrics = self._get_latest_metrics(policy.metric_name)
        if not metrics:
            return ScaleEvent(
                id=str(uuid.uuid4())[:12],
                policy_name=policy_name,
                direction=ScaleDirection.NO_CHANGE,
                current_replicas=current,
                new_replicas=current,
                reason="No metrics available",
                metrics=[],
            )

        direction, new_replicas, reason = self._calculate_scaling(policy, metrics, current)

        if direction == ScaleDirection.NO_CHANGE:
            return ScaleEvent(
                id=str(uuid.uuid4())[:12],
                policy_name=policy_name,
                direction=direction,
                current_replicas=current,
                new_replicas=current,
                reason=reason,
                metrics=metrics,
            )

        self._current_replicas[policy_name] = new_replicas
        self._start_cooldown(policy_name, policy.cooldown_seconds)

        event = ScaleEvent(
            id=str(uuid.uuid4())[:12],
            policy_name=policy_name,
            direction=direction,
            current_replicas=current,
            new_replicas=new_replicas,
            reason=reason,
            metrics=metrics,
        )
        self._scale_events.append(event)
        if len(self._scale_events) > self._max_events:
            self._scale_events = self._scale_events[-self._max_events:]

        return event

    def evaluate_all(self) -> List[ScaleEvent]:
        events = []
        for policy_name in self._policies:
            event = self.evaluate_policy(policy_name)
            events.append(event)
        return events

    def register_custom_scaler(
        self,
        metric_name: str,
        scaler_fn: Callable[[List[MetricSample]], Optional[float]],
    ):
        self._custom_scalers[metric_name] = scaler_fn

    def get_status(self) -> Dict:
        return {
            "policies": {
                name: {
                    "config": p.to_dict(),
                    "currentReplicas": self._current_replicas.get(name, 0),
                    "inCooldown": self._is_in_cooldown(name),
                }
                for name, p in self._policies.items()
            },
            "recentEvents": [e.to_dict() for e in self._scale_events[-10:]],
            "totalEvents": len(self._scale_events),
        }

    def _calculate_scaling(
        self,
        policy: ScalingPolicy,
        metrics: List[MetricSample],
        current: int,
    ) -> tuple:
        avg_value = sum(m.value for m in metrics) / len(metrics)

        if avg_value > policy.target_value * policy.scale_up_threshold:
            new_replicas = min(
                current + max(1, int(current * (avg_value / policy.target_value - 1))),
                policy.max_replicas,
            )
            return (
                ScaleDirection.SCALE_UP,
                new_replicas,
                f"Metric {policy.metric_name} at {avg_value:.1f} > target {policy.target_value:.1f}",
            )

        if avg_value < policy.target_value * policy.scale_down_threshold:
            new_replicas = max(
                policy.min_replicas,
                current - max(1, int(current * (1 - avg_value / policy.target_value))),
            )
            return (
                ScaleDirection.SCALE_DOWN,
                new_replicas,
                f"Metric {policy.metric_name} at {avg_value:.1f} < target {policy.target_value:.1f}",
            )

        return (ScaleDirection.NO_CHANGE, current, f"Metric {policy.metric_name} stable at {avg_value:.1f}")

    def _get_latest_metrics(self, metric_name: str, count: int = 10) -> List[MetricSample]:
        history = self._metrics_history.get(metric_name, [])
        return history[-count:] if history else []

    def _is_in_cooldown(self, policy_name: str) -> bool:
        cooldown_end = self._cooldown_until.get(policy_name)
        if cooldown_end and datetime.now() < cooldown_end:
            return True
        return False

    def _start_cooldown(self, policy_name: str, seconds: int):
        self._cooldown_until[policy_name] = datetime.now() + timedelta(seconds=seconds)