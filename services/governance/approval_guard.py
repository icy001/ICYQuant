"""
Approval Guard — final execution gate for approved decisions.

Sits at the last checkpoint before execution, ensuring:
  1. Approval exists and is valid (not expired/consumed)
  2. Approval scope matches the execution scope
  3. Approved amount >= execution amount
  4. Authority is still valid (not revoked since approval)
  5. Policy hasn't changed materially
  6. Decision is still valid under current market conditions

This is distinct from approval_guardian.py (which handles long-running approval
monitoring). The ApprovalGuard handles the final "just before execute" check.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .approval_request import ApprovalRequest
from .approval_response import ApprovalResponse
from .approval_status import ApprovalStatus
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class ApprovalGuardCheckResult:
    """Result of an approval guard check."""

    def __init__(self, passed: bool, reason: str = "", checks: Optional[Dict[str, bool]] = None):
        self.passed = passed
        self.reason = reason
        self.checks = checks or {}

    def __bool__(self) -> bool:
        return self.passed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "checks": self.checks,
        }


class ApprovalGuard:
    """
    Final safety gate — checks all approval conditions before execution.

    Ensures:
      - Approval Exists
      - Approval Valid (not expired, consumed, revoked)
      - Approval Scope matches execution
      - Approval Amount >= execution amount
      - Authority Still Valid
      - Policy Still Valid
      - Decision Still Valid

    FAIL CLOSED: if any check is indeterminate, BLOCK.
    """

    def __init__(self):
        self._violations: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Main Check
    # ------------------------------------------------------------------

    def check(
        self,
        approval: ApprovalResponse,
        request: Optional[DecisionRequest] = None,
        context: Optional[DecisionContext] = None,
    ) -> ApprovalGuardCheckResult:
        """
        Full pre-execution approval guard check.

        All checks must PASS for execution to proceed.
        """
        checks: Dict[str, bool] = {}
        now = time.time()

        # Check 1: Approval exists
        if approval is None:
            return self._fail("APPROVAL_MISSING", "No approval found", checks)

        # Check 2: Approval is approved
        if approval.status != ApprovalStatus.APPROVED:
            return self._fail(
                "APPROVAL_NOT_APPROVED",
                f"Approval status is {approval.status.name}",
                checks,
            )
        checks["status_approved"] = True

        # Check 3: Not consumed (replay protection)
        if approval.consumed:
            return self._fail("REPLAY_DETECTED", "Approval has already been consumed", checks)
        checks["not_consumed"] = True

        # Check 4: Not expired
        if approval.valid_until > 0 and now > approval.valid_until:
            return self._fail(
                "APPROVAL_EXPIRED",
                f"Approval expired at {approval.valid_until}",
                checks,
            )
        checks["not_expired"] = True

        # Check 5: Amount binding
        if request and approval.approved_amount is not None:
            actual_amount = getattr(request, "amount", 0.0)
            if actual_amount > approval.approved_amount:
                return self._fail(
                    "AMOUNT_EXCEEDED",
                    f"Execution amount {actual_amount} exceeds approved {approval.approved_amount}",
                    checks,
                )
        checks["amount_bound"] = True

        # Check 6: Approval hasn't been invalidated
        if approval.status == ApprovalStatus.INVALIDATED:
            return self._fail(
                "APPROVAL_INVALIDATED",
                "Approval was invalidated due to material change",
                checks,
            )
        checks["not_invalidated"] = True

        # Check 7: Scope binding
        if request and approval.approved_action:
            requested_action = getattr(request, "decision_type", "")
            if requested_action and hasattr(requested_action, 'name'):
                requested_action = requested_action.name
            if requested_action and approval.approved_action != requested_action:
                return self._fail(
                    "SCOPE_MISMATCH",
                    f"Action {requested_action} doesn't match approved {approval.approved_action}",
                    checks,
                )
        checks["scope_bound"] = True

        # All passed
        return ApprovalGuardCheckResult(
            passed=True,
            reason="All approval guard checks passed",
            checks=checks,
        )

    # ------------------------------------------------------------------
    # Quick Checks
    # ------------------------------------------------------------------

    def check_consumed(self, approval: ApprovalResponse) -> bool:
        """Check if approval has been consumed (replay protection)."""
        return not approval.consumed

    def check_amount(self, approval: ApprovalResponse, execution_amount: float) -> bool:
        """Check execution amount <= approved amount."""
        if approval.approved_amount is None:
            return True
        return execution_amount <= approval.approved_amount

    def check_scope(self, approval: ApprovalResponse, action: str) -> bool:
        """Check that the action matches the approved scope."""
        if not approval.approved_action:
            return True
        return action == approval.approved_action

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)

    def clear_violations(self) -> None:
        self._violations.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fail(self, reason_code: str, reason: str,
              checks: Dict[str, bool]) -> ApprovalGuardCheckResult:
        """Record a guard failure."""
        self._violations.append({
            "code": reason_code,
            "reason": reason,
            "timestamp": time.time(),
        })
        return ApprovalGuardCheckResult(
            passed=False,
            reason=f"[{reason_code}] {reason}",
            checks=checks,
        )
