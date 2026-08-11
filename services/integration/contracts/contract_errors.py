"""Contract error types for cross-domain control contracts."""

from __future__ import annotations


class ContractError(Exception):
    """Base exception for all contract-related errors."""

    def __init__(self, message: str, code: str = "CONTRACT_ERROR") -> None:
        super().__init__(message)
        self.code = code


class ContractValidationError(ContractError):
    """Contract failed structural or semantic validation."""

    def __init__(self, message: str, field: str = "") -> None:
        super().__init__(message, code="CONTRACT_INVALID")
        self.field = field


class ContractVersionError(ContractError):
    """Contract version mismatch or incompatibility."""

    def __init__(
        self,
        message: str,
        requested_version: str = "",
        supported_versions: list[str] | None = None,
    ) -> None:
        super().__init__(message, code="CONTRACT_VERSION_ERROR")
        self.requested_version = requested_version
        self.supported_versions = supported_versions or []


class ContractExpiredError(ContractError):
    """Contract has exceeded its validity window."""

    def __init__(self, message: str, contract_id: str = "", expires_at: float = 0) -> None:
        super().__init__(message, code="CONTRACT_EXPIRED")
        self.contract_id = contract_id
        self.expires_at = expires_at


class ContractReplayError(ContractError):
    """Duplicate contract submission detected."""

    def __init__(self, message: str, fingerprint: str = "", flow_id: str = "") -> None:
        super().__init__(message, code="REPLAY_DETECTED")
        self.fingerprint = fingerprint
        self.flow_id = flow_id


class ContextIntegrityError(ContractError):
    """Control context integrity violation — immutable fields were modified."""

    def __init__(self, message: str, field: str = "", expected: str = "", actual: str = "") -> None:
        super().__init__(message, code="CONTEXT_INTEGRITY_ERROR")
        self.field = field
        self.expected = expected
        self.actual = actual


class ConstraintConflictError(ContractError):
    """Constraint intersection resulted in an unresolvable conflict (e.g., allow vs deny)."""

    def __init__(
        self,
        message: str,
        constraint_a: str = "",
        constraint_b: str = "",
    ) -> None:
        super().__init__(message, code="CONSTRAINT_CONFLICT")
        self.constraint_a = constraint_a
        self.constraint_b = constraint_b
