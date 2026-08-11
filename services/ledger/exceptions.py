"""
Ledger domain exceptions.

Hierarchy:

    LedgerError                     ← base
    ├── EventValidationError        ← event contract violation
    ├── EventStoreError             ← persistence failure
    │   └── DuplicateEventError     ← duplicate event id in store
    ├── UnbalancedJournalError      ← debit ≠ credit
    │
    ├── LedgerEntryError            ← base for entry-level errors
    │   ├── DuplicateEntryError     ← idempotency violation
    │   ├── AccountingConflictError ← optimistic concurrency
    │   └── EntryValidationError    ← invalid entry data
    │
    ├── SequenceGapError            ← missing intermediate event
    └── StaleEventError             ← version already applied
"""


class LedgerError(Exception):
    """Base ledger exception."""


class EventValidationError(LedgerError):
    """Raised when an event fails validation."""


class EventStoreError(LedgerError):
    """Raised when event persistence fails."""


class DuplicateEventError(EventStoreError):
    """Raised when duplicated event id is detected."""


class UnbalancedJournalError(RuntimeError):
    """Journal is not balanced (debit != credit)."""


# ------------------------------------------------------------------
#  Entry-level errors
# ------------------------------------------------------------------

class LedgerEntryError(LedgerError):
    """Base for all ledger-entry-related errors."""


class DuplicateEntryError(LedgerEntryError):
    """
    Raised when an execution has already been recorded in the ledger.

    Idempotency key: (account_id, execution_id, entry_type)
    """

    def __init__(
        self,
        account_id: str = "",
        execution_id: str = "",
        entry_type: str = "",
        *args: object,
    ) -> None:
        self.account_id = account_id
        self.execution_id = execution_id
        self.entry_type = entry_type
        msg = (
            f"Duplicate ledger entry: "
            f"account={account_id}, "
            f"execution={execution_id}, "
            f"type={entry_type}"
        )
        super().__init__(msg, *args)


class AccountingConflictError(LedgerEntryError):
    """
    Optimistic concurrency conflict when updating accounting state.

    Expected version does not match the current version.
    """

    def __init__(
        self,
        account_id: str = "",
        expected_version: int = 0,
        current_version: int = 0,
        *args: object,
    ) -> None:
        self.account_id = account_id
        self.expected_version = expected_version
        self.current_version = current_version
        msg = (
            f"Accounting conflict for account={account_id}: "
            f"expected v{expected_version}, found v{current_version}"
        )
        super().__init__(msg, *args)


class EntryValidationError(LedgerEntryError):
    """Raised when ledger entry data fails validation."""


# ------------------------------------------------------------------
#  Ordering / sequencing errors
# ------------------------------------------------------------------

class SequenceGapError(LedgerError):
    """
    Raised when a gap in the event sequence is detected.

    Example: current version 4, received version 6 → version 5 is missing.
    """

    def __init__(
        self,
        aggregate_id: str = "",
        expected_version: int = 0,
        received_version: int = 0,
        *args: object,
    ) -> None:
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.received_version = received_version
        msg = (
            f"Sequence gap for {aggregate_id}: "
            f"expected v{expected_version}, received v{received_version}"
        )
        super().__init__(msg, *args)


class StaleEventError(LedgerError):
    """
    Raised when an event version is less than the current state version.

    This usually means the event was already applied.
    """

    def __init__(
        self,
        aggregate_id: str = "",
        current_version: int = 0,
        event_version: int = 0,
        *args: object,
    ) -> None:
        self.aggregate_id = aggregate_id
        self.current_version = current_version
        self.event_version = event_version
        msg = (
            f"Stale event for {aggregate_id}: "
            f"current v{current_version}, received v{event_version}"
        )
        super().__init__(msg, *args)
