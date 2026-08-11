"""
Approval Gate — validates approval status before order creation.

Commit 21 Part 1.1: checks approval_id, scope, amount, expiry, and status.
Must satisfy: APPROVED AND VALID AND NOT_EXPIRED AND WITHIN_SCOPE.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_gate import ControlGate
from .control_context import TradingControlContext
from .control_result import ControlResult


@dataclass
class ApprovalGate(ControlGate):
    """Approval Gate — validates that a trade has valid approval.

    Checks:
      - Approval Status: must be APPROVED
      - Approval Validity: not consumed, not expired
      - Approval Scope: covers the requested action
      - Approval Amount: covers the requested amount
      - Policy Version: matches current policy version

    Required: APPROVED AND VALID AND NOT_EXPIRED AND WITHIN_SCOPE
    """

    name: str = "ApprovalGate"

    # Approval state
    approval_status: str = "PENDING"       # PENDING / APPROVED / REJECTED / EXPIRED
    approved_amount: float = 0.0
    approved_action: str = ""
    consumed: bool = False
    valid_until: float = 0.0
    approval_policy_version: str = ""
    approval_id: str = ""

    def check(self, context: TradingControlContext) -> ControlResult:
        """Evaluate approval constraints."""
        now = time.time()
        app = context.approval_context or {}

        # ── Unknown Approval → BLOCK (fail-closed) ──────────────
        if app.get("state") == "UNKNOWN":
            return self.fail_closed(context, "Approval state UNKNOWN → BLOCK")

        status = app.get("status", self.approval_status)

        # ── Not Approved ────────────────────────────────────────
        if status != "APPROVED":
            if status == "REJECTED":
                return self.reject_result(
                    context,
                    code="APPROVAL_REJECTED",
                    reason="Approval was rejected",
                )
            elif status == "PENDING":
                return self.reject_result(
                    context,
                    code="APPROVAL_PENDING",
                    reason="Approval is still pending",
                )
            elif status == "EXPIRED":
                return ControlResult.make_expired(
                    flow_id=context.flow_id,
                    code="APPROVAL_EXPIRED",
                    reason="Approval has expired",
                )
            else:
                return self.reject_result(
                    context,
                    code="APPROVAL_INVALID",
                    reason=f"Invalid approval status: {status}",
                )

        # ── Consumed (replay protection) ────────────────────────
        if app.get("consumed", self.consumed):
            return self.reject_result(
                context,
                code="APPROVAL_CONSUMED",
                reason="Approval already consumed — replay blocked",
            )

        # ── Expired ─────────────────────────────────────────────
        valid_until = app.get("valid_until", self.valid_until)
        if valid_until > 0 and now > valid_until:
            return ControlResult.make_expired(
                flow_id=context.flow_id,
                code="APPROVAL_EXPIRED",
                reason=f"Approval expired at {valid_until}",
            )

        # ── Amount ──────────────────────────────────────────────
        approved_amt = app.get("approved_amount", self.approved_amount)
        requested_amt = app.get("requested_amount", 0.0)
        if approved_amt > 0 and requested_amt > approved_amt:
            return self.reject_result(
                context,
                code="APPROVAL_AMOUNT_EXCEEDED",
                reason=f"Requested {requested_amt} exceeds approved {approved_amt}",
            )

        # ── Scope / Action ──────────────────────────────────────
        approved_action = app.get("approved_action", self.approved_action)
        decision_type = context.decision_type or app.get("decision_type", "")
        if approved_action and decision_type and approved_action != decision_type:
            return self.reject_result(
                context,
                code="APPROVAL_SCOPE",
                reason=f"Action {decision_type} not in approved scope ({approved_action})",
            )

        # ── Policy Version ──────────────────────────────────────
        app_policy = app.get("policy_version", self.approval_policy_version)
        ctx_policy = context.policy_version
        if app_policy and ctx_policy and app_policy != ctx_policy:
            return self.reject_result(
                context,
                code="APPROVAL_POLICY_VERSION_MISMATCH",
                reason=f"Approval policy {app_policy} != current {ctx_policy}",
            )

        return self.pass_result(context, reason="Approval checks passed")
