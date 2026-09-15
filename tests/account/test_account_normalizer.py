"""Commit 015 §1 / §3 / §13 / §19 / §21 — broker payload → standard model.

The normalizer is the boundary the whole commit is built around, so these
suites feed it the *vendor wire dialect* (Chinese keys, string numbers, a
vendor ``更新时间``) and check the four promises the module makes:

1. a broker field name is interpreted here and nowhere else;
2. a payload that does not add up is marked ``INVALID``, never repaired;
3. the broker's stale timestamp is preserved so ``sync_latency`` is real;
4. the normalizer never sets a price — valuation belongs to Market Data.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from services.account.domain.enums import CST, PositionStatus, SyncSource
from services.account.sync.exceptions import (
    AccountNormalizationError,
    UnknownAccountSymbolError,
)
from services.market_data.universe import universe

try:  # pragma: no cover - both import paths are supported
    from .helpers import (
        T0,
        account_payload,
        demo_position_payloads,
        make_config,
        position_payload,
    )
    from .helpers import make_normalizer as _make_normalizer
except ImportError:  # pragma: no cover
    from helpers import (  # type: ignore[no-redef]
        T0,
        account_payload,
        demo_position_payloads,
        make_config,
        position_payload,
    )
    from helpers import make_normalizer as _make_normalizer

RECEIVED = T0 + timedelta(milliseconds=180)


def make_normalizer(**overrides):
    """Normalizer with the Instrument Master on (the shipped wiring)."""
    return _make_normalizer(**overrides)


def ungrounded_normalizer(**overrides):
    """Normalizer without an Instrument Master — the dialect-only path."""
    from services.broker.account.normalizer import AccountNormalizer

    return AccountNormalizer(make_config(**overrides), instruments=None)


# ══════════════════════════════════════════════════════════════════
# §2 — balance mapping
# ══════════════════════════════════════════════════════════════════


class TestAccountMapping:
    def test_chinese_dialect_maps_to_the_standard_model(self):
        balance = make_normalizer().normalize_account(
            account_payload(), received_timestamp=RECEIVED
        )
        assert balance.account_id == "A001"
        assert balance.currency == "CNY"
        assert balance.cash == Decimal("83500")
        assert balance.available_cash == Decimal("82000")
        assert balance.frozen_cash == Decimal("1500")
        assert balance.market_value == Decimal("128000")
        assert balance.total_asset == Decimal("211500")
        assert balance.buying_power == Decimal("82000")
        assert balance.usable_cash_consistent is True

    def test_english_dialect_maps_through_the_same_alias_table(self):
        balance = make_normalizer().normalize_account(
            {
                "currency": "CNY",
                "cash": "1000.00",
                "available_cash": "600.00",
                "frozen_cash": "400.00",
                "market_value": "500.00",
                "total_asset": "1500.00",
                "broker_timestamp": "2026-09-15 09:30:00",
            },
            received_timestamp=RECEIVED,
        )
        assert balance.cash == Decimal("1000")
        assert balance.market_value == Decimal("500")
        assert balance.consistent is True

    def test_snake_and_kebab_keys_fold_together(self):
        balance = make_normalizer().normalize_account(
            {
                "Available-Cash": "600.00",
                "FROZEN CASH": "400.00",
                "Cash": "1000.00",
            },
            received_timestamp=RECEIVED,
        )
        assert balance.cash == Decimal("1000")
        assert balance.available_cash == Decimal("600")
        assert balance.frozen_cash == Decimal("400")

    def test_missing_account_id_is_an_error(self):
        with pytest.raises(AccountNormalizationError):
            ungrounded_normalizer(account_id=None).normalize_account(
                {"资金余额": "1"}, received_timestamp=RECEIVED
            )

    def test_account_id_falls_back_to_the_configured_account(self):
        balance = make_normalizer().normalize_account(
            {"资金余额": "1"}, received_timestamp=RECEIVED
        )
        assert balance.account_id == "A001"

    def test_a_payload_that_is_not_a_mapping_is_an_error(self):
        with pytest.raises(TypeError):
            make_normalizer().normalize_account(["not", "a", "mapping"])

    def test_broker_timestamp_is_parsed_into_cst(self):
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": "2026-09-15 09:30:00"}),
            received_timestamp=RECEIVED,
        )
        assert balance.broker_timestamp == T0
        assert balance.broker_timestamp.tzinfo is CST

    def test_a_stale_vendor_stamp_is_never_overwritten(self):
        """§13 — the whole point of keeping two timestamps."""
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": "2026-09-15 08:00:00"}),
            received_timestamp=RECEIVED,
        )
        assert balance.broker_timestamp == T0.replace(hour=8, minute=0, second=0)
        assert balance.received_timestamp == RECEIVED
        assert balance.broker_timestamp < balance.received_timestamp

    def test_received_timestamp_defaults_to_the_clock_not_the_vendor_stamp(self):
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": "2026-09-15 08:00:00"})
        )
        assert balance.received_timestamp == RECEIVED

    def test_a_naive_vendor_stamp_is_read_as_cst(self):
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": "2026-09-15T09:30:00"}),
            received_timestamp=RECEIVED,
        )
        assert balance.broker_timestamp == T0

    def test_epoch_milliseconds_are_understood(self):
        moment = datetime(2026, 9, 15, 9, 30, tzinfo=CST)
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": int(moment.timestamp() * 1000)}),
            received_timestamp=RECEIVED,
        )
        assert balance.broker_timestamp == moment

    def test_an_unparseable_stamp_degrades_to_absent(self):
        balance = make_normalizer().normalize_account(
            account_payload(**{"更新时间": "not-a-time"}),
            received_timestamp=RECEIVED,
        )
        assert balance.broker_timestamp is None
        assert balance.received_timestamp == RECEIVED


# ══════════════════════════════════════════════════════════════════
# §3 / §19 / §21 — position mapping
# ══════════════════════════════════════════════════════════════════


class TestPositionMapping:
    def test_chinese_dialect_maps_to_the_standard_model(self):
        position = make_normalizer().normalize_position(
            position_payload(), account_id="A001", received_timestamp=RECEIVED
        )
        assert position.symbol == "159852"
        assert position.exchange == "SZSE"
        assert position.quantity == Decimal("10000")
        assert position.available_quantity == Decimal("10000")
        assert position.frozen_quantity == Decimal("0")
        assert position.average_cost == Decimal("1.25")
        assert position.status == PositionStatus.VALID.value
        assert position.is_valid is True

    def test_symbol_suffix_is_normalised_away(self):
        normalizer = make_normalizer()
        for raw, expected in (
            ("159852.SZ", "SZSE"),
            ("SZ.159852", "SZSE"),
            ("159852.SZSE", "SZSE"),
            ("513050.SH", "SSE"),
            ("SH.513050", "SSE"),
        ):
            position = normalizer.normalize_position(
                position_payload(**{"证券代码": raw}),
                account_id="A001",
                received_timestamp=RECEIVED,
            )
            assert position.exchange == expected, raw

    def test_the_instrument_master_wins_over_the_reported_market(self):
        """§21 — the exchange comes from the master, not the vendor's column."""
        position = make_normalizer().normalize_position(
            position_payload(**{"证券代码": "159852", "市场": "SH"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.exchange == universe.get("159852").exchange.value

    def test_the_reported_market_is_used_when_there_is_no_master(self):
        position = ungrounded_normalizer().normalize_position(
            position_payload(**{"证券代码": "159852", "市场": "SH"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.exchange == "SSE"

    def test_an_unknown_symbol_is_rejected_when_strict(self):
        """§21 — a symbol outside the Universe is refused, not stored."""
        with pytest.raises(UnknownAccountSymbolError):
            make_normalizer().normalize_position(
                position_payload(**{"证券代码": "123456"}),
                account_id="A001",
                received_timestamp=RECEIVED,
            )

    def test_an_unknown_symbol_falls_back_to_inference_when_not_strict(self):
        position = make_normalizer(strict_symbols=False).normalize_position(
            position_payload(**{"证券代码": "123456", "市场": "SZ"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.symbol == "123456"
        assert position.exchange == "SZSE"

    def test_a_malformed_code_is_an_error(self):
        for raw in ("ABC", "12345", "1234567", ""):
            with pytest.raises(AccountNormalizationError):
                make_normalizer().normalize_position(
                    position_payload(**{"证券代码": raw}),
                    account_id="A001",
                    received_timestamp=RECEIVED,
                )

    def test_a_payload_without_a_symbol_or_quantity_is_an_error(self):
        with pytest.raises(AccountNormalizationError) as missing_symbol:
            make_normalizer().normalize_position(
                position_payload(**{"证券代码": None}),
                account_id="A001",
                received_timestamp=RECEIVED,
            )
        assert "symbol" in str(missing_symbol.value)

        with pytest.raises(AccountNormalizationError) as missing_quantity:
            make_normalizer().normalize_position(
                position_payload(**{"持仓数量": None}),
                account_id="A001",
                received_timestamp=RECEIVED,
            )
        assert "quantity" in str(missing_quantity.value)

    # ── §19 — the T+1 trap ────────────────────────────────────────────

    def test_available_is_never_assumed_equal_to_quantity(self):
        """A T+1 buy: the whole holding is frozen, none of it sellable."""
        position = make_normalizer().normalize_position(
            position_payload(**{"持仓数量": "10000", "可用数量": "0", "冻结数量": "10000"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.available_quantity == Decimal("0")
        assert position.frozen_quantity == Decimal("10000")
        assert position.consistent is True
        assert position.is_valid is True

    def test_available_is_derived_only_from_a_reported_frozen_leg(self):
        position = make_normalizer().normalize_position(
            position_payload(**{"持仓数量": "10000", "可用数量": None, "冻结数量": "2000"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.available_quantity == Decimal("8000")
        assert position.frozen_quantity == Decimal("2000")
        assert position.is_valid is True

    def test_an_absent_split_is_invalid_rather_than_guessed(self):
        """Neither leg reported: ``available = quantity`` would be a lie,
        and ``available = 0`` would look like a healthy fully-frozen row."""
        position = make_normalizer().normalize_position(
            position_payload(**{"持仓数量": "10000", "可用数量": None, "冻结数量": None}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.status == PositionStatus.INVALID.value
        assert position.is_valid is False
        assert position.quantity == Decimal("10000")

    # ── §3 — no silent repair ─────────────────────────────────────────

    def test_a_broken_split_is_marked_invalid_not_repaired(self):
        position = make_normalizer().normalize_position(
            position_payload(**{"持仓数量": "10000", "可用数量": "2000", "冻结数量": "2000"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.status == PositionStatus.INVALID.value
        assert position.consistent is False
        # nothing was nudged to make the identity hold
        assert position.quantity == Decimal("10000")
        assert position.available_quantity == Decimal("2000")
        assert position.frozen_quantity == Decimal("2000")

    def test_a_negative_holding_is_marked_invalid(self):
        position = make_normalizer().normalize_position(
            position_payload(**{"持仓数量": "-100", "可用数量": "0", "冻结数量": "0"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.status == PositionStatus.INVALID.value

    # ── §18 — one price system ────────────────────────────────────────

    def test_the_normalizer_never_sets_a_price(self):
        """The broker's own ``现价`` / ``市值`` are ignored on purpose."""
        position = make_normalizer().normalize_position(
            position_payload(**{"现价": "99.99", "市值": "999900.00"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.market_price is None
        assert position.market_value is None
        assert position.unrealized_pnl is None
        assert position.unrealized_pnl_pct is None

    def test_lots_are_scaled_only_when_the_vendor_uses_them(self):
        in_lots = make_normalizer(volume_in_lots=True).normalize_position(
            position_payload(**{"持仓数量": "100", "可用数量": "100", "冻结数量": "0"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert in_lots.quantity == Decimal("10000")
        assert in_lots.available_quantity == Decimal("10000")

    def test_position_carries_the_receipt_time(self):
        position = make_normalizer().normalize_position(
            position_payload(**{"更新时间": "2026-09-15 09:29:00"}),
            account_id="A001",
            received_timestamp=RECEIVED,
        )
        assert position.broker_timestamp == T0.replace(minute=29)
        assert position.received_timestamp == RECEIVED

    def test_normalize_positions_maps_every_row(self):
        normalizer = make_normalizer()
        positions = normalizer.normalize_positions(
            demo_position_payloads(), account_id="A001", received_timestamp=RECEIVED
        )
        assert [p.symbol for p in positions] == ["159852", "159559", "513050"]
        assert [p.status for p in positions] == [PositionStatus.VALID.value] * 3


# ══════════════════════════════════════════════════════════════════
# §6 / §7 — snapshot assembly
# ══════════════════════════════════════════════════════════════════


class TestSnapshotAssembly:
    def test_snapshot_is_assembled_from_both_halves(self):
        snapshot = make_normalizer().normalize_snapshot(
            "A001",
            account_payload(),
            demo_position_payloads(),
            received_timestamp=RECEIVED,
        )
        assert snapshot.account_id == "A001"
        assert snapshot.source == SyncSource.BROKER.value
        assert snapshot.position_count == 3
        assert snapshot.reconciliation_status is None  # set by §9, not here
        assert snapshot.sync_latency_ms == 180.0

    def test_snapshot_id_is_unique_and_traceable(self):
        normalizer = make_normalizer()
        first = normalizer.normalize_snapshot("A001", account_payload(), [])
        second = normalizer.normalize_snapshot("A001", account_payload(), [])
        assert first.snapshot_id != second.snapshot_id
        assert first.snapshot_id.startswith("A001-")

    def test_the_sequence_is_encoded_in_the_id(self):
        snapshot = make_normalizer().normalize_snapshot(
            "A001", account_payload(), [], sequence=7
        )
        assert snapshot.snapshot_id.startswith("A001-000007-")
        # §7 — and the field agrees with the id, so neither can drift
        assert snapshot.sequence == 7

    def test_no_sequence_means_the_store_will_assign_one(self):
        snapshot = make_normalizer().normalize_snapshot("A001", account_payload(), [])
        assert snapshot.sequence == 0

    def test_broker_timestamp_falls_back_to_the_oldest_position(self):
        snapshot = make_normalizer().normalize_snapshot(
            "A001",
            account_payload(**{"更新时间": None}),
            [
                position_payload(**{"更新时间": "2026-09-15 09:29:30"}),
                position_payload(**{"证券代码": "513050", "更新时间": "2026-09-15 09:28:00"}),
            ],
            received_timestamp=RECEIVED,
        )
        assert snapshot.timestamp == T0.replace(minute=28, second=0)

    def test_broker_timestamp_falls_back_to_receipt_without_any_stamp(self):
        snapshot = make_normalizer().normalize_snapshot(
            "A001",
            account_payload(**{"更新时间": None}),
            [position_payload(**{"更新时间": None})],
            received_timestamp=RECEIVED,
        )
        assert snapshot.timestamp == RECEIVED

    def test_an_empty_book_is_a_valid_snapshot(self):
        snapshot = make_normalizer().normalize_snapshot(
            "A001", account_payload(), [], received_timestamp=RECEIVED
        )
        assert snapshot.positions == []
        assert snapshot.position_count == 0
