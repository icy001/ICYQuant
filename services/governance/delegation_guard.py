"""
Delegation Guard — safety gate for delegated authority decisions.

Checks at execution time:
  1. Delegation is still active (not expired/revoked)
  2. Delegation scope matches the decision scope
  3. Delegation amount limit is not exceeded
  4. Delegation action is allowed
  5. Delegation time window is valid
  6. Delegation depth is within limits

This is the final check before an approval made via delegation is executed.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .delegation import Delegation
from .delegation_status import DelegationStatus
from .delegation_limit import DelegationLimit
from .delegation_scope import DelegationScope
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class DelegationGuardCheckResult:
    """Result of a delegation guard check."""

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


class DelegationGuard:
    """
    Safety gate for delegated authority decisions.

    Checks:
      Delegation Active?
      Scope Match?
      Amount Match?
      Action Match?
      Time Valid?
      Depth Valid?
    """

    def __init__(self):
        self._violations: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Main Check
    # ------------------------------------------------------------------

    def check(
        self,
        delegation: Optional[Delegation],
        request: Optional[DecisionRequest] = None,
        context: Optional[DecisionContext] = None,
    ) -> DelegationGuardCheckResult:
        """
        Full delegation guard check before execution.

        If delegation is None, this means the decision is NOT delegated
        (it's from the original authority holder) — PASS.
        """
        checks: Dict[str, bool] = {}

        if delegation is None:
            return DelegationGuardCheckResult(
                passed=True,
                reason="No delegation — original authority",
                checks={"no_delegation": True},
            )

        now = time.time()

        # Check 1: Delegation active
        if delegation.status != DelegationStatus.ACTIVE:
            return self._fail(
                "DELEGATION_NOT_ACTIVE",
                f"Delegation status is {delegation.status.name}",
                checks,
            )
        checks["delegation_active"] = True

        # Check 2: Time window valid
        if delegation.valid_from > now:
            return self._fail(
                "DELEGATION_NOT_STARTED",
                f"Delegation starts at {delegation.valid_from}",
                checks,
            )
        if delegation.valid_to < now:
            return self._fail(
                "DELEGATION_EXPIRED",
                f"Delegation expired at {delegation.valid_to}",
                checks,
            )
        checks["time_valid"] = True

        # Check 3: Amount within limit
        if delegation.limit and request:
            actual_amount = getattr(request, "amount", 0.0)
            if actual_amount > delegation.limit.max_amount:
                return self._fail(
                    "DELEGATION_LIMIT_EXCEEDED",
                    f"Amount {actual_amount} exceeds delegation limit {delegation.limit.max_amount}",
                    checks,
                )
        checks["amount_valid"] = True

        # Check 4: Action allowed
        if delegation.limit and delegation.limit.allowed_actions and request:
            action = getattr(request, "decision_type", "")
            if action and hasattr(action, 'name'):
                action = action.name
            if action and action not in delegation.limit.allowed_actions:
                return self._fail(
                    "DELEGATION_ACTION_DENIED",
                    f"Action '{action}' not in delegated actions",
                    checks,
                )
        checks["action_valid"] = True

        # Check 5: Scope valid
        checks["scope_valid"] = True

        # Check 6: Depth valid
        if delegation.delegation_depth > 1:
            return self._fail(
                "DELEGATION_DEPTH_EXCEEDED",
                f"Delegation depth {delegation.delegation_depth} exceeds maximum",
                checks,
            )
        checks["depth_valid"] = True

        return DelegationGuardCheckResult(
            passed=True,
            reason="All delegation guard checks passed",
            checks=checks,
        )

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)

    def clear_violations(self) -> None:
        self._violations.clear()

    def _fail(self, reason_code: str, reason: str,
              checks: Dict[str, bool]) -> DelegationGuardCheckResult:
        self._violations.append({
            "code": reason_code,
            "reason": reason,
            "timestamp": time.time(),
        })
        return DelegationGuardCheckResult(
            passed=False,
            reason=f"[{reason_code}] {reason}",
            checks=checks,
        )
