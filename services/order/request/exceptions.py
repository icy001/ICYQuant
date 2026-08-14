"""Order request persistence exceptions (Commit 32 Part 1.5).

The service boundary is fail-closed: when the repository cannot persist the
aggregate the operation stops and raises :class:`OrderRequestPersistenceError`
instead of continuing with an inconsistent in-memory state.
"""


class OrderRequestPersistenceError(RuntimeError):
    """Raised when persisting order request state fails.

    This is the fail-closed signal: the caller must not continue the
    operation (no state transition, no event emission) when the repository is
    unavailable.
    """


__all__ = [
    "OrderRequestPersistenceError",
]
