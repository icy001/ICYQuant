"""
Authority Adapter — bridges Authority Engine into the integration control flow.

Commit 21 Part 1.1: translates authority evaluation results into a
normalized authority_context consumed by AuthorityGate.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AuthorityAdapter:
    """Bridges Authority Engine to integration layer.

    Domain (Authority) → Adapter → Integration Layer (AuthorityGate)
    """

    @staticmethod
    def build_authority_context(
        authorized: bool = True,
        max_amount: float = float("inf"),
        max_risk: float = float("inf"),
        allowed_actions: Optional[list] = None,
        expired: bool = False,
        revoked: bool = False,
        delegation_active: bool = False,
        delegation_max_amount: float = float("inf"),
        authority_id: str = "",
        autonomy_level: str = "",
        review_required: bool = False,
        approval_required: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Build an authority context dict for integration gates."""
        return {
            "authorized": authorized,
            "max_amount": max_amount,
            "max_risk": max_risk,
            "allowed_actions": allowed_actions or [],
            "expired": expired,
            "revoked": revoked,
            "delegation_active": delegation_active,
            "delegation_max_amount": delegation_max_amount,
            "authority_id": authority_id,
            "autonomy_level": autonomy_level,
            "review_required": review_required,
            "approval_required": approval_required,
            **kwargs,
        }

    @staticmethod
    def from_authority_result(auth_result: Any) -> Dict[str, Any]:
        """Convert AuthorityEvaluationResult to integration context."""
        return {
            "authorized": getattr(auth_result, "authorized", False),
            "max_amount": getattr(auth_result, "max_amount_allowed", float("inf")),
            "max_risk": getattr(auth_result, "max_risk_allowed", float("inf")),
            "reason": getattr(auth_result, "reason", ""),
            "review_required": getattr(auth_result, "review_required", False),
            "autonomy_level": getattr(getattr(auth_result, "level", None), "name", ""),
            "detail": getattr(auth_result, "detail", {}),
            "state": "AUTHORIZED" if getattr(auth_result, "authorized", False) else "DENIED",
        }

    @staticmethod
    def from_authority_grant(grant: Any) -> Dict[str, Any]:
        """Convert an AuthorityGrant to integration context."""
        return {
            "authorized": True,
            "max_amount": getattr(grant, "max_amount", float("inf")),
            "max_risk": getattr(grant, "max_risk", float("inf")),
            "allowed_actions": getattr(grant, "allowed_actions", []),
            "expired": getattr(grant, "expired", getattr(grant, "is_expired", lambda: False)(), False),
            "revoked": getattr(grant, "revoked", False),
            "authority_id": getattr(grant, "grant_id", ""),
            "state": "VALID",
        }
