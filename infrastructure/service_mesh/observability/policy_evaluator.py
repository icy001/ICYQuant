"""Runtime policy evaluator for ICYQuant Service Mesh.

Provides ``PolicyEvaluator`` for evaluating runtime policies
(retry, timeout, rate limit, circuit breaker, authorization)
with dynamic hot-update support.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .policy_repository import RuntimePolicy, RuntimePolicyRepository

logger = logging.getLogger(__name__)


class PolicyType(str):
    """Runtime policy types."""

    RETRY = "retry"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    CIRCUIT_BREAKER = "circuit_breaker"
    AUTHORIZATION = "authorization"
    TRAFFIC = "traffic"


class EvaluationResult:
    """Result of a policy evaluation."""

    def __init__(
        self,
        policy_id: str,
        policy_type: str,
        allowed: bool,
        params: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> None:
        self.policy_id = policy_id
        self.policy_type = policy_type
        self.allowed = allowed
        self.params = params or {}
        self.reason = reason
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_type": self.policy_type,
            "allowed": self.allowed,
            "params": dict(self.params),
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class PolicyEvaluator:
    """Evaluates runtime policies for mesh traffic."""

    def __init__(
        self,
        repository: Optional[RuntimePolicyRepository] = None,
    ) -> None:
        self._repository = repository or RuntimePolicyRepository()
        self._lock = threading.RLock()
        self._evaluation_count = 0
        self._allow_count = 0
        self._deny_count = 0
        self._listeners: List[Any] = []
        self._started = False

    @property
    def repository(self) -> RuntimePolicyRepository:
        return self._repository

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Policy evaluator started")

    def stop(self) -> None:
        self._started = False
        logger.info("Policy evaluator stopped")

    def register_policy(self, policy: RuntimePolicy) -> None:
        self._repository.add(policy)

    def unregister_policy(self, policy_id: str) -> bool:
        return self._repository.remove(policy_id)

    def evaluate(
        self,
        policy_type: str,
        context: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate all policies of a given type for the context."""
        with self._lock:
            self._evaluation_count += 1
            policies = [
                p for p in self._repository.list_enabled()
                if p.policy_type == policy_type
            ]
            policies.sort(key=lambda p: p.priority, reverse=True)

        for policy in policies:
            result = self._evaluate_policy(policy, context)
            if result:
                with self._lock:
                    if result.allowed:
                        self._allow_count += 1
                    else:
                        self._deny_count += 1
                self._notify_listeners(result)
                return result

        # No matching policy - default allow
        with self._lock:
            self._allow_count += 1
        result = EvaluationResult(
            policy_id="default",
            policy_type=policy_type,
            allowed=True,
            reason="no_policy_matched",
        )
        self._notify_listeners(result)
        return result

    def _evaluate_policy(
        self,
        policy: RuntimePolicy,
        context: Dict[str, Any],
    ) -> Optional[EvaluationResult]:
        config = policy.config
        if not config:
            return EvaluationResult(
                policy_id=policy.policy_id,
                policy_type=policy.policy_type,
                allowed=True,
                reason="empty_config",
            )

        # Check service filter
        from_service = config.get("from_service")
        to_service = config.get("to_service")
        if from_service and context.get("source") != from_service:
            return None
        if to_service and context.get("destination") != to_service:
            return None

        # Check namespace filter
        from_namespace = config.get("from_namespace")
        to_namespace = config.get("to_namespace")
        if from_namespace and context.get("source_namespace") != from_namespace:
            return None
        if to_namespace and context.get("destination_namespace") != to_namespace:
            return None

        # Build evaluation result
        allowed = config.get("allowed", True)
        params = {
            k: v for k, v in config.items()
            if k not in ("from_service", "to_service", "from_namespace", "to_namespace", "allowed")
        }

        return EvaluationResult(
            policy_id=policy.policy_id,
            policy_type=policy.policy_type,
            allowed=allowed,
            params=params,
            reason="policy_matched",
        )

    def evaluate_retry(self, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self.evaluate(PolicyType.RETRY, context)
        return {
            "max_retries": result.params.get("max_retries", 3),
            "retry_on": result.params.get("retry_on", []),
            "backoff_ms": result.params.get("backoff_ms", 100),
            "policy_id": result.policy_id,
        }

    def evaluate_timeout(self, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self.evaluate(PolicyType.TIMEOUT, context)
        return {
            "timeout_ms": result.params.get("timeout_ms", 30000),
            "policy_id": result.policy_id,
        }

    def evaluate_rate_limit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self.evaluate(PolicyType.RATE_LIMIT, context)
        return {
            "rate": result.params.get("rate", 1000),
            "burst": result.params.get("burst", 2000),
            "policy_id": result.policy_id,
        }

    def evaluate_circuit_breaker(self, context: Dict[str, Any]) -> Dict[str, Any]:
        result = self.evaluate(PolicyType.CIRCUIT_BREAKER, context)
        return {
            "max_connections": result.params.get("max_connections", 1000),
            "max_pending_requests": result.params.get("max_pending_requests", 100),
            "max_retries": result.params.get("max_retries", 3),
            "policy_id": result.policy_id,
        }

    def evaluate_authorization(self, context: Dict[str, Any]) -> bool:
        result = self.evaluate(PolicyType.AUTHORIZATION, context)
        return result.allowed

    def reload_from_config(self, config: Dict[str, Any]) -> int:
        """Hot-reload policies from configuration platform."""
        count = 0
        for policy_data in config.get("policies", []):
            policy = RuntimePolicy.from_dict(policy_data)
            self.register_policy(policy)
            count += 1
        logger.info("Reloaded %d policies from config", count)
        return count

    def add_listener(self, listener: Any) -> None:
        self._listeners.append(listener)

    def _notify_listeners(self, result: EvaluationResult) -> None:
        for listener in self._listeners:
            try:
                listener(result)
            except Exception as exc:
                logger.warning("Policy listener failed: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "evaluation_count": self._evaluation_count,
                "allow_count": self._allow_count,
                "deny_count": self._deny_count,
                "policy_count": self._repository.get_stats()["policy_count"],
            }
