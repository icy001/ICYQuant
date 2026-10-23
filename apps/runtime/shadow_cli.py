"""Commit 016 Shadow Trading CLI.

::

    python -m apps.runtime shadow                       # run the session
    python -m apps.runtime shadow --symbols 159852,159559 --capital 1000000
    python -m apps.runtime shadow status
    python -m apps.runtime shadow stop

Safety (§21): the ``shadow`` command structurally cannot accept
``--live`` / ``--real-order`` / ``--broker-order`` — argparse rejects
unknown flags, and the intent is documented in the parser epilog.

The demo signal source (``strategy_id="shadow-demo"``) exists only to
exercise the chain end-to-end until the strategy engine is wired into
runtime; every intent still passes the full §24 gate.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from pathlib import Path

from services.execution.shadow.shadow_order import OrderIntent, new_intent_id
from services.shadow.service import (
    AccountSyncReference,
    ShadowTradingService,
)
from services.shadow.shadow_config import ShadowConfig

#: Demo signal quantity — lot alignment itself is validated by the
#: Instrument Master inside the Commit 009 gate (§11), never assumed.
_DEMO_QUANTITY = 100
_DEMO_STRATEGY = "shadow-demo"


def _state_dir() -> Path:
    path = Path(os.getenv("SHADOW_STATE_DIR", "data/shadow"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_state() -> dict:
    path = _state_dir() / "runtime.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(payload: dict) -> None:
    (_state_dir() / "runtime.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _stop_requested() -> bool:
    return bool(_read_state().get("stop_requested"))


def _build_service(args) -> ShadowTradingService:
    config = ShadowConfig(
        initial_capital=Decimal(str(args.capital)),
        ledger_path=str(_state_dir() / "events.jsonl"),
    )
    return ShadowTradingService(
        config=config, account_reference=AccountSyncReference()
    )


def _ensure_market_data(
    service: ShadowTradingService, symbols: list[str]
) -> None:
    """Subscribe the shared paper feed so the gate sees live quotes."""
    try:
        from services.market_data import market_data_service

        market_data_service.ensure_feed()
    except Exception:  # noqa: BLE001 — offline runs still start the session
        print("WARN: live market data unavailable — the gate will block fills")
    try:
        service._feed.subscribe(symbols)  # noqa: SLF001 — façade boundary
    except Exception:  # noqa: BLE001
        print("WARN: paper feed subscription failed — check the symbol universe")


def run_shadow_session(args) -> int:
    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    if not symbols:
        print("ERROR: no symbols given")
        return 2

    service = _build_service(args)
    _ensure_market_data(service, symbols)
    service.start()

    max_signals = max(0, int(getattr(args, "signals", 20)))
    _write_state(
        {
            "mode": "SHADOW",
            "real_orders_enabled": False,
            "running": True,
            "stop_requested": False,
            "pid": os.getpid(),
            "symbols": symbols,
            "capital": str(service.config.initial_capital),
        }
    )
    print(
        f"SHADOW session started — mode=SHADOW real_orders=DISABLED "
        f"symbols={','.join(symbols)} capital={service.config.initial_capital}"
    )

    submitted = 0
    cycle = 0
    try:
        while True:
            if _stop_requested():
                print("stop requested — shutting down")
                break
            if max_signals and submitted >= max_signals:
                print(f"signal budget reached ({max_signals})")
                break
            for symbol in symbols:
                if max_signals and submitted >= max_signals:
                    break
                if service.position_book.quantity(symbol) > 0:
                    continue
                service.record_signal(
                    {
                        "symbol": symbol,
                        "side": "BUY",
                        "quantity": _DEMO_QUANTITY,
                        "strategy_id": _DEMO_STRATEGY,
                        "note": "demo signal source (strategy engine not wired yet)",
                    }
                )
                order = service.submit_intent(
                    OrderIntent(
                        intent_id=new_intent_id(),
                        symbol=symbol,
                        side="BUY",
                        quantity=_DEMO_QUANTITY,
                        strategy_id=_DEMO_STRATEGY,
                    )
                )
                submitted += 1
                if order.status == "FILLED":
                    fills = service.execution.get_fills(order.order_id)
                    price = fills[0].price if fills else "?"
                    print(
                        f"  SHADOW FILL  {order.symbol} BUY "
                        f"{order.quantity} @ {price} ({order.order_id})"
                    )
                else:
                    print(
                        f"  SHADOW REJECT {order.symbol} BUY "
                        f"{order.quantity} — {order.reason}"
                    )
            cycle += 1
            status = service.status()
            pnl = service.pnl()
            if getattr(args, "json", False):
                print(
                    json.dumps(
                        {
                            "cycle": cycle,
                            "orders": status["counts"]["orders"],
                            "fills": status["counts"]["fills"],
                            "feed": status["feed"]["state"],
                            "equity": pnl["equity"],
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                print(
                    f"  cycle {cycle}: feed={status['feed']['state']} "
                    f"orders={status['counts']['orders']} "
                    f"fills={status['counts']['fills']} "
                    f"equity={pnl['equity']}"
                )
            time.sleep(max(0.5, float(getattr(args, "interval", 5.0))))
    except KeyboardInterrupt:
        print("interrupted — shutting down")

    service.stop()
    _write_state({**_read_state(), "running": False})
    pnl = service.pnl()
    print(
        f"SHADOW session stopped — orders={service.execution.order_count} "
        f"fills={service.execution.fill_count} equity={pnl['equity']} "
        f"total_pnl={pnl['total_pnl']}"
    )
    return 0


def _ledger_counts() -> dict:
    ledger_path = _state_dir() / "events.jsonl"
    counts: dict[str, int] = {}
    if not ledger_path.exists():
        return counts
    from services.shadow.shadow_ledger import ShadowEventLedger

    for ev in ShadowEventLedger(str(ledger_path)).load_and_adopt():
        key = ev.get("type", "?")
        counts[key] = counts.get(key, 0) + 1
    return counts


def shadow_status(args) -> int:
    state = _read_state()
    if not state:
        print("no shadow session recorded (run: python -m apps.runtime shadow)")
        return 0
    payload = {
        "mode": "SHADOW",
        "real_orders_enabled": False,
        "running": state.get("running", False),
        "stop_requested": state.get("stop_requested", False),
        "pid": state.get("pid"),
        "symbols": state.get("symbols", []),
        "capital": state.get("capital"),
        "events": _ledger_counts(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def shadow_stop(args) -> int:
    state = _read_state()
    if not state:
        print("no shadow session recorded — nothing to stop")
        return 0
    if not state.get("running"):
        print("shadow session is not running")
        return 0
    _write_state({**state, "stop_requested": True})
    print(
        f"stop requested for shadow session pid={state.get('pid')} "
        "— the run loop shuts down on its next cycle"
    )
    return 0
