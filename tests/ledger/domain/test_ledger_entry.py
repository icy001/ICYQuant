"""
Tests for LedgerEntry domain entity — immutable accounting entries with debit/credit.

Coverage:
- Trade entry (BUY / SELL)
- Fee entry
- Commission entry
- Idempotency key generation
- Immutability
- Serialization to_dict
- AccountingBatch atomicity
- Double-entry constraint in batch
"""

import pytest
from datetime import datetime

from services.ledger.domain.ledger_entry import (
    AccountingBatch,
    CommissionEntry,
    EntryType,
    FeeEntry,
    LedgerEntry,
    TradeEntry,
)


class TestLedgerEntry:
    """Tests for base LedgerEntry."""

    def test_create_basic_entry(self) -> None:
        entry = LedgerEntry(
            account_id="ACC-001",
            currency="USD",
            entry_type=EntryType.TRADE,
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
            instrument_id="NVDA",
            order_id="ORD-001",
            execution_id="EXEC-001",
        )
        assert entry.account_id == "ACC-001"
        assert entry.currency == "USD"
        assert entry.credit == 100000.0
        assert entry.amount == -100000.0

    def test_auto_entry_id(self) -> None:
        entry = LedgerEntry(account_id="ACC-001", amount=500.0)
        assert entry.entry_id.startswith("LEDGER-")
        assert len(entry.entry_id) > 7

    def test_idempotency_key(self) -> None:
        entry = LedgerEntry(
            account_id="ACC-001",
            execution_id="EXEC-001",
            entry_type=EntryType.TRADE,
        )
        assert entry.idempotency_key == "ACC-001:EXEC-001:TRADE"

    def test_is_balanced_true(self) -> None:
        entry = LedgerEntry(debit=100.0, credit=100.0)
        assert entry.is_balanced

    def test_is_balanced_false(self) -> None:
        entry = LedgerEntry(debit=100.0, credit=50.0)
        assert not entry.is_balanced

    def test_is_buy_side(self) -> None:
        entry = LedgerEntry(debit=0.0, credit=100000.0)
        assert entry.is_buy_side

    def test_is_sell_side(self) -> None:
        entry = LedgerEntry(debit=100000.0, credit=0.0)
        assert entry.is_sell_side

    def test_to_dict_contains_all_fields(self) -> None:
        entry = LedgerEntry(
            account_id="ACC-001",
            order_id="ORD-001",
            execution_id="EXEC-001",
            source_event_id="EVT-001",
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LINE-001",
            amount=100000.0,
        )
        d = entry.to_dict()
        assert d["entry_id"].startswith("LEDGER-")
        assert d["account_id"] == "ACC-001"
        assert d["order_id"] == "ORD-001"
        assert d["execution_id"] == "EXEC-001"
        assert d["source_event_id"] == "EVT-001"
        assert d["correlation_id"] == "CORR-001"
        assert d["causation_id"] == "CAUS-001"
        assert d["lineage_id"] == "LINE-001"

    def test_immutable_cannot_modify_field(self) -> None:
        entry = LedgerEntry(account_id="ACC-001", amount=500.0)
        with pytest.raises(Exception):
            entry.amount = 600.0  # type: ignore[misc]

    def test_entry_with_fx_fields(self) -> None:
        entry = LedgerEntry(
            account_id="ACC-001",
            currency="CNY",
            transaction_currency="USD",
            base_currency="CNY",
            fx_rate=7.25,
            base_amount=725000.0,
        )
        assert entry.transaction_currency == "USD"
        assert entry.base_currency == "CNY"
        assert entry.fx_rate == 7.25
        assert entry.base_amount == 725000.0


class TestTradeEntry:
    """Tests for TradeEntry — the trade notional."""

    def test_default_entry_type_is_trade(self) -> None:
        entry = TradeEntry(account_id="ACC-001", amount=50000.0)
        assert entry.entry_type == EntryType.TRADE

    def test_buy_trade_credit_cash(self) -> None:
        """BUY: Credit Cash (cash outflow)."""
        entry = TradeEntry(
            account_id="ACC-001",
            debit=0.0,
            credit=100000.0,
            amount=-100000.0,
        )
        assert entry.is_buy_side
        assert entry.amount == -100000.0

    def test_sell_trade_debit_cash(self) -> None:
        """SELL: Debit Cash (cash inflow)."""
        entry = TradeEntry(
            account_id="ACC-001",
            debit=100000.0,
            credit=0.0,
            amount=100000.0,
        )
        assert entry.is_sell_side
        assert entry.amount == 100000.0


class TestFeeEntry:
    """Tests for FeeEntry."""

    def test_default_entry_type_is_fee(self) -> None:
        entry = FeeEntry(account_id="ACC-001", amount=-10.0)
        assert entry.entry_type == EntryType.FEE

    def test_fee_idempotency_key(self) -> None:
        entry = FeeEntry(
            account_id="ACC-001", execution_id="EXEC-001", amount=-10.0
        )
        assert entry.idempotency_key == "ACC-001:EXEC-001:FEE"


class TestCommissionEntry:
    """Tests for CommissionEntry."""

    def test_default_entry_type_is_commission(self) -> None:
        entry = CommissionEntry(account_id="ACC-001", amount=-5.0)
        assert entry.entry_type == EntryType.COMMISSION

    def test_commission_idempotency_key(self) -> None:
        entry = CommissionEntry(
            account_id="ACC-001", execution_id="EXEC-001", amount=-5.0
        )
        assert entry.idempotency_key == "ACC-001:EXEC-001:COMMISSION"


class TestAccountingBatch:
    """Tests for AccountingBatch — atomic group of entries."""

    def test_empty_batch(self) -> None:
        batch = AccountingBatch(batch_id="BATCH-001", entries=[])
        assert batch.total_debit == 0.0
        assert batch.total_credit == 0.0
        assert batch.is_balanced
        assert batch.entry_count == 0

    def test_single_entry_batch(self) -> None:
        entry = TradeEntry(debit=0.0, credit=100000.0)
        batch = AccountingBatch(batch_id="BATCH-001", entries=[entry])
        assert batch.total_debit == 0.0
        assert batch.total_credit == 100000.0
        assert not batch.is_balanced

    def test_balanced_batch(self) -> None:
        """Two entries that balance each other."""
        trade = TradeEntry(
            account_id="ACC-001", debit=0.0, credit=100000.0, amount=-100000.0
        )
        contra = LedgerEntry(
            account_id="ASSET-001",
            debit=100000.0,
            credit=0.0,
            amount=100000.0,
            entry_type=EntryType.TRADE,
        )
        batch = AccountingBatch(batch_id="BATCH-001", entries=[trade, contra])
        assert batch.is_balanced
        assert batch.total_debit == 100000.0
        assert batch.total_credit == 100000.0

    def test_batch_with_fee_and_commission(self) -> None:
        """Trade + fee + commission may not self-balance individually."""
        trade = TradeEntry(debit=0.0, credit=100000.0)
        fee = FeeEntry(debit=10.0, credit=0.0)
        comm = CommissionEntry(debit=5.0, credit=0.0)
        batch = AccountingBatch(batch_id="BATCH-001", entries=[trade, fee, comm])
        assert batch.total_debit == 15.0
        assert batch.total_credit == 100000.0
        # Not balanced — in full double-entry, contra entries are needed
        assert not batch.is_balanced

    def test_balanced_batch_with_fees(self) -> None:
        """Full double-entry with contra entries for fees."""
        # BUY: credit cash for trade + credit cash for fee + credit cash for commission
        trade = TradeEntry(debit=0.0, credit=100000.0)
        fee = FeeEntry(debit=0.0, credit=10.0)  # Credit Cash for fee
        comm = CommissionEntry(debit=0.0, credit=5.0)  # Credit Cash for commission
        # Contra: debit each to assets/expenses
        contra_trade = LedgerEntry(entry_type=EntryType.TRADE, debit=100000.0, credit=0.0)
        contra_fee = LedgerEntry(entry_type=EntryType.FEE, debit=10.0, credit=0.0)
        contra_comm = LedgerEntry(entry_type=EntryType.COMMISSION, debit=5.0, credit=0.0)
        batch = AccountingBatch(
            batch_id="BATCH-001",
            entries=[trade, fee, comm, contra_trade, contra_fee, contra_comm],
        )
        assert batch.is_balanced
        assert batch.total_debit == batch.total_credit == 100015.0
