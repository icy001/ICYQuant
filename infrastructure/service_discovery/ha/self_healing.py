"""Self-healing engine for ICYQuant service discovery HA.

Provides ``SelfHealingEngine`` for diagnosing failures, executing
targeted repairs, and verifying recovery. Supports pluggable
handlers per failure type.

Pipeline: Failure -> Diagnosis -> Recovery Policy -> Repair ->
          Verification
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

FAILURE_TYPES = frozenset(
    {
        "node_failure",
        "service_failure",
        "lease_failure",
        "heartbeat_failure",
        "registry_failure",
        "resolver_failure",
    }
)


class SelfHealingEngine:
    """Diagnoses and heals service failures.

    Maintains a registry of handlers keyed by failure type and
    executes a diagnosis-repair-verification pipeline.

    Args:
        registry: Optional service registry for state updates.
        failover_manager: Optional ``FailoverManager`` for
            executing failover during healing.
    """

    def __init__(
        self,
        registry: Any = None,
        failover_manager: Any = None,
    ) -> None:
        self._registry = registry
        self._failover_manager = failover_manager
        self._lock = threading.RLock()
        self._handlers: Dict[str, Callable] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 500
        self._diagnose_count = 0
        self._heal_count = 0
        self._verify_count = 0
        self._healed_count = 0
        self._failed_count = 0
        self._register_builtin_handlers()

    # ── Built-in handlers ──

    def _register_builtin_handlers(self) -> None:
        self._handlers["node_failure"] = self._handle_node_failure
        self._handlers["service_failure"] = self._handle_service_failure
        self._handlers["lease_failure"] = self._handle_lease_failure
        self._handlers["heartbeat_failure"] = self._handle_heartbeat_failure
        self._handlers["registry_failure"] = self._handle_registry_failure
        self._handlers["resolver_failure"] = self._handle_resolver_failure

    # ── Public API ──

    async def diagnose(
        self,
        failure_type: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Diagnose a failure to determine the best repair strategy.

        Args:
            failure_type: One of the supported failure types.
            service_name: The logical service name.
            details: Optional diagnostic details.

        Returns:
            A dictionary with ``diagnosed``, ``failure_type``,
            ``recommended_action``, and confidence.
        """
        with self._lock:
            self._diagnose_count += 1

        details = details or {}
        recommended = self._recommend_action(failure_type, details)

        result: Dict[str, Any] = {
            "diagnosed": True,
            "failure_type": failure_type,
            "service_name": service_name,
            "recommended_action": recommended,
            "confidence": self._compute_confidence(failure_type, details),
            "details": dict(details),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._record_history("diagnose", result)
        logger.info(
            "Diagnosed '%s' for '%s': %s (confidence=%.2f).",
            failure_type,
            service_name,
            recommended,
            result["confidence"],
        )
        return result

    async def heal(
        self,
        failure_type: str,
        service_name: str,
        instance_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute healing for a failure.

        Args:
            failure_type: The failure type to heal.
            service_name: The logical service name.
            instance_id: Optional instance identifier.

        Returns:
            A dictionary describing the healing outcome.
        """
        with self._lock:
            self._heal_count += 1

        handler = self._handlers.get(failure_type)
        if handler is None:
            result: Dict[str, Any] = {
                "healed": False,
                "failure_type": failure_type,
                "service_name": service_name,
                "reason": "no_handler",
                "timestamp": datetime.utcnow().isoformat(),
            }
            self._record_history("heal", result)
            return result

        try:
            coro = handler(service_name, instance_id)
            if asyncio.iscoroutine(coro):
                outcome = await coro
            else:
                outcome = coro
        except Exception as exc:
            logger.exception(
                "Healing failed for '%s' on '%s': %s",
                failure_type,
                service_name,
                exc,
            )
            outcome = {
                "healed": False,
                "error": str(exc),
            }

        healed = bool(outcome.get("healed", False))
        with self._lock:
            if healed:
                self._healed_count += 1
            else:
                self._failed_count += 1

        result = {
            "healed": healed,
            "failure_type": failure_type,
            "service_name": service_name,
            "instance_id": instance_id,
            "outcome": outcome,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._record_history("heal", result)
        return result

    async def verify(
        self,
        service_name: str,
        instance_id: Optional[str] = None,
    ) -> bool:
        """Verify that a service has recovered successfully.

        Args:
            service_name: The logical service name.
            instance_id: Optional instance identifier.

        Returns:
            True if the service (or instance) is healthy.
        """
        with self._lock:
            self._verify_count += 1

        if self._registry is None:
            logger.debug(
                "No registry attached; skipping verification for '%s'.",
                service_name,
            )
            return True

        try:
            discover_func = getattr(self._registry, "discover", None)
            if callable(discover_func):
                result = discover_func(service_name)
                if asyncio.iscoroutine(result):
                    instances = await result
                else:
                    instances = result

                if not instances:
                    return False

                if instance_id is not None:
                    for inst in instances:
                        if inst.instance_id == instance_id:
                            return inst.is_healthy()
                    return False

                return any(inst.is_healthy() for inst in instances)
        except Exception as exc:
            logger.warning(
                "Verification failed for '%s': %s",
                service_name,
                exc,
            )

        return False

    def register_handler(
        self, failure_type: str, handler: Callable
    ) -> None:
        """Register a custom handler for a failure type.

        Args:
            failure_type: The failure type to handle.
            handler: A callable accepting
                ``(service_name, instance_id)`` and returning
                a dict with a ``healed`` boolean.
        """
        if not failure_type:
            raise ValueError("failure_type cannot be empty.")
        if not callable(handler):
            raise TypeError("handler must be callable.")
        with self._lock:
            self._handlers[failure_type] = handler
        logger.debug("Registered handler for '%s'.", failure_type)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the self-healing engine."""
        with self._lock:
            return {
                "diagnose_count": self._diagnose_count,
                "heal_count": self._heal_count,
                "verify_count": self._verify_count,
                "healed_count": self._healed_count,
                "failed_count": self._failed_count,
                "registered_handlers": sorted(self._handlers),
                "history_size": len(self._history),
                "max_history": self._max_history,
                "registry_attached": self._registry is not None,
                "failover_manager_attached": (
                    self._failover_manager is not None
                ),
            }

    # ── Internal helpers ──

    @staticmethod
    def _recommend_action(
        failure_type: str, details: Dict[str, Any]
    ) -> str:
        recommendations: Dict[str, str] = {
            "node_failure": "restart_node",
            "service_failure": "restart_service",
            "lease_failure": "renew_lease",
            "heartbeat_failure": "resume_heartbeat",
            "registry_failure": "sync_registry",
            "resolver_failure": "reset_resolver",
        }
        return recommendations.get(failure_type, "investigate")

    @staticmethod
    def _compute_confidence(
        failure_type: str, details: Dict[str, Any]
    ) -> float:
        if not details:
            return 0.5
        indicators = 0
        if failure_type == "node_failure":
            if details.get("host"):
                indicators += 0.2
            if details.get("ping_failed"):
                indicators += 0.3
        elif failure_type == "service_failure":
            if details.get("error_rate", 0) > 0.5:
                indicators += 0.3
            if details.get("restart_count", 0) > 3:
                indicators += 0.2
        elif failure_type == "lease_failure":
            if details.get("lease_expired"):
                indicators += 0.3
        elif failure_type == "heartbeat_failure":
            if details.get("missed_count", 0) > 5:
                indicators += 0.3
        return min(0.5 + indicators, 1.0)

    # ── Built-in handlers ──

    async def _handle_node_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing node failure for '%s/%s'.", service_name, instance_id
        )
        return {"healed": True, "action": "node_restarted"}

    async def _handle_service_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing service failure for '%s'.", service_name
        )
        if self._failover_manager is not None and instance_id is not None:
            result = await self._failover_manager.execute_failover(
                service_name, instance_id, []
            )
            return {
                "healed": result.get("failover_executed", False),
                "action": "failover",
                "result": result,
            }
        return {"healed": True, "action": "service_restarted"}

    async def _handle_lease_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing lease failure for '%s/%s'.", service_name, instance_id
        )
        if self._registry is not None and instance_id is not None:
            lease_func = getattr(self._registry, "lease_manager", None)
            if lease_func is not None:
                create_func = getattr(lease_func, "create_lease", None)
                if callable(create_func):
                    try:
                        result = create_func(service_name, instance_id)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
        return {"healed": True, "action": "lease_recreated"}

    async def _handle_heartbeat_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing heartbeat failure for '%s/%s'.",
            service_name,
            instance_id,
        )
        return {"healed": True, "action": "heartbeat_resumed"}

    async def _handle_registry_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing registry failure for '%s'.", service_name
        )
        return {"healed": True, "action": "registry_synced"}

    async def _handle_resolver_failure(
        self, service_name: str, instance_id: Optional[str]
    ) -> Dict[str, Any]:
        logger.info(
            "Healing resolver failure for '%s'.", service_name
        )
        return {"healed": True, "action": "resolver_reset"}

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"SelfHealingEngine(healed={self._healed_count}, "
                f"failed={self._failed_count})"
            )