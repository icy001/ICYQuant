"""Command errors — error classes for command processing."""
from __future__ import annotations


class CommandError(Exception):
    """Base error for command processing."""

    def __init__(self, message: str, command_id: str = "",
                 order_id: str = "", code: str = "") -> None:
        super().__init__(message)
        self.message: str = message
        self.command_id: str = command_id
        self.order_id: str = order_id
        self.code: str = code or "COMMAND_ERROR"


class CommandValidationError(CommandError):
    def __init__(self, command_id: str, code: str, message: str,
                 order_id: str = "") -> None:
        super().__init__(message, command_id, order_id, code)


class DuplicateCommandError(CommandError):
    def __init__(self, command_id: str, existing_order_id: str = "") -> None:
        super().__init__(
            f"Duplicate command: {command_id}",
            command_id=command_id,
            order_id=existing_order_id,
            code="DUPLICATE_COMMAND",
        )


class ConcurrencyConflictError(CommandError):
    def __init__(self, command_id: str, order_id: str,
                 expected_version: int, actual_version: int) -> None:
        super().__init__(
            f"Concurrency conflict for {order_id}: "
            f"expected version {expected_version}, "
            f"actual {actual_version}",
            command_id=command_id,
            order_id=order_id,
            code="CONCURRENCY_CONFLICT",
        )
        self.expected_version = expected_version
        self.actual_version = actual_version


class ExecutionIdConflictError(CommandError):
    def __init__(self, command_id: str, execution_id: str,
                 order_id: str = "") -> None:
        super().__init__(
            f"Execution ID conflict: {execution_id} "
            f"already processed with different payload",
            command_id=command_id,
            order_id=order_id,
            code="EXECUTION_ID_CONFLICT",
        )
        self.execution_id = execution_id


class InvalidStateTransitionError(CommandError):
    def __init__(self, command_id: str, order_id: str,
                 current_status: str, attempted_action: str) -> None:
        super().__init__(
            f"Invalid state transition for {order_id}: "
            f"cannot {attempted_action} from {current_status}",
            command_id=command_id,
            order_id=order_id,
            code="INVALID_STATE_TRANSITION",
        )
        self.current_status = current_status
        self.attempted_action = attempted_action


class TerminalStateError(CommandError):
    def __init__(self, command_id: str, order_id: str,
                 terminal_status: str) -> None:
        super().__init__(
            f"Order {order_id} is in terminal state {terminal_status}",
            command_id=command_id,
            order_id=order_id,
            code="TERMINAL_STATE",
        )
        self.terminal_status = terminal_status


class CertificateInvalidError(CommandError):
    def __init__(self, command_id: str, certificate_id: str,
                 reason: str = "") -> None:
        super().__init__(
            f"Certificate {certificate_id} invalid: {reason}",
            command_id=command_id,
            code="CERTIFICATE_INVALID",
        )
        self.certificate_id = certificate_id


class QuantityExceededError(CommandError):
    def __init__(self, command_id: str, order_id: str,
                 requested: float, available: float) -> None:
        super().__init__(
            f"Quantity exceeded for {order_id}: "
            f"requested {requested}, available {available}",
            command_id=command_id,
            order_id=order_id,
            code="QUANTITY_EXCEEDED",
        )
        self.requested = requested
        self.available = available
