"""Execution layer errors (Commit 33 Part 1.3)."""

from __future__ import annotations


class ExecutionError(Exception):
    """Base class for execution boundary failures."""


class ExecutionTimeoutError(ExecutionError):
    """The gateway did not answer in time.

    A timeout is NOT a rejection: the venue may have already received the
    order.  The system must query before it ever retries (Commit 33 Part 1.3
    #22).
    """


class ExecutionUnavailableError(ExecutionError):
    """The execution gateway / venue is unreachable.

    The engine must stop - it may never fake an ACCEPTED or a FILLED (#26).
    """


class ExecutionRejectedError(ExecutionError):
    """The venue explicitly rejected the execution request."""


class ExecutionUnknownError(ExecutionError):
    """The final state of the request is unknown and must be reconciled."""
