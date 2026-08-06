"""Adaptive policy engine for ICYQuant Service Mesh.

Provides ``AdaptivePolicyEngine`` for automatically adjusting
runtime policies based on latency, failure rate, traffic, CPU,
and memory signals to achieve closed-loop governance.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .policy_repository import RuntimePolicy, RuntimePolicyRepository

logger = logging.getLogger(__name__)


class AdjustmentSignal(str):
    """Signals that trigger adaptive adjustments."""

    LATENCY = "latency"
    FAILURE_RATE = "failure_rate"
    TRAFFIC = "traffic"
    CPU = "cpu"
    MEMORY = "memory"


class AdjustmentAction(str):
    """Actions the adaptive engine can take."""

    INCREASE_RETRY = "increase_retry"
    DECREASE_RETRY = "decrease_retry"
    INCREASE_TIMEOUT = "increase_timeout"
    DECREASE_TIMEOUT = "decrease_timeout"
    ENABLE_CIRCUIT = "enable_circuit"
    DISABLE_CIRCUIT = "disable_circuit"
    INCREASE_RATE_LIMIT = "increase_rate_limit"
    DECREASE_RATE_LIMIT = "decrease_rate_limit"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


class AdaptiveRule:
    """A rule that defines adaptive behavior."""

    def __init__(
        self,
        rule_id: str,
        signal: str,
        threshold: float,
        comparison: str = ">",
        action: str = "",
        target_policy: str = "",
        adjustment: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> None:
        self.rule_id = rule_id
        self.signal = signal
        self.threshold = threshold
        self.comparison = comparison
        self.action = action
        self.target_policy = target_policy
        self.adjustment = adjustment or {}
        self.enabled = enabled

    def matches(self, value: float) -> bool:
        if self.comparison == ">":
            return value > self.threshold
        elif self.comparison == ">=":
            return value >= self.threshold
        elif self.comparison == "<":
            return value < self.threshold
        elif self.comparison == "<=":
            return value <= self.threshold
        elif self.comparison == "==":
            return abs(value - self.threshold) < 0.001
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "signal": self.signal,
            "threshold": self.threshold,
            "comparison": self.comparison,
            "action": self.action,
            "target_policy": self.target_policy,
            "adjustment": dict(self.adjustment),
            "enabled": self.enabled,
        }


class AdjustmentRecord:
    """Record of an adaptive adjustment."""

    def __init__(
        self,
        rule_id: str,
        signal: str,
        action: str,
        target_policy: str,
        old_value: Any,
        new_value: Any,
        reason: str,
    ) -> None:
        self.rule_id = rule_id
        self.signal = signal
        self.action = action
        self.target_policy = target_policy
        self.old_value = old_value
        self.new_value = new_value
        self.reason = reason
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "signal": self.signal,
            "action": self.action,
            "target_policy": self.target_policy,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class AdaptivePolicyEngine:
    """Automatically adjusts runtime policies based on signals."""

    def __init__(
        self,
        repository: Optional[RuntimePolicyRepository] = None,
        max_history: int = 1000,
    ) -> None:
        self._repository = repository or RuntimePolicyRepository()
        self._max_history = max_history
        self._lock = threading.RLock()
        self._rules: Dict[str, AdaptiveRule] = {}
        self._signals: Dict[str, float] = {}
        self._history: List[AdjustmentRecord] = []
        self._adjustment_count = 0
        self._started = False

        self._register_default_rules()

    @property
    def repository(self) -> RuntimePolicyRepository:
        return self._repository

    @property
    def is_running(self) -> bool:
        return self._started

    def _register_default_rules(self) -> None:
        defaults = [
            AdaptiveRule(
                rule_id="latency-high-decrease-timeout",
                signal=AdjustmentSignal.LATENCY,
                threshold=5000.0,
                comparison=">",
                action=AdjustmentAction.DECREASE_TIMEOUT,
                adjustment={"timeout_ms_delta": -5000},
            ),
            AdaptiveRule(
                rule_id="failure-high-enable-circuit",
                signal=AdjustmentSignal.FAILURE_RATE,
                threshold=0.5,
                comparison=">",
                action=AdjustmentAction.ENABLE_CIRCUIT,
                adjustment={"max_connections": 100},
            ),
            AdaptiveRule(
                rule_id="traffic-high-increase-rate-limit",
                signal=AdjustmentSignal.TRAFFIC,
                threshold=10000.0,
                comparison=">",
                action=AdjustmentAction.INCREASE_RATE_LIMIT,
                adjustment={"rate_delta": 2000},
            ),
            AdaptiveRule(
                rule_id="cpu-high-scale-up",
                signal=AdjustmentSignal.CPU,
                threshold=0.8,
                comparison=">",
                action=AdjustmentAction.SCALE_UP,
                adjustment={"replica_delta": 1},
            ),
            AdaptiveRule(
                rule_id="memory-high-scale-up",
                signal=AdjustmentSignal.MEMORY,
                threshold=0.85,
                comparison=">",
                action=AdjustmentAction.SCALE_UP,
                adjustment={"replica_delta": 1},
            ),
        ]
        for rule in defaults:
            self._rules[rule.rule_id] = rule

    def start(self) -> None:
        self._started = True
        logger.info("Adaptive policy engine started")

    def stop(self) -> None:
        self._started = False
        logger.info("Adaptive policy engine stopped")

    def register_rule(self, rule: AdaptiveRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def unregister_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def update_signal(self, signal: str, value: float) -> None:
        with self._lock:
            self._signals[signal] = value

    def update_signals(self, signals: Dict[str, float]) -> None:
        with self._lock:
            self._signals.update(signals)

    def evaluate(self) -> List[AdjustmentRecord]:
        """Evaluate all rules against current signals and apply adjustments."""
        adjustments: List[AdjustmentRecord] = []
        with self._lock:
            rules = list(self._rules.values())
            signals = dict(self._signals)

        for rule in rules:
            if not rule.enabled:
                continue
            value = signals.get(rule.signal)
            if value is None:
                continue
            if rule.matches(value):
                record = self._apply_adjustment(rule, value)
                if record:
                    adjustments.append(record)

        with self._lock:
            self._history.extend(adjustments)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            self._adjustment_count += len(adjustments)

        return adjustments

    def _apply_adjustment(self, rule: AdaptiveRule, signal_value: float) -> Optional[AdjustmentRecord]:
        target = self._repository.get(rule.target_policy)
        old_value = None
        new_value = None

        if target:
            old_config = dict(target.config)
            for key, delta in rule.adjustment.items():
                if key.endswith("_delta"):
                    actual_key = key[:-6]
                    current = target.config.get(actual_key, 0)
                    new_val = current + delta
                    target.config[actual_key] = new_val
                    new_value = new_val
                else:
                    target.config[key] = delta
                    new_value = delta
            target.updated_at = datetime.utcnow()
            target.version += 1

        return AdjustmentRecord(
            rule_id=rule.rule_id,
            signal=rule.signal,
            action=rule.action,
            target_policy=rule.target_policy,
            old_value=old_value,
            new_value=new_value,
            reason=f"Signal {rule.signal}={signal_value} {rule.comparison} {rule.threshold}",
        )

    def get_signals(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._signals)

    def get_rules(self) -> List[AdaptiveRule]:
        with self._lock:
            return list(self._rules.values())

    def get_history(self, limit: int = 100) -> List[AdjustmentRecord]:
        with self._lock:
            return list(self._history[-limit:])

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "rule_count": len(self._rules),
                "signal_count": len(self._signals),
                "adjustment_count": self._adjustment_count,
                "history_count": len(self._history),
            }

    def clear(self) -> None:
        with self._lock:
            self._signals.clear()
            self._history.clear()
            self._adjustment_count = 0
