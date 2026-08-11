"""
Ledger Entry — immutable accounting entry with debit/credit semantics.

Each execution fact produces one or more LedgerEntries:
- TRADE   — the trade notional (debit asset / credit cash for BUY)
- FEE     — trading fees
- COMMISSION — broker commission

Entries are IMMUTABLE once created. Corrections produce
new adjustment entries, not mutating existing ones.

Ledger 模型:

    Execution Fact
         │
         ▼
    AccountingBatch (atomic group)
    ├── TradeEntry
    ├── FeeEntry
    └── CommissionEntry
         │
         ▼
    LEDGER_ENTRY_CREATED (x3)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ------------------------------------------------------------------
#  Entry type registry
# ------------------------------------------------------------------

class EntryType:
    TRADE = "TRADE"
    FEE = "FEE"
    COMMISSION = "COMMISSION"
    TAX = "TAX"
    SETTLEMENT = "SETTLEMENT"
    ADJUSTMENT = "ADJUSTMENT"


# ------------------------------------------------------------------
#  Ledger Entry
# ------------------------------------------------------------------

@dataclass(frozen=True)
class LedgerEntry:
    """
    Immutable accounting entry.

    Once written, it must never be modified. Corrections produce
    new entries (ADJUSTMENT type) rather than updating existing ones.

    Fields
    ------
    entry_id : str
        Globally unique entry identifier.
    account_id : str
        Account identifier.
    currency : str
        Settlement currency (USD, HKD, CNY, etc.).
    entry_type : str
        One of EntryType constants (TRADE, FEE, COMMISSION, …).
    debit : float
        Debit side amount (positive = asset increase, expense).
    credit : float
        Credit side amount (positive = liability increase, cash outflow).
    amount : float
        Net amount (debit - credit for this entry).
    instrument_id : str
        Traded instrument.
    order_id : str
        Parent order.
    execution_id : str
        Source execution.
    source_event_id : str
        ID of the event that caused this entry.
    transaction_currency : str
        Currency of the instrument transaction.
    base_currency : str
        Account base currency.
    fx_rate : float
        FX conversion rate (1.0 = same currency).
    base_amount : float
        Amount in base currency.
    correlation_id : str
        Links all events from same root cause.
    causation_id : str
        Points to the immediate cause event.
    lineage_id : str
        Trade lineage identifier.
    occurred_at : datetime
        When the execution occurred.
    created_at : datetime
        When this entry was created.
    """

    entry_id: str = field(default_factory=lambda: f"LEDGER-{uuid4().hex[:12].upper()}")
    account_id: str = ""
    currency: str = "USD"
    entry_type: str = EntryType.TRADE

    debit: float = 0.0
    credit: float = 0.0
    amount: float = 0.0

    instrument_id: str = ""
    order_id: str = ""
    execution_id: str = ""
    source_event_id: str = ""

    transaction_currency: str = "USD"
    base_currency: str = "USD"
    fx_rate: float = 1.0
    base_amount: float = 0.0

    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── properties ──────────────────────────────────────────────

    @property
    def is_balanced(self) -> bool:
        """Single entry self-check: debit == credit for this entry type."""
        return self.debit == self.credit

    @property
    def idempotency_key(self) -> str:
        """Unique idempotency key: account_id:execution_id:entry_type."""
        return f"{self.account_id}:{self.execution_id}:{self.entry_type}"

    @property
    def is_buy_side(self) -> bool:
        """True if this entry represents a BUY (debit asset, credit cash)."""
        return self.credit > 0 and self.debit == 0

    @property
    def is_sell_side(self) -> bool:
        """True if this entry represents a SELL (credit asset, debit cash)."""
        return self.debit > 0 and self.credit == 0

    # ── serialization ───────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "account_id": self.account_id,
            "currency": self.currency,
            "entry_type": self.entry_type,
            "debit": self.debit,
            "credit": self.credit,
            "amount": self.amount,
            "instrument_id": self.instrument_id,
            "order_id": self.order_id,
            "execution_id": self.execution_id,
            "source_event_id": self.source_event_id,
            "transaction_currency": self.transaction_currency,
            "base_currency": self.base_currency,
            "fx_rate": self.fx_rate,
            "base_amount": self.base_amount,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "occurred_at": self.occurred_at.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


# ------------------------------------------------------------------
#  Factory helpers
# ------------------------------------------------------------------

@dataclass(frozen=True)
class TradeEntry(LedgerEntry):
    """
    Trade notional entry.

    BUY:
        Credit Cash  (cash outflow)
    SELL:
        Debit Cash   (cash inflow)
    """

    entry_type: str = EntryType.TRADE


@dataclass(frozen=True)
class FeeEntry(LedgerEntry):
    """
    Trading fee entry.

    Always reduces cash:
        Debit Expense (or Asset), Credit Cash
    """

    entry_type: str = EntryType.FEE


@dataclass(frozen=True)
class CommissionEntry(LedgerEntry):
    """
    Commission entry.

    Always reduces cash:
        Debit Commission Expense, Credit Cash
    """

    entry_type: str = EntryType.COMMISSION


# ------------------------------------------------------------------
#  AccountingBatch
# ------------------------------------------------------------------

@dataclass(frozen=True)
class AccountingBatch:
    """
    Atomic group of ledger entries for a single execution.

    All entries in a batch MUST succeed or fail together.
    The batch MUST satisfy double-entry: total_debit == total_credit.

    Fields
    ------
    batch_id : str
        Unique batch identifier.
    entries : list[LedgerEntry]
        The entries that make up this batch.
    """

    batch_id: str
    entries: List[LedgerEntry]

    @property
    def total_debit(self) -> float:
        """Sum of all debit amounts in this batch."""
        return sum(e.debit for e in self.entries)

    @property
    def total_credit(self) -> float:
        """Sum of all credit amounts in this batch."""
        return sum(e.credit for e in self.entries)

    @property
    def is_balanced(self) -> bool:
        """True if total_debit == total_credit (double-entry constraint)."""
        return abs(self.total_debit - self.total_credit) < 1e-10

    @property
    def entry_count(self) -> int:
        return len(self.entries)
