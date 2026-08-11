"""AdmissionPolicy — configurable policy controlling what checks are required.

Different order types and contexts (standard, emergency) have different
admission requirements. This module defines the policy hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class AdmissionPolicyLevel(Enum):
    """Admission policy strictness level."""
    STANDARD = auto()
    EMERGENCY = auto()

    @property
    def label(self) -> str:
        _labels = {
            AdmissionPolicyLevel.STANDARD: "STANDARD",
            AdmissionPolicyLevel.EMERGENCY: "EMERGENCY",
        }
        return _labels.get(self, "UNKNOWN")


@dataclass
class AdmissionPolicy:
    """Configurable admission policy.

    Defines which checks are required, whether a certificate is needed,
    and whether reservations are mandatory.
    """

    level: AdmissionPolicyLevel = AdmissionPolicyLevel.STANDARD

    # Required checks
    risk_check_required: bool = True
    governance_check_required: bool = True
    authority_check_required: bool = True
    approval_check_required: bool = True

    # Certificate and fingerprint
    certificate_required: bool = True
    fingerprint_required: bool = True

    # Reservation
    reservation_required: bool = True

    # Policy version lock — reject if approval policy version != current
    policy_version_lock: bool = True

    # Deduplication
    deduplication_enabled: bool = True

    # Expiry — max time from admission to order submission
    max_admission_age_seconds: float = 300.0

    @classmethod
    def standard(cls) -> "AdmissionPolicy":
        """Standard institutional admission policy — all checks required."""
        return cls(
            level=AdmissionPolicyLevel.STANDARD,
            risk_check_required=True,
            governance_check_required=True,
            authority_check_required=True,
            approval_check_required=True,
            certificate_required=True,
            fingerprint_required=True,
            reservation_required=True,
            policy_version_lock=True,
            deduplication_enabled=True,
        )

    @classmethod
    def emergency(cls) -> "AdmissionPolicy":
        """Emergency admission policy — reduced checks.

        Allows CANCEL, REDUCE, CLOSE, HEDGE but blocks:
        - NEW_RISK
        - INCREASE_EXPOSURE
        - INCREASE_LEVERAGE
        """
        return cls(
            level=AdmissionPolicyLevel.EMERGENCY,
            risk_check_required=False,
            governance_check_required=False,
            authority_check_required=True,
            approval_check_required=False,
            certificate_required=True,
            fingerprint_required=True,
            reservation_required=False,
            policy_version_lock=False,
            deduplication_enabled=True,
        )

    def is_check_required(self, check_name: str) -> bool:
        """Check if a specific check is required under this policy."""
        checks = {
            "risk": self.risk_check_required,
            "governance": self.governance_check_required,
            "authority": self.authority_check_required,
            "approval": self.approval_check_required,
            "certificate": self.certificate_required,
            "fingerprint": self.fingerprint_required,
            "reservation": self.reservation_required,
        }
        return checks.get(check_name, True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.name,
            "risk_check_required": self.risk_check_required,
            "governance_check_required": self.governance_check_required,
            "authority_check_required": self.authority_check_required,
            "approval_check_required": self.approval_check_required,
            "certificate_required": self.certificate_required,
            "fingerprint_required": self.fingerprint_required,
            "reservation_required": self.reservation_required,
            "policy_version_lock": self.policy_version_lock,
            "deduplication_enabled": self.deduplication_enabled,
            "max_admission_age_seconds": self.max_admission_age_seconds,
        }

    def __repr__(self) -> str:
        return (
            f"AdmissionPolicy(level={self.level.label}, "
            f"checks=[risk={self.risk_check_required}, gov={self.governance_check_required}, "
            f"auth={self.authority_check_required}, apr={self.approval_check_required}])"
        )


@dataclass
class EmergencyAdmissionPolicy:
    """Emergency-specific policy that restricts order types.

    In emergency mode:
    - Allowed: CANCEL, REDUCE, CLOSE, HEDGE
    - Blocked: NEW_RISK, INCREASE_EXPOSURE, INCREASE_LEVERAGE
    """

    allowed_intents: Set[str] = field(
        default_factory=lambda: {"CANCEL", "REDUCE", "CLOSE", "HEDGE"}
    )
    blocked_intents: Set[str] = field(
        default_factory=lambda: {"NEW_RISK", "INCREASE_EXPOSURE", "INCREASE_LEVERAGE"}
    )

    def is_allowed(self, intent_type: str) -> bool:
        """Check if an intent type is allowed under emergency policy."""
        if intent_type in self.blocked_intents:
            return False
        return intent_type in self.allowed_intents

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_intents": list(self.allowed_intents),
            "blocked_intents": list(self.blocked_intents),
        }

    def __repr__(self) -> str:
        return f"EmergencyAdmissionPolicy(allowed={self.allowed_intents})"
