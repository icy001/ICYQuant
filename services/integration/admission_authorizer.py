"""AdmissionAuthorizer — re-verifies governance, authority, and approval at the boundary.

This is the final safety checkpoint. Even if upstream gates passed,
the admission boundary re-validates:
- Governance state (FROZEN blocks all new orders)
- Authority limits and expiry
- Approval status, scope, and expiry
- Policy version consistency (policy version lock)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .admission_request import AdmissionRequest
from .admission_decision import AdmissionCheckResult
from .admission_policy import AdmissionPolicy


@dataclass
class AuthorizationReport:
    """Result of the authorization phase."""
    authorized: bool = True
    checks: List[AdmissionCheckResult] = field(default_factory=list)

    def add_check(self, check: AdmissionCheckResult) -> None:
        self.checks.append(check)
        if not check.passed:
            self.authorized = False


@dataclass
class AdmissionAuthorizer:
    """Re-verifies all upstream authorizations at the admission boundary.

    Key principle: this is a final safety checkpoint, not a message forwarder.
    Even if upstream passed, this boundary independently re-validates.
    """

    policy: AdmissionPolicy = field(default_factory=AdmissionPolicy.standard)

    def authorize(self, request: AdmissionRequest) -> AuthorizationReport:
        """Run all authorization checks."""
        report = AuthorizationReport()

        if self.policy.governance_check_required:
            report.add_check(self._check_governance(request))

        if self.policy.authority_check_required:
            report.add_check(self._check_authority(request))

        if self.policy.approval_check_required:
            report.add_check(self._check_approval(request))

        if self.policy.policy_version_lock:
            report.add_check(self._check_policy_version(request))

        return report

    def _check_governance(self, request: AdmissionRequest) -> AdmissionCheckResult:
        """Re-check governance state at admission boundary.

        FROZEN or EMERGENCY governance state blocks new orders even if
        upstream previously passed.
        """
        state = (request.governance_state or "NORMAL").upper()

        if state == "FROZEN":
            return AdmissionCheckResult(
                name="governance",
                passed=False,
                code="GOVERNANCE_FROZEN",
                message="Governance is FROZEN — new orders blocked",
                evidence={"governance_state": state},
            )

        if state == "EMERGENCY" and not request.is_emergency:
            return AdmissionCheckResult(
                name="governance",
                passed=False,
                code="GOVERNANCE_EMERGENCY",
                message="Governance is in EMERGENCY mode — only emergency orders allowed",
                evidence={"governance_state": state},
            )

        return AdmissionCheckResult(
            name="governance",
            passed=True,
            code="GOVERNANCE_OK",
            message=f"Governance state is {state}",
            evidence={"governance_state": state},
        )

    def _check_authority(self, request: AdmissionRequest) -> AdmissionCheckResult:
        """Re-validate authority at admission boundary.

        Checks: not revoked, not expired, within limit.
        """
        if request.authority_revoked:
            return AdmissionCheckResult(
                name="authority",
                passed=False,
                code="AUTHORITY_REVOKED",
                message="Authority has been revoked",
                evidence={"authority_id": request.authority_id},
            )

        if request.authority_expiry is not None and time.time() > request.authority_expiry:
            return AdmissionCheckResult(
                name="authority",
                passed=False,
                code="AUTHORITY_EXPIRED",
                message=f"Authority expired at {request.authority_expiry}",
                evidence={
                    "authority_id": request.authority_id,
                    "authority_expiry": request.authority_expiry,
                },
            )

        # Check authority limit against order notional
        if request.authority_limit is not None and request.intent is not None:
            notional = request.intent.notional
            if notional > request.authority_limit:
                return AdmissionCheckResult(
                    name="authority",
                    passed=False,
                    code="AUTHORITY_LIMIT_EXCEEDED",
                    message=f"Order notional {notional} exceeds authority limit {request.authority_limit}",
                    evidence={
                        "authority_id": request.authority_id,
                        "authority_limit": request.authority_limit,
                        "order_notional": notional,
                    },
                )

        return AdmissionCheckResult(
            name="authority",
            passed=True,
            code="AUTHORITY_VALID",
            message="Authority check passed",
            evidence={
                "authority_id": request.authority_id,
                "authority_limit": request.authority_limit,
            },
        )

    def _check_approval(self, request: AdmissionRequest) -> AdmissionCheckResult:
        """Re-validate approval at admission boundary.

        Checks: status is APPROVED, not expired, within scope.
        """
        if request.approval_status.upper() != "APPROVED":
            return AdmissionCheckResult(
                name="approval",
                passed=False,
                code="APPROVAL_NOT_APPROVED",
                message=f"Approval status is {request.approval_status}, not APPROVED",
                evidence={"approval_id": request.approval_id, "status": request.approval_status},
            )

        if request.approval_expiry is not None and time.time() > request.approval_expiry:
            return AdmissionCheckResult(
                name="approval",
                passed=False,
                code="APPROVAL_EXPIRED",
                message=f"Approval expired at {request.approval_expiry}",
                evidence={
                    "approval_id": request.approval_id,
                    "approval_expiry": request.approval_expiry,
                },
            )

        # Check approval amount against order notional
        if request.approval_amount is not None and request.intent is not None:
            notional = request.intent.notional
            if notional > request.approval_amount:
                return AdmissionCheckResult(
                    name="approval",
                    passed=False,
                    code="APPROVAL_AMOUNT_EXCEEDED",
                    message=f"Order notional {notional} exceeds approved amount {request.approval_amount}",
                    evidence={
                        "approval_id": request.approval_id,
                        "approved_amount": request.approval_amount,
                        "order_notional": notional,
                    },
                )

        return AdmissionCheckResult(
            name="approval",
            passed=True,
            code="APPROVAL_VALID",
            message="Approval check passed",
            evidence={
                "approval_id": request.approval_id,
                "approval_status": request.approval_status,
            },
        )

    def _check_policy_version(self, request: AdmissionRequest) -> AdmissionCheckResult:
        """Check that Approval's policy version matches current system policy version.

        If approval was granted under POLICY-v7 but the current policy is v8,
        the order must be re-validated or blocked.
        """
        if not request.approval_policy_version or not request.policy_version:
            # No version info to compare — pass with warning
            return AdmissionCheckResult(
                name="policy_version",
                passed=True,
                code="POLICY_VERSION_UNVERIFIED",
                message="Policy version not available for comparison",
            )

        if request.approval_policy_version != request.policy_version:
            return AdmissionCheckResult(
                name="policy_version",
                passed=False,
                code="POLICY_VERSION_MISMATCH",
                message=f"Approval policy version {request.approval_policy_version} "
                        f"does not match current policy {request.policy_version}",
                evidence={
                    "approval_policy_version": request.approval_policy_version,
                    "current_policy_version": request.policy_version,
                },
            )

        return AdmissionCheckResult(
            name="policy_version",
            passed=True,
            code="POLICY_VERSION_MATCH",
            message=f"Policy version {request.policy_version} matches",
        )

    def __repr__(self) -> str:
        return f"AdmissionAuthorizer(policy={self.policy.level.label})"
