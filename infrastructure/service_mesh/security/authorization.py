"""Authorization for ICYQuant Service Mesh.

Provides ``AuthorizationManager`` for policy-based access control
using identity, namespace, trust domain, and role information.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .principal import Principal
from .policy_engine import PolicyEngine

logger = logging.getLogger(__name__)


class AuthzResult:
    """Result of authorization check."""

    def __init__(self, allowed: bool, reason: str = "", policy_id: str = "") -> None:
        self.allowed = allowed
        self.reason = reason
        self.policy_id = policy_id
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "timestamp": self.timestamp.isoformat(),
        }


class AuthorizationManager:
    """Manages authorization decisions."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None) -> None:
        self._lock = threading.RLock()
        self._policy_engine = policy_engine or PolicyEngine()
        self._check_count = 0
        self._allow_count = 0
        self._deny_count = 0

    async def authorize(
        self,
        principal: Principal,
        resource: str,
        action: str = "access",
    ) -> AuthzResult:
        """Check if a principal is authorized for a resource/action."""
        with self._lock:
            self._check_count += 1

        if not principal.is_authenticated:
            with self._lock:
                self._deny_count += 1
            return AuthzResult(allowed=False, reason="not_authenticated")

        result = self._policy_engine.evaluate(
            principal=principal.spiffe_id,
            resource=resource,
            action=action,
            namespace=principal.namespace,
            trust_domain=principal.trust_domain,
            roles=principal.roles,
        )

        with self._lock:
            if result["allowed"]:
                self._allow_count += 1
            else:
                self._deny_count += 1

        return AuthzResult(
            allowed=result["allowed"],
            reason=result["reason"],
            policy_id=result.get("policy_id", ""),
        )

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "check_count": self._check_count,
                "allow_count": self._allow_count,
                "deny_count": self._deny_count,
                "policy_engine": self._policy_engine.get_stats(),
            }
