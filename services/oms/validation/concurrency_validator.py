"""ConcurrencyValidator — validates optimistic concurrency for commands."""
from __future__ import annotations

from services.oms.results.command_errors import ConcurrencyConflictError


class ConcurrencyValidator:
    """Validates optimistic concurrency control.

    Commands carry an expected_version. If the aggregate's actual
    version doesn't match, the command is rejected with
    CONCURRENCY_CONFLICT.
    """

    @staticmethod
    def validate(command_id: str, order_id: str,
                 expected_version: int,
                 actual_version: int) -> None:
        """Validate that expected_version matches actual_version.

        Raises ConcurrencyConflictError if mismatch.
        If expected_version is None or 0, the check is skipped (no
        optimistic locking requested).
        """
        if expected_version and expected_version != actual_version:
            raise ConcurrencyConflictError(
                command_id, order_id,
                expected_version=expected_version,
                actual_version=actual_version,
            )

    @staticmethod
    def needs_check(expected_version: int) -> bool:
        """Whether a concurrency check is needed."""
        return bool(expected_version)
