"""Configuration management for the Service Mesh.

Provides ``MeshConfiguration`` for managing routing rules,
retry policies, timeout policies, and security policies,
integrating with the ICYQuant Configuration Platform.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .context import MeshContext
from .models import RoutingRule
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class MeshConfiguration:
    """Configuration manager for the service mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._config_source: Optional[Any] = None
        self._routing_rules: Dict[str, RoutingRule] = {}
        self._retry_policies: Dict[str, Dict[str, Any]] = {}
        self._timeout_policies: Dict[str, float] = {}
        self._security_policies: Dict[str, Dict[str, Any]] = {}
        self._traffic_policies: Dict[str, Dict[str, Any]] = {}
        self._version = 0
        self._publish_count = 0

        self._context.register("configuration", self)

    def set_config_source(self, source: Any) -> None:
        self._config_source = source

    def add_routing_rule(
        self,
        rule_id: str,
        service: str,
        path: str = "/",
        methods: Optional[List[str]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        timeout_s: float = 30.0,
        weight: float = 1.0,
        enabled: bool = True,
    ) -> RoutingRule:
        rule = RoutingRule(
            rule_id=rule_id,
            service=service,
            path=path,
            methods=methods,
            retry_policy=retry_policy,
            timeout_s=timeout_s,
            weight=weight,
            enabled=enabled,
        )
        with self._lock:
            self._routing_rules[rule_id] = rule
            self._version += 1
        return rule

    def remove_routing_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self._routing_rules:
                del self._routing_rules[rule_id]
                self._version += 1
                return True
        return False

    def get_routing_rules(
        self, service: Optional[str] = None
    ) -> List[RoutingRule]:
        with self._lock:
            rules = list(self._routing_rules.values())
        if service:
            rules = [r for r in rules if r.service == service]
        return rules

    def set_retry_policy(
        self,
        service: str,
        max_retries: int = 2,
        backoff_ms: float = 100,
        retry_on: Optional[List[str]] = None,
    ) -> None:
        with self._lock:
            self._retry_policies[service] = {
                "max_retries": max_retries,
                "backoff_ms": backoff_ms,
                "retry_on": retry_on or [
                    "5xx", "connection_error", "timeout"
                ],
            }

    def get_retry_policy(self, service: str) -> Dict[str, Any]:
        with self._lock:
            return self._retry_policies.get(
                service,
                {"max_retries": 2, "backoff_ms": 100},
            )

    def set_timeout_policy(
        self,
        service: str,
        timeout_s: float = 30.0,
    ) -> None:
        with self._lock:
            self._timeout_policies[service] = timeout_s

    def get_timeout_policy(self, service: str) -> float:
        with self._lock:
            return self._timeout_policies.get(service, 30.0)

    def set_security_policy(
        self,
        policy_id: str,
        policy: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._security_policies[policy_id] = policy

    def get_security_policies(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._security_policies)

    def set_traffic_policy(
        self,
        policy_id: str,
        policy: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._traffic_policies[policy_id] = policy

    def get_traffic_policies(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._traffic_policies)

    def get_all_configuration(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "version": self._version,
                "routing_rules": [
                    r.to_dict()
                    for r in self._routing_rules.values()
                ],
                "retry_policies": dict(self._retry_policies),
                "timeout_policies": dict(self._timeout_policies),
                "security_policies": dict(self._security_policies),
                "traffic_policies": dict(self._traffic_policies),
            }

    def apply_configuration(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply configuration from a dictionary."""
        try:
            routing = config.get("routing_rules", [])
            for rule_data in routing:
                self.add_routing_rule(
                    rule_id=rule_data.get("rule_id", ""),
                    service=rule_data.get("service", ""),
                    path=rule_data.get("path", "/"),
                    methods=rule_data.get("methods"),
                    retry_policy=rule_data.get("retry_policy"),
                    timeout_s=rule_data.get("timeout_s", 30.0),
                    weight=rule_data.get("weight", 1.0),
                    enabled=rule_data.get("enabled", True),
                )

            retry = config.get("retry_policies", {})
            for svc, policy in retry.items():
                self.set_retry_policy(
                    service=svc,
                    max_retries=policy.get("max_retries", 2),
                    backoff_ms=policy.get("backoff_ms", 100),
                )

            timeouts = config.get("timeout_policies", {})
            for svc, timeout in timeouts.items():
                self.set_timeout_policy(service=svc, timeout_s=timeout)

            return {"success": True, "version": self._version}
        except Exception as exc:
            raise ConfigurationError(str(exc))

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "version": self._version,
                "routing_rules": len(self._routing_rules),
                "retry_policies": len(self._retry_policies),
                "timeout_policies": len(self._timeout_policies),
                "security_policies": len(self._security_policies),
                "traffic_policies": len(self._traffic_policies),
                "has_config_source": bool(self._config_source),
            }

    def clear(self) -> None:
        with self._lock:
            self._routing_rules.clear()
            self._retry_policies.clear()
            self._timeout_policies.clear()
            self._security_policies.clear()
            self._traffic_policies.clear()
            self._version = 0

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshConfiguration(version={self._version}, "
                f"rules={len(self._routing_rules)})"
            )
