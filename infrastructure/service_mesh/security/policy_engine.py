"""Policy engine for ICYQuant Service Mesh.

Provides ``PolicyEngine`` for evaluating allow/deny policies based
on identity, namespace, trust domain, roles, and methods.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PolicyEffect(str):
    """Policy effects."""

    ALLOW = "allow"
    DENY = "deny"


class SecurityPolicy:
    """A security policy."""

    def __init__(
        self,
        policy_id: str,
        effect: str = PolicyEffect.ALLOW,
        from_services: Optional[List[str]] = None,
        to_services: Optional[List[str]] = None,
        from_namespaces: Optional[List[str]] = None,
        to_namespaces: Optional[List[str]] = None,
        from_trust_domains: Optional[List[str]] = None,
        to_trust_domains: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
        priority: int = 100,
        enabled: bool = True,
        description: str = "",
    ) -> None:
        self.policy_id = policy_id
        self.effect = effect
        self.from_services = from_services or ["*"]
        self.to_services = to_services or ["*"]
        self.from_namespaces = from_namespaces or ["*"]
        self.to_namespaces = to_namespaces or ["*"]
        self.from_trust_domains = from_trust_domains or ["*"]
        self.to_trust_domains = to_trust_domains or ["*"]
        self.methods = methods or ["*"]
        self.roles = roles or []
        self.resources = resources or ["*"]
        self.priority = priority
        self.enabled = enabled
        self.description = description
        self.created_at = datetime.utcnow()

    def matches(
        self,
        principal: str = "",
        resource: str = "",
        action: str = "",
        namespace: str = "default",
        trust_domain: str = "icyquant.local",
        roles: Optional[List[str]] = None,
    ) -> bool:
        """Check if this policy matches the request."""
        if not self.enabled:
            return False
        if not self._match_list(self.from_namespaces, namespace):
            return False
        if not self._match_list(self.to_namespaces, namespace):
            return False
        if not self._match_list(self.from_trust_domains, trust_domain):
            return False
        if not self._match_list(self.resources, resource) and not self._match_list(self.to_services, resource):
            return False
        if not self._match_list(self.methods, action):
            return False
        if self.roles:
            roles = roles or []
            if not any(r in roles for r in self.roles):
                return False
        return True

    @staticmethod
    def _match_list(patterns: List[str], value: str) -> bool:
        if "*" in patterns:
            return True
        return value in patterns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "effect": self.effect,
            "from_services": self.from_services,
            "to_services": self.to_services,
            "from_namespaces": self.from_namespaces,
            "to_namespaces": self.to_namespaces,
            "from_trust_domains": self.from_trust_domains,
            "to_trust_domains": self.to_trust_domains,
            "methods": self.methods,
            "roles": self.roles,
            "resources": self.resources,
            "priority": self.priority,
            "enabled": self.enabled,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }


class PolicyEngine:
    """Evaluates security policies."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: Dict[str, SecurityPolicy] = {}
        self._evaluation_count = 0
        self._allow_count = 0
        self._deny_count = 0

    def register_policy(self, policy: SecurityPolicy) -> None:
        with self._lock:
            self._policies[policy.policy_id] = policy

    def unregister_policy(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                return True
            return False

    def get_policy(self, policy_id: str) -> Optional[SecurityPolicy]:
        with self._lock:
            return self._policies.get(policy_id)

    def list_policies(self) -> List[SecurityPolicy]:
        with self._lock:
            return sorted(
                self._policies.values(),
                key=lambda p: p.priority,
                reverse=True,
            )

    def evaluate(
        self,
        principal: str = "",
        resource: str = "",
        action: str = "access",
        namespace: str = "default",
        trust_domain: str = "icyquant.local",
        roles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Evaluate policies for a request. Deny takes precedence."""
        with self._lock:
            self._evaluation_count += 1
            policies = sorted(
                self._policies.values(),
                key=lambda p: p.priority,
                reverse=True,
            )

        matched_allow = False
        matched_policy_id = ""

        for policy in policies:
            if policy.matches(
                principal=principal,
                resource=resource,
                action=action,
                namespace=namespace,
                trust_domain=trust_domain,
                roles=roles,
            ):
                if policy.effect == PolicyEffect.DENY:
                    with self._lock:
                        self._deny_count += 1
                    return {
                        "allowed": False,
                        "reason": "denied_by_policy",
                        "policy_id": policy.policy_id,
                    }
                elif policy.effect == PolicyEffect.ALLOW:
                    matched_allow = True
                    matched_policy_id = policy.policy_id

        if matched_allow:
            with self._lock:
                self._allow_count += 1
            return {
                "allowed": True,
                "reason": "allowed_by_policy",
                "policy_id": matched_policy_id,
            }

        # Default deny
        with self._lock:
            self._deny_count += 1
        return {
            "allowed": False,
            "reason": "default_deny",
            "policy_id": "",
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy_count": len(self._policies),
                "evaluation_count": self._evaluation_count,
                "allow_count": self._allow_count,
                "deny_count": self._deny_count,
            }
