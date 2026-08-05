"""Destination rule for ICYQuant Service Mesh.

Provides ``DestinationRule`` for defining policies applied to
traffic destined for a specific host: load balancer, connection
pool, retry, circuit breaker, and TLS configuration.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DestinationRule:
    """Defines policies for traffic destined for a host."""

    def __init__(
        self,
        rule_id: str,
        host: str,
        traffic_policy_id: str = "",
        load_balancer_type: str = "round_robin",
        connection_pool: Optional[Dict[str, Any]] = None,
        outlier_detection: Optional[Dict[str, Any]] = None,
        tls_mode: str = "PERMISSIVE",
        subsets: Optional[List[Dict[str, Any]]] = None,
        export_to: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.rule_id = rule_id
        self.host = host
        self.traffic_policy_id = traffic_policy_id
        self.load_balancer_type = load_balancer_type
        self.connection_pool = connection_pool or {
            "max_connections": 1024,
            "max_pending_requests": 1024,
            "max_requests": 1024,
            "max_retries": 3,
        }
        self.outlier_detection = outlier_detection or {
            "consecutive_errors": 5,
            "interval_s": 10.0,
            "base_ejection_time_s": 30.0,
            "max_ejection_percent": 50,
        }
        self.tls_mode = tls_mode
        self.subsets = subsets or []
        self.export_to = export_to or ["*"]
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_subset(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        version: str = "",
    ) -> None:
        self.subsets.append(
            {
                "name": name,
                "labels": labels or {},
                "version": version,
            }
        )
        self.updated_at = datetime.utcnow()

    def get_subset(self, name: str) -> Optional[Dict[str, Any]]:
        for s in self.subsets:
            if s["name"] == name:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "host": self.host,
            "traffic_policy_id": self.traffic_policy_id,
            "load_balancer_type": self.load_balancer_type,
            "connection_pool": self.connection_pool,
            "outlier_detection": self.outlier_detection,
            "tls_mode": self.tls_mode,
            "subsets": self.subsets,
            "export_to": self.export_to,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DestinationRuleManager:
    """Manages destination rules."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rules: Dict[str, DestinationRule] = {}
        self._host_index: Dict[str, str] = {}
        self._update_count = 0

    def register(self, rule: DestinationRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule
            self._host_index[rule.host] = rule.rule_id
            self._update_count += 1

    def unregister(self, rule_id: str) -> bool:
        with self._lock:
            rule = self._rules.pop(rule_id, None)
            if rule:
                self._host_index.pop(rule.host, None)
                self._update_count += 1
                return True
            return False

    def get_rule(self, rule_id: str) -> Optional[DestinationRule]:
        with self._lock:
            return self._rules.get(rule_id)

    def get_rule_for_host(
        self, host: str
    ) -> Optional[DestinationRule]:
        with self._lock:
            rule_id = self._host_index.get(host)
            if rule_id:
                return self._rules.get(rule_id)
            return None

    def list_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._rules.values()]

    def clear(self) -> None:
        with self._lock:
            self._rules.clear()
            self._host_index.clear()
            self._update_count += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rule_count": len(self._rules),
                "host_index_count": len(self._host_index),
                "update_count": self._update_count,
            }