"""
Ledger domain exceptions.
"""


class LedgerError(Exception):
    """
    Base ledger exception.
    """


class EventValidationError(LedgerError):
    """
    Raised when an event
    fails validation.
    """


class EventStoreError(LedgerError):
    """
    Raised when event persistence
    fails.
    """


class DuplicateEventError(EventStoreError):
    """
    Raised when duplicated
    event id is detected.
    """


class UnbalancedJournalError(
    RuntimeError,
):
    """Journal is not balanced."""