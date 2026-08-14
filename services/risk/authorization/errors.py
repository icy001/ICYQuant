"""Unified error model for the risk authorization boundary.

Internal components raise granular exceptions / return machine-readable
violations; the integration boundary maps them onto a small, stable set of
:class:`AuthorizationErrorCode` values so consumers (starting with the order
request engine in Commit 32) never have to understand dozens of internal
failure modes.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class AuthorizationErrorCode(str, Enum):
    """Stable error codes exposed across the authorization boundary."""

    INVALID_REQUEST = "INVALID_REQUEST"
    RISK_REJECTED = "RISK_REJECTED"
    CERTIFICATE_INVALID = "CERTIFICATE_INVALID"
    CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    QUANTITY_EXCEEDED = "QUANTITY_EXCEEDED"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    INTEGRATION_FAILURE = "INTEGRATION_FAILURE"


class AuthorizationError(Exception):
    """An authorization boundary failure with a stable machine-readable code."""

    def __init__(
        self,
        code: AuthorizationErrorCode,
        message: str,
        *,
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        if self.detail:
            return f"{self.code.value}: {self.message} ({self.detail})"
        return f"{self.code.value}: {self.message}"


#: Granular execution eligibility violations -> stable boundary error codes.
SCOPE_VIOLATIONS = frozenset(
    {
        "INTENT_MISMATCH",
        "STRATEGY_MISMATCH",
        "SESSION_MISMATCH",
        "SIGNAL_MISMATCH",
        "SYMBOL_MISMATCH",
        "SIDE_MISMATCH",
        "CORRELATION_MISMATCH",
    }
)


def map_violation(violation: str) -> AuthorizationErrorCode:
    """Map an internal violation string onto the stable boundary code.

    ``None`` (no violation) is *not* accepted here; callers check eligibility
    before invoking this mapping.
    """
    if violation == "CERTIFICATE_REJECTED":
        return AuthorizationErrorCode.CERTIFICATE_INVALID
    if violation == "CERTIFICATE_EXPIRED":
        return AuthorizationErrorCode.CERTIFICATE_EXPIRED
    if violation == "QUANTITY_EXCEEDS_AUTHORIZATION":
        return AuthorizationErrorCode.QUANTITY_EXCEEDED
    if violation == "POLICY_MISMATCH":
        return AuthorizationErrorCode.POLICY_MISMATCH
    if violation in SCOPE_VIOLATIONS:
        return AuthorizationErrorCode.SCOPE_MISMATCH
    return AuthorizationErrorCode.INTEGRATION_FAILURE
