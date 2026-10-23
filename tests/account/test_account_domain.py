"""Commit 015 §2 / §3 / §13 / §18 / §19 — account & position domain rules.

These are the invariants the rest of the commit leans on.  They are
deliberately expressed as *laws*, not as snapshots of a happy path:

* a broken identity is **reported**, never repaired (§3);
* an absent valuation stays ``None``, never ``0`` (§18);
* "the broker did not say" is never turned into a plausible number
  (§19 — the T+1 trap).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from services.account.domain.balance import AccountBalance
from services.account.domain.enums import CST, PositionStatus, SyncSource
from services.account.domain.exceptions import InvalidPositionError
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot
from services.account.domain.values import (
    MONEY_QUANT,
    money,
    money_or_none,
    quantity,
    to_decimal,
)

T0 = datetime(2026, 9, 15, 9, 30, 0, tzinfo=CST)


def _pos(symbol: str = "159852", **overrides) -> Position:
    """A sound position unless a test deliberately breaks it."""
    payload = {
        "account_id": "A001",
        "symbol": symbol,
        "exchange": "SZSE",
        "quantity": "10000",
        "available_quantity": "10000",
        "frozen_quantity": "0",
        "average_cost": "1.25",
    }
    payload.update(overrides)
    return Position(**payload)


def _balance(**overrides) -> AccountBalance:
    """The demo balance — complete and self-consistent by default."""
    payload = {
        "account_id": "A001",
        "cash": "83500",
        "available_cash": "82000",
        "frozen_cash": "1500",
        "market_value": "37300",
        "total_asset": "120800",
        "buying_power": "82000",
    }
    payload.update(overrides)
    return AccountBalance(**payload)


# ══════════════════════════════════════════════════════════════════
# §2 — account balance
# ══════════════════════════════════════════════════════════════════


class TestAccountBalance:
    def test_coerces_strings_to_quantised_decimals(self):
        balance = _balance(cash="83500.00", available_cash="82000", frozen_cash="1,500")
        assert balance.cash == Decimal("83500")
        assert balance.frozen_cash == Decimal("1500")
        assert balance.cash.as_tuple().exponent == MONEY_QUANT.as_tuple().exponent

    def test_empty_account_id_is_rejected(self):
        with pytest.raises(ValueError):
            _balance(account_id="")

    def test_cash_identity_holds(self):
        balance = _balance()
        assert balance.usable_cash_consistent is True
        assert balance.total_consistent is True
        assert balance.consistent is True
        assert balance.inconsistencies() == []

    def test_broken_cash_identity_is_reported_not_repaired(self):
        balance = _balance(frozen_cash="2000")  # 82000 + 2000 != 83500
        assert balance.usable_cash_consistent is False
        assert balance.inconsistencies()
        # §3 — the reported numbers are untouched; nothing was "corrected".
        assert balance.cash == Decimal("83500")
        assert balance.frozen_cash == Decimal("2000")

    def test_total_identity_failure_when_total_is_stale(self):
        balance = _balance(total_asset="211500")  # a stale vendor total
        assert balance.total_consistent is False
        assert balance.usable_cash_consistent is True

    def test_cash_without_a_split_is_inconsistent(self):
        """Cash with no available/frozen breakdown cannot satisfy the
        identity — so it must not claim to be consistent."""
        assert AccountBalance(account_id="A001", cash="83500").consistent is False

    def test_derive_missing_fills_only_unambiguous_fields(self):
        derived = AccountBalance(
            account_id="A001", cash="0", available_cash="82000", frozen_cash="1500"
        ).derive_missing()
        assert derived.cash == Decimal("83500")
        assert derived.buying_power == Decimal("82000")
        assert derived.total_asset == Decimal("83500")
        assert derived.consistent is True

    def test_derive_missing_never_invents_a_total(self):
        derived = AccountBalance(account_id="A001").derive_missing()
        assert derived.cash == Decimal("0")
        assert derived.total_asset == Decimal("0")
        assert derived.buying_power == Decimal("0")

    def test_with_market_value_recomputes_total_from_cash(self):
        valued = _balance(market_value="128000", total_asset="211500").with_market_value(
            "37300"
        )
        assert valued.market_value == Decimal("37300")
        assert valued.total_asset == Decimal("120800")
        assert valued.consistent is True
        assert valued.cash == Decimal("83500")  # never touched

    def test_with_market_value_accepts_an_explicit_total(self):
        valued = _balance().with_market_value("37300", "120000")
        assert valued.total_asset == Decimal("120000")
        assert valued.total_consistent is False  # and it says so

    def test_currency_is_a_field_not_an_assumption(self):
        balance = _balance(currency="HKD")
        assert balance.currency == "HKD"
        assert balance.as_dict()["currency"] == "HKD"

    def test_as_dict_serialises_decimals_and_flags(self):
        payload = _balance(
            broker_timestamp=T0,
            received_timestamp=T0 + timedelta(milliseconds=180),
        ).as_dict()
        assert payload["cash"] == 83500.0
        assert payload["consistent"] is True
        assert payload["broker_timestamp"] == T0.isoformat()
        assert payload["received_timestamp"] == (
            T0 + timedelta(milliseconds=180)
        ).isoformat()


# ══════════════════════════════════════════════════════════════════
# §3 / §19 — positions
# ══════════════════════════════════════════════════════════════════


class TestPosition:
    def test_empty_account_or_symbol_is_rejected(self):
        with pytest.raises(ValueError):
            _pos(account_id="")
        with pytest.raises(ValueError):
            _pos(symbol="")

    def test_t_plus_1_split_is_consistent_and_valid(self):
        """§19 — the broker's frozen leg is the truth, not a bug."""
        position = _pos(
            symbol="159559",
            quantity="20000",
            available_quantity="0",
            frozen_quantity="20000",
        )
        assert position.consistent is True
        assert position.is_valid is True
        assert position.available_quantity == Decimal("0")
        assert position.frozen_quantity == Decimal("20000")

    def test_broken_split_is_inconsistent(self):
        position = _pos(quantity="10000", available_quantity="2000", frozen_quantity="2000")
        assert position.consistent is False
        assert position.inconsistencies()

    def test_negative_quantity_is_reported(self):
        position = _pos(quantity="-1", available_quantity="0", frozen_quantity="0")
        assert position.consistent is False
        assert any("quantity" in problem for problem in position.inconsistencies())

    def test_validate_raises_and_leaves_the_numbers_alone(self):
        position = _pos(quantity="10000", available_quantity="100", frozen_quantity="0")
        with pytest.raises(InvalidPositionError):
            position.validate()
        assert position.quantity == Decimal("10000")
        assert position.available_quantity == Decimal("100")

    def test_validate_returns_self_when_sound(self):
        position = _pos()
        assert position.validate() is position

    def test_as_invalid_marks_without_touching_numbers(self):
        position = _pos().as_invalid()
        assert position.status == PositionStatus.INVALID.value
        assert position.is_valid is False
        # the arithmetic is still self-consistent — the verdict is separate
        assert position.consistent is True
        assert position.quantity == Decimal("10000")


class TestPositionValuation:
    def test_with_valuation_computes_value_and_pnl(self):
        valued = _pos().with_valuation("1.28")
        assert valued.market_price == Decimal("1.28")
        assert valued.market_value == Decimal("12800")
        assert valued.unrealized_pnl == Decimal("300")
        assert valued.unrealized_pnl_pct == Decimal("2.4")

    def test_with_valuation_keeps_absence_absent(self):
        """§18 — no price means no numbers, never a fabricated zero."""
        position = _pos().with_valuation(None)
        assert position.market_price is None
        assert position.market_value is None
        assert position.unrealized_pnl is None
        assert position.unrealized_pnl_pct is None

    def test_zero_cost_basis_has_no_percentage(self):
        valued = _pos(symbol="510300", average_cost="0").with_valuation("1.28")
        assert valued.market_value == Decimal("12800")
        assert valued.unrealized_pnl == Decimal("12800")
        assert valued.unrealized_pnl_pct is None  # 0 cost → undefined, not 0 %

    def test_a_loss_is_negative(self):
        valued = _pos(symbol="513050", quantity="5000", average_cost="1.60").with_valuation(
            "1.50"
        )
        assert valued.unrealized_pnl == Decimal("-500")
        assert valued.unrealized_pnl_pct == Decimal("-6.25")

    def test_valuation_preserves_the_invalid_verdict(self):
        invalid = _pos(available_quantity="10").as_invalid()
        assert invalid.with_valuation("1.28").status == PositionStatus.INVALID.value


# ══════════════════════════════════════════════════════════════════
# §21 — value coercion (no silent zeros)
# ══════════════════════════════════════════════════════════════════


class TestValueCoercion:
    def test_to_decimal_rejects_bool(self):
        assert to_decimal(True) is None
        assert to_decimal(False) is None
        assert money(True) == Decimal("0")

    def test_to_decimal_parses_grouped_and_padded_text(self):
        assert to_decimal("  1,234.50 ") == Decimal("1234.50")

    def test_to_decimal_returns_default_for_garbage(self):
        assert to_decimal("n/a") is None
        assert to_decimal("") is None
        assert to_decimal(None) is None
        assert to_decimal("abc", Decimal("9")) == Decimal("9")

    def test_money_or_none_preserves_absence(self):
        assert money_or_none(None) is None
        assert money_or_none("") is None
        assert money_or_none("1.25") == Decimal("1.25")

    def test_quantities_are_quantised_at_six_dp(self):
        assert quantity("100") == Decimal("100")
        assert quantity("0.1234567") == Decimal("0.123457")


# ══════════════════════════════════════════════════════════════════
# §7 / §13 — snapshot
# ══════════════════════════════════════════════════════════════════


def _snapshot(**overrides) -> AccountSnapshot:
    payload = {
        "snapshot_id": "A001-000001-abcd1234",
        "account_id": "A001",
        "timestamp": T0,
        "received_timestamp": T0 + timedelta(milliseconds=180),
    }
    payload.update(overrides)
    return AccountSnapshot(**payload)


class TestAccountSnapshot:
    def test_defaults_to_a_broker_sourced_syncing_snapshot(self):
        snapshot = _snapshot()
        assert snapshot.source == SyncSource.BROKER.value
        assert snapshot.sequence == 0
        assert snapshot.positions == []

    def test_identity_fields_are_required(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")
        with pytest.raises(ValueError):
            _snapshot(account_id="")

    def test_naive_timestamps_are_rejected(self):
        """§13 — a naive stamp would silently compare in the wrong zone."""
        with pytest.raises(ValueError):
            _snapshot(timestamp=datetime(2026, 9, 15, 9, 30, 0))

    def test_latency_is_receipt_minus_broker_stamp(self):
        assert _snapshot().sync_latency_ms == 180.0

    def test_latency_is_zero_when_the_stamps_agree(self):
        assert _snapshot(received_timestamp=T0).sync_latency_ms == 0.0

    def test_position_count_and_symbols(self):
        snapshot = _snapshot(positions=[_pos("159852"), _pos("159559")])
        assert snapshot.position_count == 2
        assert snapshot.symbols == ["159852", "159559"]

    def test_invalid_positions_use_the_verdict_not_the_arithmetic(self):
        """A split the broker never sent has consistent arithmetic but is
        still INVALID — the snapshot must not hide it."""
        snapshot = _snapshot(positions=[_pos("159852").as_invalid(), _pos("159559")])
        assert [p.symbol for p in snapshot.invalid_positions] == ["159852"]

    def test_total_market_value_counts_only_priced_positions(self):
        snapshot = _snapshot(
            positions=[
                _pos("159852").with_valuation("1.28"),
                _pos("159559", quantity="20000"),  # unpriced → contributes nothing
            ]
        )
        assert snapshot.total_market_value == 12800.0

    def test_reconciliation_status_is_none_until_reconciled(self):
        assert _snapshot().reconciliation_status is None

    def test_as_dict_can_omit_positions(self):
        snapshot = _snapshot(positions=[_pos()])
        assert "positions" not in snapshot.as_dict(include_positions=False)
        assert len(snapshot.as_dict()["positions"]) == 1
