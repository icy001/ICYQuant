"""
Permission Engine — RBAC integration for autonomous operations.

Connects identity → role → permission → autonomy level → policy → decision
for all autonomous domains.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PermissionEngine:
    """
    Central permission engine connecting RBAC with autonomous control.

    Evaluates whether a given identity/role has permission to perform
    a specific autonomous action at the current autonomy level.
    """

    def __init__(self):
        self._permission_registry: dict[str, Any] = {}
        self._check_count = 0
        self._denial_count = 0

    def register(self, domain: str, handler) -> None:
        """Register a domain-specific permission handler."""
        self._permission_registry[domain] = handler

    async def check(self, context) -> object:
        """Check permissions for a decision context."""
        from .decision_result import DecisionResult

        self._check_count += 1
        scope = getattr(context, "requested_scope", "default")

        handler = self._permission_registry.get(scope)
        if not handler:
            # No specific handler — check default
            handler = self._permission_registry.get("default")

        if handler:
            allowed = await handler.check(context)
            if not allowed:
                self._denial_count += 1
                return DecisionResult.denied(f"Permission denied for scope: {scope}")

        return DecisionResult.allowed_result()

    def stats(self) -> dict:
        return {
            "checks_total": self._check_count,
            "denials_total": self._denial_count,
            "registered_domains": len(self._permission_registry),
        }
