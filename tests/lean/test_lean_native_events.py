"""K02 acceptance tests — native LEAN order-events JSON → canonical events.

The adapter is the only translation layer: ``map_order_event`` and
everything downstream must stay untouched, which these tests pin by
running the full native → canonical → mapper → ledger-trade chain.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.adapters.lean.native_events import (
    adapt_native_order_events,
    extract_signal_ids_from_contract,
    extract_signal_ids_from_log,
    is_native_lean_order_events,
)
from apps.adapters.lean.order_mapper import (
    map_order_event,
    order_event_to_ledger_trade,
)
from apps.runtime.lean_paper_e2e import load_events, parse_lean_debug_log

#: Verbatim structure of backtests/2026-09-30_14-15-35/*-order-events.json.
NATIVE_EVENTS = [
    {
        "id": "1350234380-1-1",
        "algorithmId": "1350234380",
        "orderId": 1,
        "orderEventId": 1,
        "symbol": "SPY R735QTJ8XC9X",
        "symbolValue": "SPY",
        "symbolPermtick": "SPY",
        "time": 1381152660.0,
        "status": "submitted",
        "fillPrice": 0.0,
        "fillPriceCurrency": "USD",
        "fillQuantity": 0.0,
        "direction": "buy",
        "isAssignment": False,
        "quantity": 100.0,
    },
    {
        "id": "1350234380-1-2",
        "algorithmId": "1350234380",
        "orderId": 1,
        "orderEventId": 2,
        "symbol": "SPY R735QTJ8XC9X",
        "symbolValue": "SPY",
        "symbolPermtick": "SPY",
        "time": 1381152660.0,
        "status": "filled",
        "orderFeeAmount": 1.0,
        "orderFeeCurrency": "USD",
        "fillPrice": 144.78172417,
        "fillPriceCurrency": "USD",
        "fillQuantity": 100.0,
        "direction": "buy",
        "isAssignment": False,
        "quantity": 100.0,
    },
]

#: K01-fixed runtime evidence: order events now carry the signal_id.
LOG_EVIDENCE = """
2013-10-07 09:31:00 ICYQUANT_ORDER_EVENT order_id=1 signal_id=p0_buy_spy symbol=SPY status=1 quantity=100.0 fill_qty=0.0 fill_price=0.0
2013-10-07 09:31:00 ICYQUANT_ORDER_EVENT order_id=1 signal_id=p0_buy_spy symbol=SPY status=3 quantity=100.0 fill_qty=100.0 fill_price=144.78172417
""".strip()

CONTRACT_PAYLOAD = {
    "contract_version": "1.0",
    "strategy_id": "ICYQUANT_P0_01",
    "mode": "paper",
    "symbols": ["SPY"],
    "orders": [
        {
            "strategy_id": "ICYQUANT_P0_01",
            "signal_id": "p0_buy_spy",
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 100,
        }
    ],
}


# ══════════════════════════════════════════════════════════════════
# Detection
# ══════════════════════════════════════════════════════════════════
def test_detects_native_export():
    assert is_native_lean_order_events(NATIVE_EVENTS)


def test_rejects_canonical_events():
    canonical = [{"type": "ORDER_EVENT", "order_id": "1", "status": "FILLED"}]

    assert not is_native_lean_order_events(canonical)


def test_rejects_empty_payload():
    assert not is_native_lean_order_events([])


# ══════════════════════════════════════════════════════════════════
# Frozen field mapping
# ══════════════════════════════════════════════════════════════════
def test_frozen_field_mapping():
    adapted = adapt_native_order_events(
        NATIVE_EVENTS, signal_lookup={"1": "p0_buy_spy"}
    )

    assert len(adapted) == 2

    filled = adapted[1]

    assert filled["type"] == "ORDER_EVENT"
    assert filled["order_id"] == "1"
    assert filled["symbol"] == "SPY"                      # symbolValue, SID stripped
    assert filled["status"] == "FILLED"
    assert filled["quantity"] == 100.0
    assert filled["filled_quantity"] == 100.0
    assert filled["fill_price"] == pytest.approx(144.78172417)
    assert filled["signal_id"] == "p0_buy_spy"
    assert filled["commission"] == 1.0
    assert "order_fee=1.0" in filled["message"]
    assert filled["timestamp"].startswith("2013-10-07T")


def test_unfilled_event_has_no_fill_price():
    adapted = adapt_native_order_events(
        NATIVE_EVENTS, signal_lookup={"1": "p0_buy_spy"}
    )

    submitted = adapted[0]

    assert submitted["status"] == "SUBMITTED"
    assert submitted["fill_price"] is None
    assert submitted["filled_quantity"] == 0


def test_sell_direction_signs_quantity():
    native = [
        {
            "orderId": 2,
            "status": "filled",
            "symbolValue": "SPY",
            "fillPrice": 150.0,
            "fillQuantity": 100.0,
            "direction": "sell",
            "quantity": 100.0,
            "time": 1381152660.0,
        }
    ]

    adapted = adapt_native_order_events(native)

    assert adapted[0]["quantity"] == -100.0


def test_partially_filled_status_alias():
    native = [
        {"orderId": 1, "status": "partiallyFilled", "symbolValue": "SPY"}
    ]

    adapted = adapt_native_order_events(native)

    assert adapted[0]["status"] == "PARTIALLY_FILLED"


# ══════════════════════════════════════════════════════════════════
# signal_id recovery: evidence first, contract fallback, never a guess
# ══════════════════════════════════════════════════════════════════
def test_signal_ids_from_log_evidence():
    lookup = extract_signal_ids_from_log(LOG_EVIDENCE)

    assert lookup == {"1": "p0_buy_spy"}


def test_contract_fallback_only_when_unambiguous():
    lookup = extract_signal_ids_from_contract(CONTRACT_PAYLOAD)

    assert lookup == {"SPY": "p0_buy_spy"}


def test_contract_fallback_skips_ambiguous_symbols():
    payload = {
        "orders": [
            {"symbol": "SPY", "signal_id": "a"},
            {"symbol": "SPY", "signal_id": "b"},
        ]
    }

    assert extract_signal_ids_from_contract(payload) == {}


def test_unresolved_signal_id_stays_empty():
    adapted = adapt_native_order_events(NATIVE_EVENTS)

    assert adapted[0]["signal_id"] == ""
    assert adapted[1]["signal_id"] == ""


# ══════════════════════════════════════════════════════════════════
# Downstream contract: mapper and ledger trade untouched and working
# ══════════════════════════════════════════════════════════════════
def test_canonical_event_passes_map_order_event():
    adapted = adapt_native_order_events(
        NATIVE_EVENTS, signal_lookup={"1": "p0_buy_spy"}
    )

    normalised = [map_order_event(event) for event in adapted]

    assert normalised[0]["status"] == "SUBMITTED"
    assert normalised[1]["status"] == "FILLED"
    assert normalised[1]["signal_id"] == "p0_buy_spy"
    assert normalised[1]["symbol"] == "SPY"
    assert normalised[1]["fill_price"] == pytest.approx(144.78172417)


def test_filled_canonical_event_becomes_ledger_trade():
    adapted = adapt_native_order_events(
        NATIVE_EVENTS, signal_lookup={"1": "p0_buy_spy"}
    )

    trade = order_event_to_ledger_trade(adapted[1])

    assert trade.symbol == "SPY"
    assert trade.quantity == Decimal("100")
    assert trade.price == Decimal("144.78172417")


def test_unfilled_canonical_event_rejected_by_ledger():
    adapted = adapt_native_order_events(
        NATIVE_EVENTS, signal_lookup={"1": "p0_buy_spy"}
    )

    with pytest.raises(ValueError):
        order_event_to_ledger_trade(adapted[0])


# ══════════════════════════════════════════════════════════════════
# load_events boundary: native JSON vs canonical JSON vs raw log
# ══════════════════════════════════════════════════════════════════
def test_load_events_routes_native_json(tmp_path: Path):
    run_dir = tmp_path / "2026-09-30_14-15-35"
    run_dir.mkdir()
    (run_dir / "1350234380-order-events.json").write_text(
        json.dumps(NATIVE_EVENTS), encoding="utf-8"
    )
    (run_dir / "1350234380-log.txt").write_text(LOG_EVIDENCE, encoding="utf-8")

    events, source = load_events(run_dir / "1350234380-order-events.json")

    assert source == "lean-native-json"
    assert events[1]["signal_id"] == "p0_buy_spy"
    assert events[1]["status"] == "FILLED"


def test_load_events_native_json_contract_fallback(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "order-events.json").write_text(
        json.dumps(NATIVE_EVENTS), encoding="utf-8"
    )
    # No log evidence at all; the contract sits one directory up.
    (tmp_path / "strategy_contract.json").write_text(
        json.dumps(CONTRACT_PAYLOAD), encoding="utf-8"
    )

    events, source = load_events(run_dir / "order-events.json")

    assert source == "lean-native-json"
    assert events[1]["signal_id"] == "p0_buy_spy"     # symbol fallback
    assert events[1]["order_id"] == "1"


def test_load_events_native_json_unresolved_signal(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "order-events.json").write_text(
        json.dumps(NATIVE_EVENTS), encoding="utf-8"
    )
    # No log, no contract anywhere near: the gap must stay visible.

    events, _source = load_events(run_dir / "order-events.json")

    assert events[1]["signal_id"] == ""


def test_load_events_still_routes_canonical_json(tmp_path: Path):
    canonical = [{"type": "ORDER_EVENT", "order_id": "1", "status": "FILLED"}]
    path = tmp_path / "events.json"
    path.write_text(json.dumps(canonical), encoding="utf-8")

    events, source = load_events(path)

    assert source == "json"
    assert events == canonical


def test_load_events_still_routes_raw_log(tmp_path: Path):
    path = tmp_path / "lean-live.log"
    path.write_text(LOG_EVIDENCE, encoding="utf-8")

    events, source = load_events(path)

    assert source == "lean-log"
    assert parse_lean_debug_log(LOG_EVIDENCE)[0]["signal_id"] == "p0_buy_spy"
