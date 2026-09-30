"""K02 — Native LEAN order-events JSON → ICYQuant canonical events.

LEAN's own ``*-order-events.json`` export (written by the backtesting
result handler and by live deployments) uses camelCase keys, lowercase
enum statuses and a ``symbol`` field polluted with the SID:

    {"orderId": 1, "status": "filled", "fillPrice": 144.78172417,
     "fillQuantity": 100.0, "direction": "buy", "symbolValue": "SPY", ...}

ICYQuant's internal event contract is snake_case with normalised
statuses.  This module is the *only* place where that translation
happens, so ``map_order_event`` and everything downstream of it stays
untouched — regardless of whether the events came from a backtest, a
paper deployment or a live one.

``signal_id`` recovery (ties into the K01 fix): native events know
nothing about ICYQuant signals, so the adapter takes an explicit
``order_id -> signal_id`` lookup built from the run's own log evidence
(``ICYQUANT_ORDER_EVENT order_id=.. signal_id=..`` lines) plus an
optional symbol-level fallback from ``strategy_contract.json``.  When
neither resolves an order the signal_id stays **empty** — never guessed
at — so downstream gates surface the gap loudly instead of silently
reconciling the wrong signal.

Field mapping (frozen in the K02 decision, completed in K03):

    orderId        -> order_id
    status         -> status            (normalised, see _STATUS_ALIASES)
    symbolValue    -> symbol            (fallback: symbolPermtick, symbol)
    fillQuantity   -> filled_quantity   (signed by ``direction``: sell < 0)
    fillPrice      -> fill_price        (None when not a positive fill)
    quantity       -> quantity          (signed by ``direction``)
    orderFeeAmount -> commission/message
    time           -> timestamp         (epoch seconds -> ISO 8601 UTC)
    signal_id      -> recovered from log evidence / contract fallback

════════════════════════════════════════════════════════════════════
ICYQuant canonical ORDER_EVENT contract (K03, frozen)
════════════════════════════════════════════════════════════════════

Required fields (always present, never null):

    type             "ORDER_EVENT"
    order_id         str — LEAN orderId, serialised
    status           str — one of NEW / SUBMITTED / PARTIALLY_FILLED /
                     FILLED / CANCELLED / REJECTED / UNKNOWN, always
                     upper-case; ``map_order_event`` must be able to
                     round-trip it unchanged.
    quantity         float|int — order quantity, signed: sell < 0
    filled_quantity  float|int — *cumulative filled quantity for this
                     event*, signed: sell < 0.  Native LEAN emits
                     ``fillQuantity`` always positive and carries the
                     direction in ``direction``; the adapter restores
                     the sign so reconciliation can compare directly
                     against ``StrategyIntent.signed_quantity``.

Optional fields (present when known, else None / 0 / ""):

    symbol           str|None — bare ticker (SID stripped); needed to
                     post a ledger trade.
    fill_price       float|None — positive fill price; None when the
                     event carries no fill (Submitted) or a zero price.
    commission       float — orderFeeAmount of the fill event; 0 by
                     default.  Posted to the ledger COMMISSION journal
                     by G08.
    message          str — human-readable detail ("order_fee=... USD").
    timestamp        str|None — ISO 8601 UTC.

signal_id evidence priority (frozen in K02, restated):

    (i)  ``order_id -> signal_id`` from the run's own ``*-log.txt``
         ``ICYQUANT_ORDER_EVENT`` lines (K01 guarantees the binding);
    (ii) ``symbol -> signal_id`` from ``strategy_contract.json``, only
         when the symbol carries exactly one intent;
    (iii) unresolved stays **empty** — never guessed; downstream gates
         surface the gap via their symbol fallback or an explicit FAIL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

__all__ = [
    "adapt_native_order_events",
    "extract_signal_ids_from_contract",
    "extract_signal_ids_from_log",
    "is_native_lean_order_events",
]

#: The log marker the algorithm emits per order event (K01 guarantees it
#: carries the signal_id from the very first Submitted event onwards).
_ORDER_EVENT_MARKER = "ICYQUANT_ORDER_EVENT"

#: Statuses LEAN serialises as the bare enum name, lower-cased, which do
#: not round-trip through ``LEAN_ORDER_STATUS_MAP`` without a hyphen fix.
_STATUS_ALIASES = {
    "PARTIALLYFILLED": "PARTIALLY_FILLED",
}


def is_native_lean_order_events(events: Iterable[Any]) -> bool:
    """True when ``events`` looks like LEAN's native order-events export.

    The signature is the camelCase ``orderId`` key on the first event;
    ICYQuant canonical events use ``order_id`` instead.
    """
    events = list(events)

    if not events:
        return False

    first = events[0]

    return isinstance(first, dict) and "orderId" in first


def extract_signal_ids_from_log(text: str) -> dict[str, str]:
    """Build ``order_id -> signal_id`` from the run's own log evidence.

    Only ``ICYQUANT_ORDER_EVENT order_id=.. signal_id=..`` lines count:
    they are the algorithm's runtime record of what it actually
    submitted, not what we hope it did.  First non-empty signal wins.
    """
    lookup: dict[str, str] = {}

    for line in text.splitlines():
        if _ORDER_EVENT_MARKER not in line:
            continue

        fields = _parse_kv(line.split(_ORDER_EVENT_MARKER, 1)[1])

        order_id = fields.get("order_id", "")
        signal_id = fields.get("signal_id", "")

        if order_id and signal_id and order_id not in lookup:
            lookup[order_id] = signal_id

    return lookup


def extract_signal_ids_from_contract(payload: Mapping[str, Any]) -> dict[str, str]:
    """Build a ``symbol -> signal_id`` fallback from the contract.

    A symbol maps only when exactly one intent targets it: multiple
    intents on the same symbol are ambiguous and, per the K02 decision,
    ambiguity resolves to *nothing* rather than a guess.
    """
    counts: dict[str, int] = {}
    signals: dict[str, str] = {}

    for intent in payload.get("orders") or payload.get("intents") or []:
        if not isinstance(intent, Mapping):
            continue

        symbol = str(intent.get("symbol") or "")
        signal_id = str(intent.get("signal_id") or "")

        if not symbol or not signal_id:
            continue

        counts[symbol] = counts.get(symbol, 0) + 1

        if counts[symbol] == 1:
            signals[symbol] = signal_id
        else:
            signals.pop(symbol, None)

    return signals


def adapt_native_order_events(
    events: Iterable[Mapping[str, Any]],
    *,
    signal_lookup: Optional[Mapping[str, str]] = None,
    symbol_signal_lookup: Optional[Mapping[str, str]] = None,
) -> list[dict[str, Any]]:
    """Translate native LEAN order events into ICYQuant canonical events.

    ``signal_lookup`` is the ``order_id -> signal_id`` evidence map;
    ``symbol_signal_lookup`` is the contract-derived fallback.  An order
    that neither resolves keeps an empty signal_id on purpose.
    """
    signal_lookup = signal_lookup or {}
    symbol_signal_lookup = symbol_signal_lookup or {}
    out: list[dict[str, Any]] = []

    for raw in events:
        order_id = str(raw.get("orderId", ""))

        symbol = (
            raw.get("symbolValue")
            or raw.get("symbolPermtick")
            or raw.get("symbol")
        )
        symbol = str(symbol).strip() if symbol else ""

        signal_id = signal_lookup.get(order_id) or symbol_signal_lookup.get(symbol, "")

        quantity = _to_float(raw.get("quantity"))
        direction = str(raw.get("direction") or "").strip().lower()

        if quantity is not None and direction == "sell":
            quantity = -abs(quantity)

        # K03: LEAN's native fillQuantity is always positive and carries
        # the side in ``direction``; the canonical contract promises a
        # signed quantity so G08 can compare against signed_quantity
        # without re-deriving the sign.
        filled_quantity = _to_float(raw.get("fillQuantity"))

        if filled_quantity is not None and direction == "sell":
            filled_quantity = -abs(filled_quantity)

        fill_price = _to_float(raw.get("fillPrice"))

        status = str(raw.get("status") or "").strip().upper()
        status = _STATUS_ALIASES.get(status, status)

        event: dict[str, Any] = {
            "type": "ORDER_EVENT",
            "order_id": order_id,
            "signal_id": signal_id,
            "symbol": symbol or None,
            "status": status,
            "quantity": quantity if quantity is not None else 0,
            "filled_quantity": filled_quantity or 0,
            "fill_price": fill_price,
            "timestamp": _epoch_to_iso(raw.get("time")),
        }

        fee = _to_float(raw.get("orderFeeAmount"))

        if fee is not None:
            event["commission"] = fee
            event["message"] = (
                f"order_fee={fee} {raw.get('orderFeeCurrency') or ''}".strip()
            )

        out.append(event)

    return out


# ── helpers ────────────────────────────────────────────────────────
def _parse_kv(segment: str) -> dict[str, str]:
    out: dict[str, str] = {}

    for token in segment.split():
        if "=" in token:
            key, _, value = token.partition("=")
            out[key.strip()] = value.strip()

    return out


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None

    return parsed if parsed > 0 else None


def _epoch_to_iso(value: Any) -> Optional[str]:
    seconds = _to_float(value)

    if seconds is None:
        return None

    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
