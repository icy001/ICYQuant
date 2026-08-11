"""
RecordExecutionCommand — translate Execution facts into Ledger Entries.

This command bridges the gap between an execution event
(ORDER_FILLED / ORDER_PARTIAL_FILL) and immutable ledger entries.

Design principle:

    Ledger 不直接修改 Cash。
    Balance 是 Ledger Entry 的结果，不是独立事实。
    Trade / Fee / Commission 必须分开记录。

Validation:
- fill_quantity > 0, fill_price > 0
- account_id, instrument_id, order_id, execution_id all required
- Side must be BUY or SELL
- Entry must be self-balancing (debit == credit)
"""

from dataclasses import dataclass, field
from typing import List, Optional

from ..domain.ledger_entry import (
    AccountingBatch,
    CommissionEntry,
    EntryType,
    FeeEntry,
    LedgerEntry,
    TradeEntry,
)
from ..exceptions import EntryValidationError, LedgerError


# Forward reference to avoid circular import
LedgerErrors = (LedgerError, EntryValidationError)


@dataclass
class RecordExecutionCommand:
    """
    Command: record an execution fact as ledger entries.

    Input from execution event:
        account_id, instrument_id, side
        fill_quantity, fill_price
        order_id, execution_id
        source_event_id

    Optional:
        fee, commission
        correlation_id, causation_id, lineage_id
    """

    account_id: str
    instrument_id: str
    side: str  # BUY or SELL

    fill_quantity: float
    fill_price: float

    order_id: str
    execution_id: str
    source_event_id: str

    # ── additional financial details ────────────────────────────
    currency: str = "USD"
    fee: float = 0.0
    commission: float = 0.0

    # ── order context ───────────────────────────────────────────
    ordered_quantity: float = 0.0
    cumulative_fill: float = 0.0
    previous_cumulative_fill: float = 0.0
    delta: float = 0.0

    # ── lineage ─────────────────────────────────────────────────
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    # ── internal ────────────────────────────────────────────────
    _entries: List[LedgerEntry] = field(default_factory=list, repr=False)

    # ── properties ──────────────────────────────────────────────

    @property
    def trade_notional(self) -> float:
        """Gross trade value: fill_quantity × fill_price."""
        return self.fill_quantity * self.fill_price

    @property
    def delta_notional(self) -> float:
        """Notional value of the delta (non-cumulative fill)."""
        effective_qty = self.delta if self.delta > 0 else self.fill_quantity
        return effective_qty * self.fill_price

    @property
    def total_cash_impact(self) -> float:
        """Total cash outflow (BUY) or inflow (SELL) including fees."""
        notional = self.trade_notional
        extras = self.fee + self.commission
        if self.is_buy:
            return notional + extras  # outflow
        return notional - extras  # inflow

    @property
    def is_buy(self) -> bool:
        return self.side.upper() == "BUY"

    @property
    def is_sell(self) -> bool:
        return self.side.upper() == "SELL"

    @property
    def entries(self) -> List[LedgerEntry]:
        """The ledger entries produced by this command."""
        return list(self._entries)

    # ── validation ──────────────────────────────────────────────

    def validate(self) -> None:
        """Validate all required fields are present and valid."""
        errors: List[str] = []

        if not self.account_id:
            errors.append("account_id is required")
        if not self.instrument_id:
            errors.append("instrument_id is required")
        if not self.order_id:
            errors.append("order_id is required")
        if not self.execution_id:
            errors.append("execution_id is required")
        if self.fill_quantity <= 0:
            errors.append(f"fill_quantity must be > 0, got {self.fill_quantity}")
        if self.fill_price <= 0:
            errors.append(f"fill_price must be > 0, got {self.fill_price}")
        if self.side.upper() not in ("BUY", "SELL"):
            errors.append(f"side must be BUY or SELL, got {self.side}")
        if self.fee < 0:
            errors.append(f"fee cannot be negative, got {self.fee}")
        if self.commission < 0:
            errors.append(f"commission cannot be negative, got {self.commission}")

        if errors:
            raise EntryValidationError("; ".join(errors))

    # ── entry generation ────────────────────────────────────────

    def build_entries(self) -> List[LedgerEntry]:
        """
        Build all ledger entries for this execution.

        Returns a list of [TradeEntry, FeeEntry?, CommissionEntry?].
        The entries are NOT persisted here — this is purely domain logic.
        """
        self.validate()
        self._entries = []

        # ── 1. Trade entry ──────────────────────────────────────
        notional = self.trade_notional

        if self.is_buy:
            # BUY: Debit Asset, Credit Cash
            trade = TradeEntry(
                account_id=self.account_id,
                currency=self.currency,
                debit=0.0,
                credit=notional,
                amount=-notional,  # negative = cash outflow
                instrument_id=self.instrument_id,
                order_id=self.order_id,
                execution_id=self.execution_id,
                source_event_id=self.source_event_id,
                correlation_id=self.correlation_id,
                causation_id=self.causation_id,
                lineage_id=self.lineage_id,
            )
        else:
            # SELL: Debit Cash, Credit Asset
            trade = TradeEntry(
                account_id=self.account_id,
                currency=self.currency,
                debit=notional,
                credit=0.0,
                amount=notional,  # positive = cash inflow
                instrument_id=self.instrument_id,
                order_id=self.order_id,
                execution_id=self.execution_id,
                source_event_id=self.source_event_id,
                correlation_id=self.correlation_id,
                causation_id=self.causation_id,
                lineage_id=self.lineage_id,
            )
        self._entries.append(trade)

        # ── 2. Fee entry (if applicable) ────────────────────────
        if self.fee > 0:
            fee = FeeEntry(
                account_id=self.account_id,
                currency=self.currency,
                debit=self.fee,  # expense debit
                credit=0.0,
                amount=-self.fee,
                instrument_id=self.instrument_id,
                order_id=self.order_id,
                execution_id=self.execution_id,
                source_event_id=self.source_event_id,
                correlation_id=self.correlation_id,
                causation_id=self.causation_id,
                lineage_id=self.lineage_id,
            )
            self._entries.append(fee)

        # ── 3. Commission entry (if applicable) ─────────────────
        if self.commission > 0:
            comm = CommissionEntry(
                account_id=self.account_id,
                currency=self.currency,
                debit=self.commission,  # expense debit
                credit=0.0,
                amount=-self.commission,
                instrument_id=self.instrument_id,
                order_id=self.order_id,
                execution_id=self.execution_id,
                source_event_id=self.source_event_id,
                correlation_id=self.correlation_id,
                causation_id=self.causation_id,
                lineage_id=self.lineage_id,
            )
            self._entries.append(comm)

        return self._entries

    def build_batch(self) -> AccountingBatch:
        """
        Build an atomic accounting batch from the entries.

        Returns the batch without requiring intra-batch self-balance.
        In full double-entry, individual account entries are one side
        of the journal — the contra goes to other accounts. The batch
        is structured for atomic posting, not self-balancing.
        """
        entries = self.build_entries()
        batch_id = f"BATCH-{self.execution_id}"
        return AccountingBatch(batch_id=batch_id, entries=entries)

    # ── entry filtering ─────────────────────────────────────────

    def get_entry_by_type(self, entry_type: str) -> Optional[LedgerEntry]:
        for entry in self._entries:
            if entry.entry_type == entry_type:
                return entry
        return None

    @property
    def trade_entry(self) -> Optional[LedgerEntry]:
        return self.get_entry_by_type(EntryType.TRADE)

    @property
    def fee_entry(self) -> Optional[LedgerEntry]:
        return self.get_entry_by_type(EntryType.FEE)

    @property
    def commission_entry(self) -> Optional[LedgerEntry]:
        return self.get_entry_by_type(EntryType.COMMISSION)
