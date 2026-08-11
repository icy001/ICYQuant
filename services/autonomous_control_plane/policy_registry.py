"""
Policy Registry — Storage and indexing for all policies.

Maintains versioned policies across all domains with activation status.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Policy:
    """A single policy rule with scope, version, and evaluation logic."""

    def __init__(
        self,
        policy_id: str,
        name: str,
        scope: str,
        rule: Any,
        version: str = "1.0",
        priority: int = 0,
        active: bool = True,
    ):
        self.policy_id = policy_id
        self.name = name
        self.scope = scope
        self.rule = rule
        self.version = version
        self.priority = priority
        self.active = active
        self.created_at = time.time()
        self.updated_at = time.time()

    def evaluate(self, context):
        """Evaluate this policy against a context."""
        from .control_plane import ControlPlaneDecision

        try:
            result = self.rule.evaluate(context)
            if hasattr(result, "decision"):
                return result
            return PolicyEvaluationResult(
                policy_id=self.policy_id,
                decision=ControlPlaneDecision.ALLOW if result else ControlPlaneDecision.DENY,
            )
        except Exception:
            return PolicyEvaluationResult(
                policy_id=self.policy_id,
                decision=ControlPlaneDecision.DENY,
                reason=f"Policy {self.policy_id} evaluation failed",
            )


class PolicyEvaluationResult:
    """Result of a single policy evaluation."""

    def __init__(self, policy_id: str, decision=None, reason: str = ""):
        from .control_plane import ControlPlaneDecision
        self.policy_id = policy_id
        self.decision = decision or ControlPlaneDecision.ALLOW
        self.reason = reason


class PolicyRegistry:
    """
    Registry for all policies in the ICYQuant Control Plane.

    Supports versioning, activation/deactivation, and querying by scope.
    """

    def __init__(self):
        self._policies: dict[str, Policy] = {}
        self._by_scope: dict[str, list[str]] = {}
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, policy: Policy) -> None:
        """Register a policy."""
        self._policies[policy.policy_id] = policy
        self._by_scope.setdefault(policy.scope, []).append(policy.policy_id)
        self._history.append({
            "action": "add",
            "policy_id": policy.policy_id,
            "version": policy.version,
            "timestamp": time.time(),
        })

    def update(self, policy_id: str, updates: dict) -> Optional[Policy]:
        """Update an existing policy."""
        policy = self._policies.get(policy_id)
        if not policy:
            return None
        for key, value in updates.items():
            if hasattr(policy, key):
                setattr(policy, key, value)
        policy.updated_at = time.time()
        self._history.append({
            "action": "update",
            "policy_id": policy_id,
            "updates": updates,
            "timestamp": time.time(),
        })
        return policy

    def deactivate(self, policy_id: str) -> bool:
        """Deactivate a policy."""
        policy = self._policies.get(policy_id)
        if policy:
            policy.active = False
            return True
        return False

    def activate(self, policy_id: str) -> bool:
        """Activate a policy."""
        policy = self._policies.get(policy_id)
        if policy:
            policy.active = True
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def active(self, scope: Optional[str] = None) -> list[Policy]:
        """Get all active policies, optionally filtered by scope."""
        if scope:
            ids = self._by_scope.get(scope, [])
            policies = [self._policies[pid] for pid in ids if pid in self._policies]
        else:
            policies = list(self._policies.values())
        return [p for p in policies if p.active]

    def get(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)

    def get_by_scope(self, scope: str) -> list[Policy]:
        return [self._policies[pid] for pid in self._by_scope.get(scope, []) if pid in self._policies]

    def all_scopes(self) -> list[str]:
        return list(self._by_scope.keys())

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "total_policies": len(self._policies),
            "active_policies": len([p for p in self._policies.values() if p.active]),
            "scopes": self.all_scopes(),
            "history_length": len(self._history),
        }
