"""
Accounting State — versioned ledger balance aggregate.

AccountingState is the aggregate root within the Ledger bounded
context. It maintains a versioned, double-entry consistent view
of an account's financial state.

Key responsibilities:
- Track debit_total and credit_total per currency
- Derive balance from debit - credit
- Check double-entry constraint
- Version protection for concurrent updates

This is NOT a projection — it is the canonical aggregate.
Projections are rebuilt from this state's event stream.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .ledger_entry import EntryType
from .ledger_event import LedgerEvent, LedgerEventType


@dataclass
class AccountingState:
    """
    Versioned accounting state for a single (account, currency) pair.

    This is the source of truth for the account's balance.
    Balance is ALWAYS derived from the event stream, never
    directly mutated.
    """

    account_id: str
    currency: str = "USD"

    debit_total: float = 0.0
    credit_total: float = 0.0

    version: int = 0

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── tracking ────────────────────────────────────────────────
    last_event_id: str = ""
    last_execution_id: str = ""
    _processed_executions: set = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        if isinstance(self._processed_executions, list):
            self._processed_executions = set(self._processed_executions)

    # ── properties ──────────────────────────────────────────────

    @property
    def balance(self) -> float:
        """Net balance: debit_total - credit_total."""
        return self.debit_total - self.credit_total

    @property
    def is_balanced(self) -> bool:
        """True if the entire ledger is in balance (debit == credit overall)."""
        return abs(self.debit_total - self.credit_total) < 1e-10

    @property
    def key(self) -> Tuple[str, str]:
        """Unique key: (account_id, currency)."""
        return (self.account_id, self.currency)

    # ── event application ───────────────────────────────────────

    def apply_event(self, event: LedgerEvent) -> None:
        """
        Apply a single ledger event to update accounting state.

        Version is incremented on each successful application.
        Events must be applied in order.
        """
        # Only process entry-creation events
        if event.event_type not in (
            LedgerEventType.LEDGER_ENTRY_CREATED,
            LedgerEventType.LEDGER_BATCH_POSTED,
        ):
            return

        self.debit_total += event.debit
        self.credit_total += event.credit

        self.version += 1
        self.updated_at = event.timestamp
        self.last_event_id = event.source_event_id
        self.last_execution_id = event.execution_id

    def record_execution(self, execution_id: str, entry_type: str) -> None:
        """Mark an execution+entry_type as processed (idempotency)."""
        self._processed_executions.add(f"{execution_id}:{entry_type}")

    def has_execution(self, execution_id: str, entry_type: str) -> bool:
        """Check if an execution+entry_type has already been recorded."""
        return f"{execution_id}:{entry_type}" in self._processed_executions

    # ── double-entry validation ─────────────────────────────────

    def can_apply_entry(self, debit: float, credit: float) -> bool:
        """
        Pre-flight check: would applying this entry maintain balance?

        In a full double-entry system, each entry is self-balancing.
        This is a safety check before committing.
        """
        if abs(debit - credit) < 1e-10:
            return True
        new_debit = self.debit_total + debit
        new_credit = self.credit_total + credit
        return abs(new_debit - new_credit) < 1e-10

    # ── serialization ───────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "currency": self.currency,
            "debit_total": self.debit_total,
            "credit_total": self.credit_total,
            "balance": self.balance,
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "last_event_id": self.last_event_id,
            "last_execution_id": self.last_execution_id,
            "processed_executions": sorted(list(self._processed_executions)),
        }

    # ── factory ─────────────────────────────────────────────────

    @classmethod
    def empty(cls, account_id: str, currency: str = "USD") -> "AccountingState":
        """Create a zero-balance accounting state."""
        return cls(account_id=account_id, currency=currency)
