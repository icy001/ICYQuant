"""Traffic policies for ICYQuant Service Mesh Traffic Management.

Provides unified policy definitions for retry, timeout, circuit breaker,
traffic routing, and rate limiting. Policies are loaded from the
Configuration Platform and applied by the TrafficManager.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Retry policy configuration."""

    def __init__(
        self,
        max_retries: int = 2,
        initial_backoff_ms: int = 100,
        max_backoff_ms: int = 5000,
        backoff_multiplier: float = 2.0,
        retry_on: Optional[List[str]] = None,
        retry_methods: Optional[List[str]] = None,
        per_try_timeout_ms: int = 5000,
    ) -> None:
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.backoff_multiplier = backoff_multiplier
        self.retry_on = retry_on or ["5xx", "gateway-error", "connect-failure"]
        self.retry_methods = retry_methods or ["GET", "HEAD"]
        self.per_try_timeout_ms = per_try_timeout_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "initial_backoff_ms": self.initial_backoff_ms,
            "max_backoff_ms": self.max_backoff_ms,
            "backoff_multiplier": self.backoff_multiplier,
            "retry_on": self.retry_on,
            "retry_methods": self.retry_methods,
            "per_try_timeout_ms": self.per_try_timeout_ms,
        }


class TimeoutPolicy:
    """Timeout policy configuration."""

    def __init__(
        self,
        connect_timeout_ms: int = 5000,
        read_timeout_ms: int = 10000,
        write_timeout_ms: int = 10000,
        overall_timeout_ms: int = 30000,
        idle_timeout_ms: int = 60000,
    ) -> None:
        self.connect_timeout_ms = connect_timeout_ms
        self.read_timeout_ms = read_timeout_ms
        self.write_timeout_ms = write_timeout_ms
        self.overall_timeout_ms = overall_timeout_ms
        self.idle_timeout_ms = idle_timeout_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connect_timeout_ms": self.connect_timeout_ms,
            "read_timeout_ms": self.read_timeout_ms,
            "write_timeout_ms": self.write_timeout_ms,
            "overall_timeout_ms": self.overall_timeout_ms,
            "idle_timeout_ms": self.idle_timeout_ms,
        }


class CircuitPolicy:
    """Circuit breaker policy configuration."""

    def __init__(
        self,
        max_connections: int = 100,
        max_pending_requests: int = 1000,
        max_requests: int = 1000,
        max_retries: int = 3,
        per_host_throttle: int = 100,
        tracking_period_s: float = 60.0,
        burst_size: int = 100,
    ) -> None:
        self.max_connections = max_connections
        self.max_pending_requests = max_pending_requests
        self.max_requests = max_requests
        self.max_retries = max_retries
        self.per_host_throttle = per_host_throttle
        self.tracking_period_s = tracking_period_s
        self.burst_size = burst_size

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_connections": self.max_connections,
            "max_pending_requests": self.max_pending_requests,
            "max_requests": self.max_requests,
            "max_retries": self.max_retries,
            "per_host_throttle": self.per_host_throttle,
            "tracking_period_s": self.tracking_period_s,
            "burst_size": self.burst_size,
        }


class TrafficPolicy:
    """Traffic management policy."""

    def __init__(
        self,
        policy_id: str,
        description: str = "",
        enabled: bool = True,
        priority: int = 100,
        retries: Optional[RetryPolicy] = None,
        timeouts: Optional[TimeoutPolicy] = None,
        circuit: Optional[CircuitPolicy] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.policy_id = policy_id
        self.description = description
        self.enabled = enabled
        self.priority = priority
        self.retries = retries or RetryPolicy()
        self.timeouts = timeouts or TimeoutPolicy()
        self.circuit = circuit or CircuitPolicy()
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "description": self.description,
            "enabled": self.enabled,
            "priority": self.priority,
            "retries": self.retries.to_dict(),
            "timeouts": self.timeouts.to_dict(),
            "circuit": self.circuit.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class RatePolicy:
    """Rate limiting policy."""

    def __init__(
        self,
        policy_id: str,
        rate: float = 100.0,
        burst: int = 200,
        enabled: bool = True,
        strategy: str = "token_bucket",
        per_client: bool = False,
    ) -> None:
        self.policy_id = policy_id
        self.rate = rate
        self.burst = burst
        self.enabled = enabled
        self.strategy = strategy
        self.per_client = per_client
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "rate": self.rate,
            "burst": self.burst,
            "enabled": self.enabled,
            "strategy": self.strategy,
            "per_client": self.per_client,
        }


class PolicyManager:
    """Manages traffic policies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._traffic_policies: Dict[str, TrafficPolicy] = {}
        self._rate_policies: Dict[str, RatePolicy] = {}
        self._listeners: List[Callable] = []
        self._update_count = 0

    def register_traffic_policy(
        self, policy: TrafficPolicy
    ) -> None:
        with self._lock:
            self._traffic_policies[policy.policy_id] = policy
            self._update_count += 1
        self._notify_listeners("traffic_policy_updated", policy)

    def register_rate_policy(
        self, policy: RatePolicy
    ) -> None:
        with self._lock:
            self._rate_policies[policy.policy_id] = policy
            self._update_count += 1
        self._notify_listeners("rate_policy_updated", policy)

    def get_traffic_policy(
        self, policy_id: str
    ) -> Optional[TrafficPolicy]:
        with self._lock:
            return self._traffic_policies.get(policy_id)

    def get_rate_policy(
        self, policy_id: str
    ) -> Optional[RatePolicy]:
        with self._lock:
            return self._rate_policies.get(policy_id)

    def list_traffic_policies(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._traffic_policies.values()]

    def list_rate_policies(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [p.to_dict() for p in self._rate_policies.values()]

    def remove_policy(self, policy_id: str) -> bool:
        with self._lock:
            removed = False
            if policy_id in self._traffic_policies:
                del self._traffic_policies[policy_id]
                removed = True
            if policy_id in self._rate_policies:
                del self._rate_policies[policy_id]
                removed = True
            if removed:
                self._update_count += 1
        if removed:
            self._notify_listeners("policy_removed", policy_id)
        return removed

    def subscribe(self, listener: Callable) -> None:
        with self._lock:
            self._listeners.append(listener)

    def _notify_listeners(
        self, event: str, data: Any
    ) -> None:
        for listener in list(self._listeners):
            try:
                listener(event, data)
            except Exception as exc:
                logger.warning(
                    "Policy listener failed: %s", exc
                )

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "traffic_policy_count": len(self._traffic_policies),
                "rate_policy_count": len(self._rate_policies),
                "update_count": self._update_count,
                "listener_count": len(self._listeners),
            }