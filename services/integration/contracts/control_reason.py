"""Structured reason codes for every control decision.

Every control outcome must carry a specific reason code
so that audit, metrics, and alerting systems can consume them.
"""

from __future__ import annotations

from enum import Enum, auto


class ReasonCode(Enum):
    """Machine-readable reason codes for control gate decisions."""

    # ── Pass reasons ──
    RISK_LIMIT_OK = auto()
    RISK_CHECK_PASSED = auto()
    POLICY_COMPLIANT = auto()
    AUTHORITY_VALID = auto()
    APPROVAL_VALID = auto()
    APPROVAL_GRANTED = auto()
    ORDER_ADMITTED = auto()

    # ── Risk reject reasons ──
    RISK_EXPOSURE_BREACH = auto()
    RISK_LEVERAGE_BREACH = auto()
    RISK_CONCENTRATION_BREACH = auto()
    RISK_VAR_BREACH = auto()
    RISK_LIMIT_EXCEEDED = auto()
    RISK_UNKNOWN = auto()

    # ── Governance reject reasons ──
    GOVERNANCE_FROZEN = auto()
    GOVERNANCE_SUSPENDED = auto()
    POLICY_VERSION_MISMATCH = auto()
    POLICY_VIOLATION = auto()
    GOVERNANCE_UNKNOWN = auto()

    # ── Authority reject reasons ──
    AUTHORITY_EXPIRED = auto()
    AUTHORITY_LIMIT_EXCEEDED = auto()
    AUTHORITY_SCOPE_MISMATCH = auto()
    AUTHORITY_REVOKED = auto()
    AUTHORITY_UNKNOWN = auto()

    # ── Approval reject reasons ──
    APPROVAL_EXPIRED = auto()
    APPROVAL_SCOPE_MISMATCH = auto()
    APPROVAL_LIMIT_EXCEEDED = auto()
    APPROVAL_REVOKED = auto()
    APPROVAL_UNKNOWN = auto()

    # ── Contract-level reasons ──
    CONTRACT_EXPIRED = auto()
    CONTRACT_INVALID = auto()
    CONTRACT_REPLAY = auto()
    CONTEXT_INTEGRITY_ERROR = auto()
    CONSTRAINT_CONFLICT = auto()
    UNKNOWN_ERROR = auto()

    @property
    def label(self) -> str:
        return REASON_CODE_LABELS.get(self, "UNKNOWN")

    @property
    def is_pass(self) -> bool:
        _pass_codes = {
            ReasonCode.RISK_LIMIT_OK,
            ReasonCode.RISK_CHECK_PASSED,
            ReasonCode.POLICY_COMPLIANT,
            ReasonCode.AUTHORITY_VALID,
            ReasonCode.APPROVAL_VALID,
            ReasonCode.APPROVAL_GRANTED,
            ReasonCode.ORDER_ADMITTED,
        }
        return self in _pass_codes

    @property
    def domain(self) -> str:
        """Return the domain this reason code belongs to."""
        name = self.name
        if name.startswith("RISK_"):
            return "risk"
        if name.startswith("GOVERNANCE_"):
            return "governance"
        if name.startswith("AUTHORITY_"):
            return "authority"
        if name.startswith("APPROVAL_"):
            return "approval"
        if name.startswith("CONTRACT_") or name.startswith("CONTEXT_") or name.startswith("CONSTRAINT_"):
            return "contract"
        if name.startswith("POLICY_"):
            return "governance"
        if name.startswith("ORDER_"):
            return "admission"
        return "system"


REASON_CODE_LABELS: dict[ReasonCode, str] = {
    # Pass
    ReasonCode.RISK_LIMIT_OK: "Risk limits within acceptable range",
    ReasonCode.RISK_CHECK_PASSED: "All risk checks passed",
    ReasonCode.POLICY_COMPLIANT: "Policy compliance verified",
    ReasonCode.AUTHORITY_VALID: "Authority is valid",
    ReasonCode.APPROVAL_VALID: "Approval is valid",
    ReasonCode.APPROVAL_GRANTED: "Approval granted",
    ReasonCode.ORDER_ADMITTED: "Order admitted",
    # Risk
    ReasonCode.RISK_EXPOSURE_BREACH: "Portfolio exposure exceeds limit",
    ReasonCode.RISK_LEVERAGE_BREACH: "Leverage exceeds limit",
    ReasonCode.RISK_CONCENTRATION_BREACH: "Concentration exceeds limit",
    ReasonCode.RISK_VAR_BREACH: "VaR exceeds limit",
    ReasonCode.RISK_LIMIT_EXCEEDED: "Risk limit exceeded",
    ReasonCode.RISK_UNKNOWN: "Risk assessment unavailable",
    # Governance
    ReasonCode.GOVERNANCE_FROZEN: "Portfolio/account is frozen",
    ReasonCode.GOVERNANCE_SUSPENDED: "Trading is suspended",
    ReasonCode.POLICY_VERSION_MISMATCH: "Policy version mismatch",
    ReasonCode.POLICY_VIOLATION: "Policy violation detected",
    ReasonCode.GOVERNANCE_UNKNOWN: "Governance state unknown",
    # Authority
    ReasonCode.AUTHORITY_EXPIRED: "Authority has expired",
    ReasonCode.AUTHORITY_LIMIT_EXCEEDED: "Authority limit exceeded",
    ReasonCode.AUTHORITY_SCOPE_MISMATCH: "Authority scope mismatch",
    ReasonCode.AUTHORITY_REVOKED: "Authority has been revoked",
    ReasonCode.AUTHORITY_UNKNOWN: "Authority state unknown",
    # Approval
    ReasonCode.APPROVAL_EXPIRED: "Approval has expired",
    ReasonCode.APPROVAL_SCOPE_MISMATCH: "Approval scope mismatch",
    ReasonCode.APPROVAL_LIMIT_EXCEEDED: "Approval limit exceeded",
    ReasonCode.APPROVAL_REVOKED: "Approval has been revoked",
    ReasonCode.APPROVAL_UNKNOWN: "Approval state unknown",
    # Contract
    ReasonCode.CONTRACT_EXPIRED: "Contract has expired",
    ReasonCode.CONTRACT_INVALID: "Contract validation failed",
    ReasonCode.CONTRACT_REPLAY: "Contract replay detected",
    ReasonCode.CONTEXT_INTEGRITY_ERROR: "Context integrity violation",
    ReasonCode.CONSTRAINT_CONFLICT: "Constraint conflict detected",
    ReasonCode.UNKNOWN_ERROR: "Unknown error",
}
