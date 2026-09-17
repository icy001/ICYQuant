"""Shadow Trading service — the Commit 016 runtime façade.

Wires the §2 core chain onto the already-committed infrastructure::

    market data (Redis/merge, 007/008) → PaperMarketFeed gate (009)
        → ShadowGate ring (§24) → ShadowExecution (§5)
        → ShadowPositionBook / ShadowAccount / ShadowPnL
        → ShadowEventLedger (§19)

The broker side stays **read-only** (§15): an
:class:`AccountSyncReference` exposes exactly the account-service
queries Shadow needs (is it blocking new orders? what are the broker
positions for the comparison view?) and nothing else.  There is no
reference — symbolically or literally — to any broker order API.

A process-wide singleton is available via :func:`get_shadow_service`
(lazily built, swappable for tests via :func:`set_shadow_service`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from services.execution.shadow.shadow_execution import ShadowExecution
from services.execution.shadow.shadow_order import (
    OrderIntent,
    ShadowOrder,
    ShadowOrderStatus,
)
from services.market_data.paper import paper_market_feed
from services.shadow.shadow_account import ShadowAccount
from services.shadow.shadow_config import ShadowConfig
from services.shadow.shadow_gate import ShadowGate
from services.shadow.shadow_ledger import ShadowEventLedger, ShadowEventType
from services.shadow.shadow_pnl import ShadowPnL
from services.shadow.shadow_position import ShadowPositionBook
from services.trading.mode import TradingMode

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _feed_state(feed) -> str:
    state = getattr(feed, "state", None)
    if state is None:
        return "UNKNOWN"
    return str(getattr(state, "value", state))


class AccountSyncReference:
    """Read-only broker reference (§15) — queries only, never orders.

    Every query is fail-closed: an account service that cannot answer
    blocks new Shadow orders instead of waving them through.
    """

    def __init__(self, service=None) -> None:
        self._service = service

    def _svc(self):
        if self._service is None:
            # Local import keeps the domain import graph clean.
            from services.account.sync.service import account_service

            self._service = account_service
        return self._service

    def new_orders_blocked(self) -> bool:
        """Account-sync ERROR or reconciliation MISMATCH → True."""
        try:
            return bool(self._svc().new_orders_blocked())
        except Exception:  # noqa: BLE001 — fail-closed (§13)
            logger.exception("shadow: account reference query failed")
            return True

    def status(self) -> dict:
        try:
            status = self._svc().status() or {}
        except Exception:  # noqa: BLE001
            return {"available": False, "status": "UNAVAILABLE"}
        status.setdefault("available", True)
        return status

    def positions(self) -> list[dict]:
        """Aggregate broker positions (symbol, quantity) across accounts."""
        rows: list[dict] = []
        try:
            svc = self._svc()
            accounts = svc.accounts() or []
        except Exception:  # noqa: BLE001
            return rows
        for account in accounts:
            account_id = self._account_id(account)
            if account_id is None:
                continue
            try:
                for pos in svc.positions(account_id) or []:
                    symbol = getattr(pos, "symbol", None)
                    quantity = getattr(pos, "quantity", None)
                    if symbol is None or quantity is None:
                        continue
                    rows.append(
                        {
                            "account_id": account_id,
                            "symbol": str(symbol),
                            "quantity": int(quantity),
                        }
                    )
            except Exception:  # noqa: BLE001 — read-only, best effort
                logger.warning(
                    "shadow: broker positions unavailable for %s", account_id
                )
        return rows

    @staticmethod
    def _account_id(account) -> Optional[str]:
        if isinstance(account, dict):
            raw = account.get("account_id")
        else:
            raw = getattr(account, "account_id", None)
        return str(raw) if raw else None


class ShadowTradingService:
    """Everything a Shadow session needs behind one façade."""

    def __init__(
        self,
        *,
        config: Optional[ShadowConfig] = None,
        feed=None,
        account_reference=None,
        clock=None,
        ledger: Optional[ShadowEventLedger] = None,
    ) -> None:
        self._cfg = config or ShadowConfig.from_env()
        self._feed = feed if feed is not None else paper_market_feed
        self._clock = clock or _utc_now
        self._ledger = ledger or ShadowEventLedger(self._cfg.ledger_path)
        self.account = ShadowAccount(self._cfg.initial_capital)
        self.position_book = ShadowPositionBook()
        self.pnl_tracker = ShadowPnL(self._cfg.initial_capital)
        self.gate = ShadowGate(
            feed=self._feed,
            account=self.account,
            positions=self.position_book,
            mode=TradingMode.SHADOW,
            account_reference=account_reference,
            config=self._cfg,
            clock=self._clock,
        )
        self.execution = ShadowExecution(
            gate=self.gate,
            feed=self._feed,
            account=self.account,
            positions=self.position_book,
            config=self._cfg,
            ledger=self._ledger,
            clock=self._clock,
        )
        self._running = False
        self._started_at: Optional[datetime] = None

    # ── identity / safety ──────────────────────────────────────

    @property
    def mode(self) -> TradingMode:
        return TradingMode.SHADOW

    @property
    def real_orders_enabled(self) -> bool:
        """Always False — the §22/§23 banner is a property of the design."""
        return False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def config(self) -> ShadowConfig:
        return self._cfg

    # ── session lifecycle ──────────────────────────────────────

    def start(self, *, replay: bool = True) -> dict:
        """Start the session, resuming persisted state (§14)."""
        if self._running:
            return self.status()
        replayed = 0
        if replay and self._ledger.persist_path is not None:
            events = self._ledger.load_and_adopt()
            if events:
                self.execution.replay(events)
                replayed = len(events)
        self._running = True
        self._started_at = self._clock()
        self._ledger.append(
            ShadowEventType.SESSION_STARTED,
            payload={"replayed_events": replayed},
            timestamp=self._started_at,
        )
        return self.status()

    def stop(self) -> dict:
        if self._running:
            self._ledger.append(
                ShadowEventType.SESSION_STOPPED,
                payload={},
                timestamp=self._clock(),
            )
        self._running = False
        return self.status()

    # ── trading ────────────────────────────────────────────────

    def record_signal(self, payload: dict) -> None:
        """Log the strategy signal that precedes an intent (§19)."""
        self._ledger.append(ShadowEventType.SIGNAL, payload=payload)

    def submit_intent(self, intent: OrderIntent) -> ShadowOrder:
        """Intent → gate → (simulated) execution, fully traced (§19)."""
        self._ledger.append(
            ShadowEventType.ORDER_INTENT,
            payload=intent.as_dict(),
            timestamp=intent.timestamp or self._clock(),
        )
        return self.execution.submit(intent)

    # ── views ──────────────────────────────────────────────────

    def status(self) -> dict:
        ref = self._account_reference
        return {
            "mode": self.mode.value,
            "real_orders_enabled": self.real_orders_enabled,
            "running": self._running,
            "started_at": (
                self._started_at.isoformat() if self._started_at else None
            ),
            "feed": {
                "state": _feed_state(self._feed),
                "source": str(getattr(self._feed, "source", "LIVE")),
            },
            "account_reference": (
                ref.status() if ref is not None else {"configured": False}
            ),
            "counts": {
                "orders": self.execution.order_count,
                "fills": self.execution.fill_count,
                "rejected": sum(
                    1
                    for o in self.execution.orders()
                    if o.status == ShadowOrderStatus.REJECTED.value
                ),
                "events": self._ledger.count(),
            },
            "config": self._cfg.as_dict(),
        }

    def orders(self, limit: Optional[int] = None) -> list[dict]:
        return [o.as_dict() for o in self.execution.orders(limit=limit)]

    def fills(self, limit: Optional[int] = None) -> list[dict]:
        rows = [f.as_dict() for f in self.execution.get_fills()]
        return rows[-limit:] if limit else rows

    def positions(self) -> list[dict]:
        """Open shadow positions, marked against the live book."""
        rows = []
        for pos in self.position_book.positions():
            price = self._mark_price(pos.symbol)
            row = pos.as_dict()
            row["market_price"] = str(price) if price is not None else None
            if price is not None:
                value = price * pos.quantity
                row["market_value"] = str(value)
                row["unrealized_pnl"] = str(
                    (price - pos.avg_cost) * pos.quantity
                )
            else:
                row["market_value"] = None
                row["unrealized_pnl"] = None
            rows.append(row)
        return rows

    def pnl(self) -> dict:
        """The §23 PnL card."""
        prices = {}
        for pos in self.position_book.positions():
            price = self._mark_price(pos.symbol)
            if price is not None:
                prices[pos.symbol] = price
        return self.pnl_tracker.snapshot(
            cash=self.account.cash,
            market_value=self.position_book.market_value(prices),
            realized_pnl=self.position_book.realized_pnl(),
            now=self._clock(),
        )

    def events(
        self,
        *,
        type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        return self._ledger.events(type=type, symbol=symbol, limit=limit)

    def broker_comparison(self) -> dict:
        """§18 — the read-only Shadow-vs-Broker view.

        The difference column is informational only: Shadow and the
        broker are separate ledgers by design, so a difference is NOT
        a reconciliation mismatch.
        """
        shadow_qty = {
            p.symbol: p.quantity for p in self.position_book.positions()
        }
        broker_qty: dict[str, int] = {}
        ref = self._account_reference
        broker_rows = ref.positions() if ref is not None else []
        for row in broker_rows:
            broker_qty[row["symbol"]] = (
                broker_qty.get(row["symbol"], 0) + int(row["quantity"])
            )
        symbols = sorted(set(shadow_qty) | set(broker_qty))
        return {
            "mode": self.mode.value,
            "real_orders_enabled": self.real_orders_enabled,
            "note": (
                "informational only — Shadow and the broker account are "
                "separate ledgers; a difference is not a reconciliation "
                "mismatch (Commit 016 §18)"
            ),
            "rows": [
                {
                    "symbol": s,
                    "shadow_quantity": shadow_qty.get(s, 0),
                    "broker_quantity": broker_qty.get(s, 0),
                    "difference": shadow_qty.get(s, 0)
                    - broker_qty.get(s, 0),
                }
                for s in symbols
            ],
        }

    # ── internals ──────────────────────────────────────────────

    @property
    def _account_reference(self):
        return self.gate._ref  # noqa: SLF001 — same-package façade

    def _mark_price(self, symbol: str) -> Optional[Decimal]:
        try:
            quote = self._feed.latest_quote(symbol)
        except Exception:  # noqa: BLE001 — marking is best effort
            return None
        if quote is None:
            return None
        last = getattr(quote, "last", None)
        if last is not None and last > 0:
            return Decimal(str(last))
        bid = getattr(quote, "bid", None)
        ask = getattr(quote, "ask", None)
        if bid and ask:
            return (Decimal(str(bid)) + Decimal(str(ask))) / 2
        return Decimal(str(last)) if last else None


# ── process-wide singleton ─────────────────────────────────────

_shadow_service: Optional[ShadowTradingService] = None


def get_shadow_service() -> ShadowTradingService:
    global _shadow_service
    if _shadow_service is None:
        _shadow_service = ShadowTradingService(
            account_reference=AccountSyncReference()
        )
    return _shadow_service


def set_shadow_service(service: Optional[ShadowTradingService]) -> None:
    """Swap the singleton (tests / deliberate reconfiguration)."""
    global _shadow_service
    _shadow_service = service


__all__ = [
    "AccountSyncReference",
    "ShadowTradingService",
    "get_shadow_service",
    "set_shadow_service",
]
