"""CertificateStatus — lifecycle state for PreTradeControlCertificate.

State transitions:
    ISSUED → VALID → USED
    VALID → EXPIRED
    VALID → REVOKED
    ISSUED → INVALID  (integrity failure)
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Dict, Set


class CertificateStatus(Enum):
    """Lifecycle states for a Pre-Trade Control Certificate."""

    ISSUED = auto()
    VALID = auto()
    USED = auto()
    EXPIRED = auto()
    REVOKED = auto()
    INVALID = auto()

    @property
    def label(self) -> str:
        _labels: Dict[CertificateStatus, str] = {
            CertificateStatus.ISSUED: "Issued",
            CertificateStatus.VALID: "Valid",
            CertificateStatus.USED: "Used",
            CertificateStatus.EXPIRED: "Expired",
            CertificateStatus.REVOKED: "Revoked",
            CertificateStatus.INVALID: "Invalid",
        }
        return _labels.get(self, "UNKNOWN")

    @property
    def is_terminal(self) -> bool:
        """Whether this status is a terminal (non-transitionable) state."""
        return self in {
            CertificateStatus.USED,
            CertificateStatus.EXPIRED,
            CertificateStatus.REVOKED,
            CertificateStatus.INVALID,
        }

    @property
    def is_active(self) -> bool:
        """Whether the certificate is currently usable."""
        return self in {CertificateStatus.ISSUED, CertificateStatus.VALID}


# ── Valid status transitions ──────────────────────────────────

_VALID_TRANSITIONS: Dict[CertificateStatus, Set[CertificateStatus]] = {
    CertificateStatus.ISSUED: {CertificateStatus.VALID, CertificateStatus.INVALID},
    CertificateStatus.VALID: {
        CertificateStatus.USED,
        CertificateStatus.EXPIRED,
        CertificateStatus.REVOKED,
        CertificateStatus.INVALID,
    },
    CertificateStatus.USED: set(),
    CertificateStatus.EXPIRED: set(),
    CertificateStatus.REVOKED: set(),
    CertificateStatus.INVALID: set(),
}


def can_transition(
    from_status: CertificateStatus, to_status: CertificateStatus
) -> bool:
    """Check whether a state transition is valid."""
    return to_status in _VALID_TRANSITIONS.get(from_status, set())


def valid_transitions_from(
    from_status: CertificateStatus,
) -> Set[CertificateStatus]:
    """Return the set of valid next states for *from_status*."""
    return _VALID_TRANSITIONS.get(from_status, set())
