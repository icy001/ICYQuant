"""Control Plane error hierarchy (Commit 29 Part 1.1 §31).

The Control Plane fails closed: any unknown command, unknown target,
invalid state, missing approval, or malformed request results in an
explicit error rather than a silent allow.
"""

from enum import Enum


class ControlPlaneError(Exception):
    """Base error for the production control plane."""


class InvalidControlRequest(ControlPlaneError):
    """A control request is missing critical fields and cannot enter the dispatcher (§32)."""


class CommandNotFound(ControlPlaneError):
    """No handler is registered for the requested resource:action (§9, §41)."""


class TargetNotFound(ControlPlaneError):
    """The requested control target does not exist in the target registry (§34)."""


class CommandConflict(ControlPlaneError):
    """An idempotency key was reused with a different command fingerprint (§29-30)."""


class UnauthorizedControl(ControlPlaneError):
    """Governance rejected the control request (§25, §35 fail closed)."""


class AuthorizationExpired(UnauthorizedControl):
    """An authorization grant is no longer valid because it expired (§12)."""


class InvalidControlState(ControlPlaneError):
    """A control command attempted an illegal lifecycle transition (§15)."""


class ControlExecutionError(ControlPlaneError):
    """A registered handler failed while executing an already-authorised command (§17)."""


class ControlErrorCode(str, Enum):
    """Execution-failure classification (Commit 29 Part 1.3 §44).

    Governance DENY is an AUTHORIZATION failure; a handler crash is an
    EXECUTION failure; they must never be conflated (§43).
    """

    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    APPROVAL_ERROR = "APPROVAL_ERROR"
    DISPATCH_ERROR = "DISPATCH_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RECOVERY_ERROR = "RECOVERY_ERROR"
    CONCURRENCY_ERROR = "CONCURRENCY_ERROR"
    TARGET_ERROR = "TARGET_ERROR"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    REPLAY_REJECTED = "REPLAY_REJECTED"


class VersionConflict(ControlPlaneError):
    """Optimistic concurrency: the expected version is stale (§10, §36-37)."""


class DuplicateCommand(ControlPlaneError):
    """A durable record for this command_id already exists (§35)."""


class CommandRecordNotFound(ControlPlaneError):
    """No durable record exists for the requested command_id (§35)."""


class IdempotencyConflict(ControlPlaneError):
    """An idempotency key was reused with a different command fingerprint (§16-17)."""


class ReplayRejected(ControlPlaneError):
    """A request is outside the replay window or completed replay is disabled (§28-31)."""


class TargetResponseTimeout(ControlPlaneError):
    """The target did not respond within the execution timeout window (§14-15).

    Timeout does not imply failure - the target may already have executed.
    """


def classify_error(exc: Exception) -> ControlErrorCode:
    """Map an exception to a ControlErrorCode (§44)."""
    if isinstance(exc, TargetResponseTimeout):
        return ControlErrorCode.TIMEOUT_ERROR
    if isinstance(exc, (UnauthorizedControl, AuthorizationExpired)):
        return ControlErrorCode.AUTHORIZATION_ERROR
    if isinstance(exc, VersionConflict):
        return ControlErrorCode.CONCURRENCY_ERROR
    if isinstance(exc, TargetNotFound):
        return ControlErrorCode.TARGET_ERROR
    if isinstance(exc, IdempotencyConflict):
        return ControlErrorCode.IDEMPOTENCY_CONFLICT
    if isinstance(exc, ReplayRejected):
        return ControlErrorCode.REPLAY_REJECTED
    if isinstance(exc, (CommandNotFound, InvalidControlRequest, InvalidControlState, CommandConflict)):
        return ControlErrorCode.DISPATCH_ERROR
    return ControlErrorCode.EXECUTION_ERROR
