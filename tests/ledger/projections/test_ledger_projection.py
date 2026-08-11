"""
Tests for LedgerProjection — read-optimized balance projection.

Coverage:
- Empty projection creation
- apply_event() updates balances
- apply_events() batch update
- from_events() factory method
- Multi-currency support
- Entry-type breakdown (TRADE, FEE, COMMISSION)
- Balance query by currency
- Serialization to_dict
"""

from datetime import datetime, timezone

from services.ledger.domain.ledger_entry import EntryType
from services.ledger.domain.ledger_event import (
    LedgerEntryCreatedEvent,
    LedgerEvent,
    LedgerEventType,
)
from services.ledger.projections.ledger_projection import LedgerProjection


# ── fixture helpers ────────────────────────────────────────────────

def _make_trade_event(
    account_id: str = "ACC-001",
    currency: str = "USD",
    debit: float = 0.0,
    credit: float = 0.0,
    amount: float = 0.0,
    execution_id: str = "EXEC-001",
    source_event_id: str = "EVT-001",
    entry_type: str = EntryType.TRADE,
    **kwargs,
) -> LedgerEntryCreatedEvent:
    return LedgerEntryCreatedEvent(
        entry_id=f"LEDGER-{source_event_id}",
        account_id=account_id,
        currency=currency,
        entry_type=entry_type,
        debit=debit,
        credit=credit,
        amount=amount,
        instrument_id="NVDA",
        order_id="ORD-001",
        execution_id=execution_id,
        source_event_id=source_event_id,
        **kwargs,
    )


# ── Empty projection ───────────────────────────────────────────────

class TestEmptyProjection:
    def test_empty_balance_is_zero(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        assert proj.get_balance("USD") == 0.0

    def test_empty_zero_events(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        assert proj.event_count == 0
        assert proj.version == 0

    def test_empty_no_currencies(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        assert proj.all_currencies == []

    def test_empty_fee_amount_zero(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        assert proj.fee_amount == 0.0
        assert proj.commission_amount == 0.0
        assert proj.total_fees_and_commissions == 0.0


# ── Single event ───────────────────────────────────────────────────

class TestSingleEvent:
    def test_apply_buy_trade(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        event = _make_trade_event(credit=180000.0, amount=-180000.0)
        proj.apply_event(event)
        assert proj.get_balance("USD") == -180000.0
        assert proj.version == 1
        assert proj.event_count == 1

    def test_apply_sell_trade(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        event = _make_trade_event(debit=185000.0, amount=185000.0)
        proj.apply_event(event)
        assert proj.get_balance("USD") == 185000.0

    def test_apply_fee(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        event = _make_trade_event(
            entry_type=EntryType.FEE, debit=10.0, credit=0.0, amount=-10.0,
        )
        proj.apply_event(event)
        assert proj.get_balance("USD") == 10.0  # debit increases balance
        assert proj.fee_amount == -10.0

    def test_apply_commission(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        event = _make_trade_event(
            entry_type=EntryType.COMMISSION, debit=5.0, credit=0.0, amount=-5.0,
        )
        proj.apply_event(event)
        assert proj.commission_amount == -5.0
        assert proj.total_fees_and_commissions == -5.0

    def test_last_event_id_tracked(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        event = _make_trade_event(source_event_id="EVT-001", credit=100000.0, amount=-100000.0)
        proj.apply_event(event)
        assert proj.last_event_id == "EVT-001"


# ── Multiple events ────────────────────────────────────────────────

class TestMultipleEvents:
    def test_multiple_trades(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        # BUY 1000 @ 180 = -180000
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-001", execution_id="EXEC-001",
            credit=180000.0, amount=-180000.0,
        ))
        # BUY 500 @ 182 = -91000
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-002", execution_id="EXEC-002",
            credit=91000.0, amount=-91000.0,
        ))
        assert proj.get_balance("USD") == -271000.0
        assert proj.version == 2
        assert proj.event_count == 2

    def test_buy_and_sell_net_balance(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        # BUY: credit 100000
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-001", credit=100000.0, amount=-100000.0,
        ))
        # SELL: debit 120000
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-002", execution_id="EXEC-002",
            debit=120000.0, amount=120000.0,
        ))
        # Net: debit 120000 - credit 100000 = 20000
        assert proj.get_balance("USD") == 20000.0

    def test_entry_type_counts(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-001", credit=100000.0, amount=-100000.0,
        ))
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-002", credit=10000.0, amount=-10000.0,
            entry_type=EntryType.FEE,
        ))
        assert proj.get_entry_type_count(EntryType.TRADE) == 1
        assert proj.get_entry_type_count(EntryType.FEE) == 1
        assert proj.trade_amount == -100000.0
        assert proj.fee_amount == -10000.0

    def test_total_fees_and_commissions(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-001", credit=100000.0, amount=-100000.0,
        ))
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-002", entry_type=EntryType.FEE,
            debit=10.0, amount=-10.0,
        ))
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-003", entry_type=EntryType.COMMISSION,
            debit=5.0, amount=-5.0,
        ))
        assert proj.total_fees_and_commissions == -15.0


# ── Multi-currency ─────────────────────────────────────────────────

class TestMultiCurrency:
    def test_different_currencies_separate(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        proj.apply_event(_make_trade_event(currency="USD", credit=100000.0, amount=-100000.0))
        proj.apply_event(_make_trade_event(
            source_event_id="EVT-002", execution_id="EXEC-002",
            currency="HKD", debit=500000.0, amount=500000.0,
        ))
        assert proj.get_balance("USD") == -100000.0
        assert proj.get_balance("HKD") == 500000.0
        assert set(proj.all_currencies) == {"HKD", "USD"}


# ── Factory ────────────────────────────────────────────────────────

class TestFactoryMethods:
    def test_from_events(self) -> None:
        events = [
            _make_trade_event(source_event_id="EVT-001", credit=100000.0, amount=-100000.0),
            _make_trade_event(
                source_event_id="EVT-002", execution_id="EXEC-002",
                debit=20000.0, amount=20000.0,
            ),
        ]
        proj = LedgerProjection.from_events("ACC-001", events)
        assert proj.get_balance("USD") == -80000.0
        assert proj.event_count == 2

    def test_from_events_empty(self) -> None:
        proj = LedgerProjection.from_events("ACC-001", [])
        assert proj.get_balance("USD") == 0.0
        assert proj.event_count == 0


# ── Serialization ──────────────────────────────────────────────────

class TestSerialization:
    def test_to_dict(self) -> None:
        proj = LedgerProjection.empty("ACC-001")
        proj.apply_event(_make_trade_event(credit=100000.0, amount=-100000.0))
        d = proj.to_dict()
        assert d["account_id"] == "ACC-001"
        assert "USD" in d["balances"]
        assert d["balances"]["USD"]["balance"] == -100000.0
        assert d["version"] == 1
        assert d["event_count"] == 1
