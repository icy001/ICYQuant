"""
Balance Projection — query model derived from ledger events.

The projection is rebuilt by replaying LedgerEntryCreatedEvent
events. It is NOT the source of truth — the event stream is.

If the projection is corrupted, it can be rebuilt by replaying
the event stream without touching OMS, Position, or any other
bounded context.

Usage:
    proj = LedgerProjection.empty("ACC-001", "USD")
    for event in event_store.load("ACC-001"):
        proj.apply_event(event)
    balance = proj.balance
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from ..domain.ledger_entry import EntryType
from ..domain.ledger_event import LedgerEvent, LedgerEventType


@dataclass
class BalanceByCurrency:
    """Breakdown of debit/credit/balance for a single currency."""

    currency: str
    debit_total: float = 0.0
    credit_total: float = 0.0

    @property
    def balance(self) -> float:
        return self.debit_total - self.credit_total

    def apply_debit(self, amount: float) -> None:
        self.debit_total += amount

    def apply_credit(self, amount: float) -> None:
        self.credit_total += amount


@dataclass
class EntryTypeBreakdown:
    """Amounts broken down by entry type."""

    entry_type: str
    total_amount: float = 0.0
    count: int = 0

    def apply(self, amount: float) -> None:
        self.total_amount += amount
        self.count += 1


@dataclass
class LedgerProjection:
    """
    Read-optimized balance projection.

    Built from ledger events. Used for fast balance queries
    without scanning the entire event store.

    Supports multi-currency balances and entry-type breakdowns.
    """

    account_id: str

    # ── per-currency balances ───────────────────────────────────
    _currencies: Dict[str, BalanceByCurrency] = field(default_factory=dict)

    # ── per entry-type breakdown ────────────────────────────────
    _entry_types: Dict[str, EntryTypeBreakdown] = field(default_factory=dict)

    # ── metadata ────────────────────────────────────────────────
    version: int = 0
    event_count: int = 0
    last_event_id: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── balance query ───────────────────────────────────────────

    def get_balance(self, currency: str = "USD") -> float:
        """Get the net balance for a currency."""
        if currency in self._currencies:
            return self._currencies[currency].balance
        return 0.0

    def get_debit_total(self, currency: str = "USD") -> float:
        if currency in self._currencies:
            return self._currencies[currency].debit_total
        return 0.0

    def get_credit_total(self, currency: str = "USD") -> float:
        if currency in self._currencies:
            return self._currencies[currency].credit_total
        return 0.0

    @property
    def all_currencies(self) -> List[str]:
        return sorted(self._currencies.keys())

    @property
    def total_balance(self) -> Dict[str, float]:
        """Balances across all currencies."""
        return {c: v.balance for c, v in self._currencies.items()}

    # ── entry-type breakdown ────────────────────────────────────

    def get_entry_type_amount(self, entry_type: str) -> float:
        if entry_type in self._entry_types:
            return self._entry_types[entry_type].total_amount
        return 0.0

    def get_entry_type_count(self, entry_type: str) -> int:
        if entry_type in self._entry_types:
            return self._entry_types[entry_type].count
        return 0

    @property
    def trade_amount(self) -> float:
        return self.get_entry_type_amount(EntryType.TRADE)

    @property
    def fee_amount(self) -> float:
        return self.get_entry_type_amount(EntryType.FEE)

    @property
    def commission_amount(self) -> float:
        return self.get_entry_type_amount(EntryType.COMMISSION)

    @property
    def total_fees_and_commissions(self) -> float:
        return self.fee_amount + self.commission_amount

    # ── event application ───────────────────────────────────────

    def apply_event(self, event: LedgerEvent) -> None:
        """Apply a ledger event to update the projection."""
        currency = event.currency or "USD"

        # Ensure currency bucket exists
        if currency not in self._currencies:
            self._currencies[currency] = BalanceByCurrency(currency=currency)

        # Apply debit/credit
        if event.debit > 0:
            self._currencies[currency].apply_debit(event.debit)
        if event.credit > 0:
            self._currencies[currency].apply_credit(event.credit)

        # Entry-type breakdown
        entry_type = event.entry_type or "UNKNOWN"
        if entry_type not in self._entry_types:
            self._entry_types[entry_type] = EntryTypeBreakdown(entry_type=entry_type)
        self._entry_types[entry_type].apply(event.amount)

        # Metadata
        self.version += 1
        self.event_count += 1
        self.last_event_id = event.source_event_id
        self.updated_at = event.timestamp

    def apply_events(self, events: List[LedgerEvent]) -> None:
        """Apply multiple events in order."""
        for event in events:
            self.apply_event(event)

    # ── rebuild ─────────────────────────────────────────────────

    @classmethod
    def from_events(cls, account_id: str, events: List[LedgerEvent]) -> "LedgerProjection":
        """Rebuild the projection from an event stream."""
        proj = cls.empty(account_id)
        proj.apply_events(events)
        return proj

    @classmethod
    def empty(cls, account_id: str) -> "LedgerProjection":
        return cls(account_id=account_id)

    # ── serialization ───────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "balances": {
                c: {"debit": v.debit_total, "credit": v.credit_total, "balance": v.balance}
                for c, v in self._currencies.items()
            },
            "entry_types": {
                et: {"total": b.total_amount, "count": b.count}
                for et, b in self._entry_types.items()
            },
            "version": self.version,
            "event_count": self.event_count,
            "last_event_id": self.last_event_id,
            "updated_at": self.updated_at.isoformat(),
        }
