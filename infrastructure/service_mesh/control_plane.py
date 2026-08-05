"""Control Plane for the Service Mesh.

Provides ``ControlPlane`` for managing routing rules, security
policies, traffic policies, and certificate policies, and
distributing configuration to data plane proxies.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .models import RoutingRule
from .exceptions import ControlPlaneError

logger = logging.getLogger(__name__)


class ControlPlane:
    """Control plane for managing mesh configuration and policy."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._rules: Dict[str, RoutingRule] = {}
        self._security_policies: Dict[str, Dict[str, Any]] = {}
        self._traffic_policies: Dict[str, Dict[str, Any]] = {}
        self._certificate_policies: Dict[str, Dict[str, Any]] = {}
        self._publisher: Optional[MeshEventPublisher] = None
        self._synchronize_count = 0
        self._last_synchronize: Optional[Dict[str, Any]] = None
        self._running = False

        self._context.register("control_plane", self)

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    async def start(self) -> Dict[str, Any]:
        """Start the control plane."""
        with self._lock:
            self._running = True
        logger.info("Control plane started.")
        return {"success": True, "status": "running"}

    async def stop(self) -> Dict[str, Any]:
        """Stop the control plane."""
        with self._lock:
            self._running = False
        logger.info("Control plane stopped.")
        return {"success": True, "status": "stopped"}

    @property
    def is_running(self) -> bool:
        return self._running

    def add_routing_rule(
        self,
        rule: RoutingRule,
    ) -> None:
        """Add or update a routing rule."""
        with self._lock:
            self._rules[rule.rule_id] = rule
        logger.info(
            "Routing rule '%s' added for service '%s'.",
            rule.rule_id,
            rule.service,
        )

    def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def get_routing_rules(
        self, service: Optional[str] = None
    ) -> List[RoutingRule]:
        with self._lock:
            rules = list(self._rules.values())
        if service:
            rules = [r for r in rules if r.service == service]
        return rules

    def set_security_policy(
        self,
        policy_id: str,
        policy: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._security_policies[policy_id] = policy

    def set_traffic_policy(
        self,
        policy_id: str,
        policy: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._traffic_policies[policy_id] = policy

    def set_certificate_policy(
        self,
        policy_id: str,
        policy: Dict[str, Any],
    ) -> None:
        with self._lock:
            self._certificate_policies[policy_id] = policy

    async def publish_configuration(
        self,
        config_type: str = "routing",
    ) -> Dict[str, Any]:
        """Publish configuration to subscribed proxies."""
        with self._lock:
            self._synchronize_count += 1
            if config_type == "routing":
                config_data = {
                    "rules": [
                        r.to_dict() for r in self._rules.values()
                    ]
                }
            elif config_type == "security":
                config_data = {
                    "policies": dict(self._security_policies)
                }
            elif config_type == "traffic":
                config_data = {
                    "policies": dict(self._traffic_policies)
                }
            elif config_type == "certificates":
                config_data = {
                    "policies": dict(self._certificate_policies)
                }
            else:
                config_data = {
                    "rules": [
                        r.to_dict() for r in self._rules.values()
                    ],
                    "security": dict(self._security_policies),
                    "traffic": dict(self._traffic_policies),
                    "certificates": dict(self._certificate_policies),
                }

            result = {
                "config_type": config_type,
                "version": self._synchronize_count,
                "data": config_data,
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._last_synchronize = result

        if self._publisher:
            await self._publisher.publish(
                MeshEvent.CONFIGURATION_PUBLISHED,
                {"config_type": config_type, "version": self._synchronize_count},
            )

        logger.info(
            "Configuration published: %s (v%d).",
            config_type,
            self._synchronize_count,
        )
        return result

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize all configuration to data plane."""
        results: Dict[str, Any] = {}
        for config_type in ["routing", "security", "traffic", "certificates"]:
            try:
                result = await self.publish_configuration(config_type)
                results[config_type] = {"success": True, "version": result["version"]}
            except Exception as exc:
                results[config_type] = {
                    "success": False,
                    "error": str(exc),
                }

        all_ok = all(
            r.get("success", False) for r in results.values()
        )
        return {
            "success": all_ok,
            "synchronizations": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_configuration(
        self, config_type: str = "all"
    ) -> Dict[str, Any]:
        """Get current configuration."""
        with self._lock:
            if config_type == "routing":
                return {
                    "rules": [
                        r.to_dict() for r in self._rules.values()
                    ]
                }
            elif config_type == "security":
                return {"policies": dict(self._security_policies)}
            elif config_type == "traffic":
                return {"policies": dict(self._traffic_policies)}
            elif config_type == "certificates":
                return {"policies": dict(self._certificate_policies)}
            else:
                return {
                    "rules": [
                        r.to_dict() for r in self._rules.values()
                    ],
                    "security": dict(self._security_policies),
                    "traffic": dict(self._traffic_policies),
                    "certificates": dict(self._certificate_policies),
                }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "routing_rules": len(self._rules),
                "security_policies": len(self._security_policies),
                "traffic_policies": len(self._traffic_policies),
                "certificate_policies": len(self._certificate_policies),
                "synchronize_count": self._synchronize_count,
                "last_synchronize": self._last_synchronize,
            }

    def clear(self) -> None:
        with self._lock:
            self._rules.clear()
            self._security_policies.clear()
            self._traffic_policies.clear()
            self._certificate_policies.clear()
            self._synchronize_count = 0
            self._last_synchronize = None

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ControlPlane(running={self._running}, "
                f"rules={len(self._rules)})"
            )
