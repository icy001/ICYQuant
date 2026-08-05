"""Data Plane for the Service Mesh.

Provides ``DataPlane`` for traffic proxying, retry, circuit
breaking, load balancing, and telemetry collection at the
proxy level.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .models import ProxyConfig, ProxyProtocol, RoutingRule
from .exceptions import (
    CircuitBreakerOpenError,
    DataPlaneError,
    ProxyTimeoutError,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for protecting backend services."""

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout_s = reset_timeout_s
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._open = False

    @property
    def is_open(self) -> bool:
        if not self._open:
            return False
        if (
            self._last_failure_time
            and (time.monotonic() - self._last_failure_time)
            > self._reset_timeout_s
        ):
            self._open = False
            self._failure_count = 0
            logger.info("Circuit breaker reset to closed state.")
            return False
        return True

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._open = True
            logger.warning("Circuit breaker OPEN after %d failures.", self._failure_count)

    def record_success(self) -> None:
        self._failure_count = max(0, self._failure_count - 1)
        if self._failure_count == 0:
            self._open = False

    def reset(self) -> None:
        self._failure_count = 0
        self._last_failure_time = None
        self._open = False

    def get_state(self) -> Dict[str, Any]:
        return {
            "open": self._open,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "last_failure": self._last_failure_time,
        }


class DataPlane:
    """Data plane for traffic proxying and enforcement."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
        config: Optional[ProxyConfig] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._config = config or ProxyConfig()
        self._publisher: Optional[MeshEventPublisher] = None
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._rules: List[RoutingRule] = []
        self._request_count = 0
        self._active_connections = 0
        self._running = False
        self._start_time: Optional[float] = None

        self._context.register("data_plane", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    async def start(self) -> Dict[str, Any]:
        with self._lock:
            self._running = True
            self._start_time = time.monotonic()
        logger.info(
            "Data plane started on %s:%d.",
            self._config.listen_host,
            self._config.listen_port,
        )
        return {"success": True, "status": "running"}

    async def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._running = False
        logger.info("Data plane stopped.")
        return {"success": True, "status": "stopped"}

    @property
    def is_running(self) -> bool:
        return self._running

    def configure(self, config: ProxyConfig) -> None:
        with self._lock:
            self._config = config

    def update_routing_rules(self, rules: List[RoutingRule]) -> None:
        with self._lock:
            self._rules = list(rules)

    async def intercept(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Intercept and route an incoming request."""
        with self._lock:
            self._request_count += 1
            self._active_connections += 1

        try:
            rule = self._match_rule(method, path)
            if rule is None:
                return {
                    "status": 404,
                    "body": {"error": "No route found"},
                    "matched_rule": None,
                }

            result = await self._execute_rule(rule, method, path, headers)
            return result
        except Exception as exc:
            return {
                "status": 500,
                "body": {"error": str(exc)},
                "matched_rule": None,
            }
        finally:
            with self._lock:
                self._active_connections = max(
                    0, self._active_connections - 1
                )

    async def forward(
        self,
        target: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Forward a request to a target service."""
        cb = self._get_circuit_breaker(target)
        if cb.is_open:
            raise CircuitBreakerOpenError(
                f"Circuit breaker open for {target}"
            )

        start = time.monotonic()
        try:
            result = await self._do_forward(target, method, path, headers)
            cb.record_success()
            duration = time.monotonic() - start
            if self._publisher:
                await self._publisher.publish(
                    MeshEvent.PROXY_RELOADED,
                    {
                        "target": target,
                        "status": "success",
                        "duration_s": duration,
                    },
                )
            return result
        except Exception as exc:
            cb.record_failure()
            raise

    def _match_rule(
        self, method: str, path: str
    ) -> Optional[RoutingRule]:
        with self._lock:
            rules = [r for r in self._rules if r.enabled]
        for rule in rules:
            if rule.methods and method not in rule.methods:
                continue
            if rule.path and path.startswith(rule.path):
                return rule
        return None

    async def _execute_rule(
        self,
        rule: RoutingRule,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        target = rule.destination or rule.service
        cb = self._get_circuit_breaker(target)

        if cb.is_open:
            return {
                "status": 503,
                "body": {"error": "Circuit breaker open"},
                "matched_rule": rule.rule_id,
            }

        max_retries = rule.retry_policy.get("max_retries", 0)
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self._do_forward(
                    target, method, path, headers
                )
                cb.record_success()
                result["matched_rule"] = rule.rule_id
                return result
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    cb.record_failure()
                    await asyncio.sleep(
                        rule.retry_policy.get("backoff_ms", 100) / 1000.0
                    )
                else:
                    cb.record_failure()

        return {
            "status": 502,
            "body": {"error": str(last_error)},
            "matched_rule": rule.rule_id,
        }

    async def _do_forward(
        self,
        target: str,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return {
            "status": 200,
            "body": {
                "target": target,
                "method": method,
                "path": path,
                "forwarded": True,
            },
            "headers": headers or {},
        }

    def _get_circuit_breaker(
        self, target: str
    ) -> CircuitBreaker:
        if target not in self._circuit_breakers:
            self._circuit_breakers[target] = CircuitBreaker()
        return self._circuit_breakers[target]

    def get_circuit_breaker_state(
        self, target: Optional[str] = None
    ) -> Dict[str, Any]:
        if target:
            cb = self._circuit_breakers.get(target)
            return cb.get_state() if cb else {"open": False}
        return {
            target: cb.get_state()
            for target, cb in self._circuit_breakers.items()
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "config": self._config.to_dict(),
                "rules_count": len(self._rules),
                "request_count": self._request_count,
                "active_connections": self._active_connections,
                "start_time": self._start_time,
                "circuit_breakers": {
                    k: v.get_state()
                    for k, v in self._circuit_breakers.items()
                },
            }

    def clear(self) -> None:
        with self._lock:
            self._rules.clear()
            self._circuit_breakers.clear()
            self._request_count = 0
            self._active_connections = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DataPlane(running={self._running}, "
                f"rules={len(self._rules)}, "
                f"requests={self._request_count})"
            )
