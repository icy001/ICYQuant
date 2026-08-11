"""
Authority Gate — validates actor authority before trade proceeds.

Commit 21 Part 1.1: checks authority, scope, limit, expiry, delegation,
and revocation. Fails-closed: UNKNOWN authority → BLOCK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_gate import ControlGate
from .control_context import TradingControlContext
from .control_result import ControlResult


@dataclass
class AuthorityGate(ControlGate):
    """Authority Gate — validates actor authority.

    Checks:
      - Authority existence: does the actor have authority?
      - Scope: does the authority cover this decision type?
      - Limit: is the amount within authority limits?
      - Expiry: has the authority expired?
      - Delegation: is delegation valid?
      - Revocation: has authority been revoked?
    """

    name: str = "AuthorityGate"

    # Authority state
    has_authority: bool = True
    max_amount: float = float("inf")
    max_risk: float = float("inf")
    allowed_actions: list = field(default_factory=list)
    expired: bool = False
    revoked: bool = False
    delegation_active: bool = False
    delegation_max_amount: float = float("inf")

    def check(self, context: TradingControlContext) -> ControlResult:
        """Evaluate authority constraints."""
        auth = context.authority_context or {}

        # ── Unknown Authority → BLOCK (fail-closed) ─────────────
        if auth.get("state") == "UNKNOWN":
            return self.fail_closed(context, "Authority state UNKNOWN → BLOCK")

        # ── No Authority ────────────────────────────────────────
        if not self.has_authority and not auth.get("authorized"):
            return self.reject_result(
                context,
                code="AUTHORITY_DENIED",
                reason=f"No authority for actor {context.actor}",
            )

        # ── Revoked ─────────────────────────────────────────────
        if self.revoked or auth.get("revoked"):
            return self.reject_result(
                context,
                code="AUTHORITY_REVOKED",
                reason="Authority has been revoked",
            )

        # ── Expired ─────────────────────────────────────────────
        if self.expired or auth.get("expired"):
            return ControlResult.make_expired(
                flow_id=context.flow_id,
                code="AUTHORITY_EXPIRED",
                reason="Authority has expired",
            )

        # ── Scope / Allowed Actions ─────────────────────────────
        if self.allowed_actions:
            decision_type = context.decision_type or auth.get("decision_type", "")
            if decision_type not in self.allowed_actions and "*" not in self.allowed_actions:
                return self.reject_result(
                    context,
                    code="AUTHORITY_SCOPE",
                    reason=f"Action {decision_type} not in allowed scope",
                )

        # ── Amount Limit ────────────────────────────────────────
        requested_amount = auth.get("requested_amount", 0.0)
        effective_max = self.max_amount
        if self.delegation_active:
            effective_max = min(effective_max, self.delegation_max_amount)

        if requested_amount > effective_max:
            return self.reject_result(
                context,
                code="AUTHORITY_LIMIT_EXCEEDED",
                reason=f"Requested {requested_amount} exceeds authority limit {effective_max}",
            )

        # ── Risk Limit ──────────────────────────────────────────
        requested_risk = auth.get("additional_risk", auth.get("requested_risk", 0.0))
        if requested_risk > self.max_risk:
            return self.reject_result(
                context,
                code="AUTHORITY_RISK_EXCEEDED",
                reason=f"Requested risk {requested_risk} exceeds max {self.max_risk}",
            )

        return self.pass_result(context, reason="Authority checks passed")
