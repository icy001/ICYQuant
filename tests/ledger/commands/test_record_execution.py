"""
Tests for RecordExecutionCommand — translating execution facts into ledger entries.

Coverage:
- Basic command construction
- Validation (missing fields, invalid values)
- Trade entry generation (BUY / SELL)
- Fee and commission entry generation
- Batch building with double-entry validation
- Entry property accessors
- Trade notional calculation
- Total cash impact
"""

import pytest

from services.ledger.commands.record_execution import RecordExecutionCommand
from services.ledger.domain.ledger_entry import (
    AccountingBatch,
    EntryType,
)
from services.ledger.exceptions import EntryValidationError


# ── fixture helpers ────────────────────────────────────────────────

def _make_command(**overrides) -> RecordExecutionCommand:
    """Create a valid BUY command with sensible defaults."""
    defaults = {
        "account_id": "ACC-001",
        "instrument_id": "NVDA",
        "side": "BUY",
        "fill_quantity": 1000.0,
        "fill_price": 180.0,
        "order_id": "ORD-001",
        "execution_id": "EXEC-001",
        "source_event_id": "EVT-001",
        "currency": "USD",
    }
    defaults.update(overrides)
    return RecordExecutionCommand(**defaults)


# ── Basic construction ─────────────────────────────────────────────

class TestCommandConstruction:
    def test_create_valid_buy_command(self) -> None:
        cmd = _make_command()
        assert cmd.account_id == "ACC-001"
        assert cmd.side == "BUY"
        assert cmd.is_buy
        assert not cmd.is_sell

    def test_create_valid_sell_command(self) -> None:
        cmd = _make_command(side="SELL")
        assert cmd.side == "SELL"
        assert cmd.is_sell
        assert not cmd.is_buy

    def test_trade_notional(self) -> None:
        cmd = _make_command(fill_quantity=1000, fill_price=180.0)
        assert cmd.trade_notional == 180000.0

    def test_delta_notional(self) -> None:
        cmd = _make_command(fill_quantity=1000, fill_price=180.0, delta=500.0)
        assert cmd.delta_notional == 90000.0

    def test_delta_notional_without_delta(self) -> None:
        """When delta is unset, uses fill_quantity."""
        cmd = _make_command(fill_quantity=1000, fill_price=180.0)
        assert cmd.delta_notional == 180000.0

    def test_total_cash_impact_buy(self) -> None:
        cmd = _make_command(fill_quantity=1000, fill_price=180.0, fee=10.0, commission=5.0)
        assert cmd.total_cash_impact == 180015.0  # 180000 + 10 + 5

    def test_total_cash_impact_sell(self) -> None:
        cmd = _make_command(side="SELL", fill_quantity=1000, fill_price=185.0,
                            fee=10.0, commission=5.0)
        assert cmd.total_cash_impact == 184985.0  # 185000 - 10 - 5

    def test_total_cash_impact_no_fees(self) -> None:
        cmd = _make_command(fill_quantity=1000, fill_price=180.0)
        assert cmd.total_cash_impact == 180000.0


# ── Validation ─────────────────────────────────────────────────────

class TestCommandValidation:
    def test_valid_command_passes(self) -> None:
        cmd = _make_command()
        cmd.validate()  # Should not raise

    def test_missing_account_id(self) -> None:
        cmd = _make_command(account_id="")
        with pytest.raises(EntryValidationError, match="account_id"):
            cmd.validate()

    def test_missing_instrument_id(self) -> None:
        cmd = _make_command(instrument_id="")
        with pytest.raises(EntryValidationError, match="instrument_id"):
            cmd.validate()

    def test_missing_order_id(self) -> None:
        cmd = _make_command(order_id="")
        with pytest.raises(EntryValidationError, match="order_id"):
            cmd.validate()

    def test_missing_execution_id(self) -> None:
        cmd = _make_command(execution_id="")
        with pytest.raises(EntryValidationError, match="execution_id"):
            cmd.validate()

    def test_zero_fill_quantity(self) -> None:
        cmd = _make_command(fill_quantity=0)
        with pytest.raises(EntryValidationError, match="fill_quantity"):
            cmd.validate()

    def test_negative_fill_quantity(self) -> None:
        cmd = _make_command(fill_quantity=-100)
        with pytest.raises(EntryValidationError, match="fill_quantity"):
            cmd.validate()

    def test_zero_fill_price(self) -> None:
        cmd = _make_command(fill_price=0)
        with pytest.raises(EntryValidationError, match="fill_price"):
            cmd.validate()

    def test_negative_fill_price(self) -> None:
        cmd = _make_command(fill_price=-100)
        with pytest.raises(EntryValidationError, match="fill_price"):
            cmd.validate()

    def test_invalid_side(self) -> None:
        cmd = _make_command(side="HOLD")
        with pytest.raises(EntryValidationError, match="side"):
            cmd.validate()

    def test_negative_fee(self) -> None:
        cmd = _make_command(fee=-10)
        with pytest.raises(EntryValidationError, match="fee"):
            cmd.validate()

    def test_negative_commission(self) -> None:
        cmd = _make_command(commission=-5)
        with pytest.raises(EntryValidationError, match="commission"):
            cmd.validate()


# ── Entry building ─────────────────────────────────────────────────

class TestEntryBuilding:
    def test_build_buy_trade_entry(self) -> None:
        cmd = _make_command(side="BUY", fill_quantity=1000, fill_price=180.0)
        entries = cmd.build_entries()
        assert len(entries) == 1
        trade = entries[0]
        assert trade.entry_type == EntryType.TRADE
        assert trade.debit == 0.0
        assert trade.credit == 180000.0
        assert trade.amount == -180000.0
        assert trade.is_buy_side

    def test_build_sell_trade_entry(self) -> None:
        cmd = _make_command(side="SELL", fill_quantity=1000, fill_price=185.0)
        entries = cmd.build_entries()
        assert len(entries) == 1
        trade = entries[0]
        assert trade.entry_type == EntryType.TRADE
        assert trade.debit == 185000.0
        assert trade.credit == 0.0
        assert trade.amount == 185000.0
        assert trade.is_sell_side

    def test_build_with_fee(self) -> None:
        cmd = _make_command(fee=10.0)
        entries = cmd.build_entries()
        assert len(entries) == 2
        types = [e.entry_type for e in entries]
        assert EntryType.TRADE in types
        assert EntryType.FEE in types

    def test_build_with_commission(self) -> None:
        cmd = _make_command(commission=5.0)
        entries = cmd.build_entries()
        assert len(entries) == 2
        types = [e.entry_type for e in entries]
        assert EntryType.TRADE in types
        assert EntryType.COMMISSION in types

    def test_build_with_both_fee_and_commission(self) -> None:
        cmd = _make_command(fee=10.0, commission=5.0)
        entries = cmd.build_entries()
        assert len(entries) == 3
        types = {e.entry_type for e in entries}
        assert types == {EntryType.TRADE, EntryType.FEE, EntryType.COMMISSION}

    def test_fee_entry_has_correct_amount(self) -> None:
        cmd = _make_command(fee=10.0)
        cmd.build_entries()
        fee_entry = cmd.fee_entry
        assert fee_entry is not None
        assert fee_entry.debit == 10.0
        assert fee_entry.amount == -10.0

    def test_commission_entry_has_correct_amount(self) -> None:
        cmd = _make_command(commission=5.0)
        cmd.build_entries()
        comm_entry = cmd.commission_entry
        assert comm_entry is not None
        assert comm_entry.debit == 5.0
        assert comm_entry.amount == -5.0

    def test_entry_lineage_propagation(self) -> None:
        cmd = _make_command(
            correlation_id="CORR-001",
            causation_id="CAUS-001",
            lineage_id="LINE-001",
        )
        entries = cmd.build_entries()
        for entry in entries:
            assert entry.correlation_id == "CORR-001"
            assert entry.causation_id == "CAUS-001"
            assert entry.lineage_id == "LINE-001"

    def test_entry_source_event_id(self) -> None:
        cmd = _make_command(source_event_id="EVT-001")
        entries = cmd.build_entries()
        for entry in entries:
            assert entry.source_event_id == "EVT-001"
            assert entry.execution_id == "EXEC-001"
            assert entry.order_id == "ORD-001"

    def test_build_entries_only_once(self) -> None:
        cmd = _make_command()
        entries1 = cmd.build_entries()
        entries2 = cmd.build_entries()
        assert len(entries1) == len(entries2) == 1
        # Calls rebuilds — entries are new objects


# ── Batch building ─────────────────────────────────────────────────

class TestBatchBuilding:
    def test_build_batch_no_fees(self) -> None:
        cmd = _make_command()
        batch = cmd.build_batch()
        assert isinstance(batch, AccountingBatch)
        assert batch.batch_id == "BATCH-EXEC-001"

    def test_build_batch_with_fees(self) -> None:
        cmd = _make_command(fee=10.0, commission=5.0)
        batch = cmd.build_batch()
        assert batch.entry_count == 3
        assert batch.batch_id == "BATCH-EXEC-001"

    def test_single_entry_batch_not_self_balanced(self) -> None:
        """Single cash entry is one side of the journal — contra goes elsewhere."""
        cmd = _make_command(side="SELL", fill_quantity=1000, fill_price=100.0)
        batch = cmd.build_batch()
        # Single entry with only debit is not balanced by itself
        assert not batch.is_balanced
