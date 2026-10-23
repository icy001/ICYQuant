"""Shadow execution — simulated fills only, never a broker order (Commit 016 §5/§25).

This is the single execution module of Commit 016.  The §25 rule is
enforced structurally, not by configuration:

* it imports **no** broker module — there is no ``submit_order`` /
  ``BrokerOrderAdapter`` symbol anywhere in this package, and the
  safety test ``test_shadow_never_calls_broker_order`` verifies both
  the import graph and the runtime behaviour;
* the gate must be in ``TradingMode.SHADOW`` (constructing one in LIVE
  raises), and this engine re-asserts it in ``__init__``;
* every artifact it produces is namespaced ``SHD-`` / ``SHDF-`` so it
  can never masquerade as a broker order id.

Fill policy (§8) reuses the Commit 009 book pricing through the gate's
embedded paper decision; the §10 frictions (slippage / latency /
commission) are layered on top.  §9 no-lookahead is enforced with the
timestamp chain::

    signal_ts  ≤  quote.timestamp  ≤  execution_ts (= signal_ts + latency)
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from services.shadow.shadow_account import ShadowAccount, ShadowAccountError
from services.shadow.shadow_config import ShadowConfig
from services.shadow.shadow_ledger import ShadowEventLedger, ShadowEventType
from services.shadow.shadow_position import ShadowPositionBook
from services.trading.mode import TradingMode

from .shadow_fill import ShadowFill
from .shadow_order import OrderIntent, ShadowOrder, ShadowOrderStatus

logger = logging.getLogger(__name__)

_BPS = Decimal("10000")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_stamp(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.strftime("%Y%m%d")


class ShadowExecution:
    """Simulated execution engine behind the §5 interface::

        submit(intent) -> ShadowOrder
        cancel(order_id) -> ShadowOrder | None
        get_order(order_id) -> ShadowOrder | None
        get_fills(order_id=None) -> [ShadowFill]

    ``submit`` never raises for a blocked order — rejection is a
    first-class :class:`ShadowOrder` with a machine-readable reason.
    """

    def __init__(
        self,
        *,
        gate,
        feed,
        account: ShadowAccount,
        positions: ShadowPositionBook,
        config: Optional[ShadowConfig] = None,
        ledger: Optional[ShadowEventLedger] = None,
        clock=None,
    ) -> None:
        # §25 — the code-level mode assertion.
        if getattr(gate, "mode", None) is not TradingMode.SHADOW:
            raise ValueError(
                "ShadowExecution requires a SHADOW-mode gate — "
                "real (LIVE) execution is not implemented"
            )
        self._gate = gate
        self._feed = feed
        self._account = account
        self._positions = positions
        self._cfg = config or ShadowConfig()
        self._ledger = ledger or ShadowEventLedger()
        self._clock = clock or _utc_now
        self._orders: dict[str, ShadowOrder] = {}
        self._fills: list[ShadowFill] = []
        self._seq = 0

    # ── §5 interface ───────────────────────────────────────────

    def submit(self, intent: OrderIntent) -> ShadowOrder:
        now = self._clock()
        signal_ts = intent.timestamp or now
        decision = self._gate.evaluate(intent)
        order_id = self._next_id("SHD")
        order = ShadowOrder(
            order_id=order_id,
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=str(intent.side).upper(),
            quantity=int(intent.quantity),
            order_type=str(intent.order_type).upper(),
            strategy_id=intent.strategy_id,
            status=ShadowOrderStatus.ACCEPTED.value,
            created_at=now,
            signal_timestamp=signal_ts,
        )
        # Every gate verdict lands in the ledger (§19 RISK_DECISION).
        self._ledger.append(
            ShadowEventType.RISK_DECISION,
            payload={
                "symbol": intent.symbol,
                "order_id": order_id,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "checks": decision.as_dict()["checks"],
            },
            timestamp=now,
        )
        if not decision.allowed:
            rejected = replace(
                order,
                status=ShadowOrderStatus.REJECTED.value,
                reason=decision.reason,
            )
            self._orders[order_id] = rejected
            self._ledger.append(
                ShadowEventType.ORDER_REJECTED,
                payload=rejected.as_dict(),
                timestamp=now,
            )
            logger.info(
                "shadow order rejected: %s %s %s — %s",
                rejected.side,
                rejected.quantity,
                rejected.symbol,
                rejected.reason,
            )
            return rejected

        self._orders[order_id] = order
        self._ledger.append(
            ShadowEventType.ORDER_ACCEPTED,
            payload=order.as_dict(),
            timestamp=now,
        )
        try:
            fills = self._simulate_fills(order, decision, signal_ts, now)
        except ShadowAccountError as exc:
            # The gate pre-checks everything this guards; a raise here
            # means the world moved between gate and fill — record the
            # honest rejection instead of a half-fill.
            rejected = replace(
                order, status=ShadowOrderStatus.REJECTED.value, reason=exc.code
            )
            self._orders[order_id] = rejected
            self._ledger.append(
                ShadowEventType.ORDER_REJECTED,
                payload=rejected.as_dict(),
                timestamp=now,
            )
            return rejected

        total_qty = sum(f.quantity for f in fills)
        total_notional = sum((f.notional for f in fills), Decimal("0"))
        filled = replace(
            order,
            status=ShadowOrderStatus.FILLED.value,
            filled_quantity=total_qty,
            avg_fill_price=(total_notional / total_qty if total_qty else None),
        )
        self._orders[order_id] = filled
        self._ledger.append(
            ShadowEventType.PNL_UPDATE,
            payload={
                "order_id": order_id,
                "cash": str(self._account.cash),
                "realized_pnl": str(self._positions.realized_pnl()),
            },
            timestamp=now,
        )
        return filled

    def cancel(self, order_id: str) -> Optional[ShadowOrder]:
        """Cancel an open order.

        Because MARKET orders fill synchronously inside ``submit``,
        a cancellable (ACCEPTED, unfilled) order cannot be observed
        from outside; the branch exists so the contract is honest.
        """
        order = self._orders.get(order_id)
        if order is None or order.is_terminal:
            return order
        cancelled = replace(order, status=ShadowOrderStatus.CANCELLED.value)
        self._orders[order_id] = cancelled
        self._ledger.append(
            ShadowEventType.ORDER_CANCELLED,
            payload=cancelled.as_dict(),
            timestamp=self._clock(),
        )
        return cancelled

    def get_order(self, order_id: str) -> Optional[ShadowOrder]:
        return self._orders.get(order_id)

    def get_fills(self, order_id: Optional[str] = None) -> list[ShadowFill]:
        if order_id is None:
            return list(self._fills)
        return [f for f in self._fills if f.order_id == order_id]

    def orders(self, limit: Optional[int] = None) -> list[ShadowOrder]:
        rows = list(self._orders.values())
        return rows[-limit:] if limit else rows

    @property
    def order_count(self) -> int:
        return len(self._orders)

    @property
    def fill_count(self) -> int:
        return len(self._fills)

    # ── persistence (§14) ──────────────────────────────────────

    def replay(self, events: list[dict]) -> None:
        """Rebuild orders / fills / ledger state from a persisted stream."""
        for ev in events:
            etype = str(ev.get("type", "")).upper()
            payload = ev.get("payload", {}) or {}
            try:
                if etype in (
                    ShadowEventType.ORDER_ACCEPTED.value,
                    ShadowEventType.ORDER_REJECTED.value,
                ):
                    order = ShadowOrder.from_dict(payload)
                    self._orders[order.order_id] = order
                elif etype == ShadowEventType.FILL.value:
                    fill = ShadowFill.from_dict(payload)
                    self._fills.append(fill)
                    self._account.apply_fill(
                        fill.side, fill.quantity, fill.price, fill.commission
                    )
                    self._positions.apply_fill(
                        fill.symbol, fill.side, fill.quantity, fill.price
                    )
            except (KeyError, ValueError, ArithmeticError):
                logger.warning(
                    "shadow replay: skipping corrupt %s event", etype
                )
        # Aggregate replayed fills back onto their orders.
        for order_id, order in list(self._orders.items()):
            fills = [f for f in self._fills if f.order_id == order_id]
            if not fills:
                continue
            qty = sum(f.quantity for f in fills)
            notional = sum((f.notional for f in fills), Decimal("0"))
            self._orders[order_id] = replace(
                order,
                status=ShadowOrderStatus.FILLED.value,
                filled_quantity=qty,
                avg_fill_price=notional / qty if qty else None,
            )
        self._sync_sequence()

    def _sync_sequence(self) -> None:
        best = 0
        for ident in [o.order_id for o in self._orders.values()] + [
            f.fill_id for f in self._fills
        ]:
            tail = ident.rsplit("-", 1)[-1]
            if tail.isdigit():
                best = max(best, int(tail))
        self._seq = best

    # ── fill simulation (§8 / §9 / §10) ────────────────────────

    def _simulate_fills(
        self, order: ShadowOrder, decision, signal_ts: datetime, now: datetime
    ) -> list[ShadowFill]:
        quote = self._feed.latest_quote(order.symbol)
        if quote is None:
            raise ShadowAccountError(
                "SHADOW_QUOTE_UNAVAILABLE",
                f"no quote for {order.symbol} at execution time",
            )
        # §9 — simulated latency pushes the fill into the future of
        # the signal; the quote used must already be visible then.
        execution_ts = signal_ts + timedelta(
            milliseconds=self._cfg.execution_latency_ms
        )
        if quote.timestamp > execution_ts:
            raise ShadowAccountError(
                "SHADOW_LOOKAHEAD_VIOLATION",
                f"quote {quote.timestamp.isoformat()} is newer than the "
                f"simulated execution time {execution_ts.isoformat()}",
            )

        reference = Decimal(decision.paper_decision.fill_price)
        source = decision.paper_decision.fill_price_source or "LAST"
        slip = Decimal(str(self._cfg.slippage_bps)) / _BPS
        comm_rate = Decimal(str(self._cfg.commission_bps)) / _BPS
        side_u = str(order.side).upper()
        if side_u not in ("BUY", "SELL"):
            raise ShadowAccountError(
                "SHADOW_INVALID_SIDE", f"unsupported side {order.side!r}"
            )

        fills: list[ShadowFill] = []
        for clip_qty in self._clips(order.quantity):
            if side_u == "BUY":
                price = reference * (1 + slip)
            else:
                price = reference * (1 - slip)
            notional = price * clip_qty
            commission = (notional * comm_rate).quantize(Decimal("0.01"))
            fill = ShadowFill(
                fill_id=self._next_id("SHDF"),
                order_id=order.order_id,
                symbol=order.symbol,
                side=side_u,
                quantity=clip_qty,
                price=price,
                price_source=source,
                market_timestamp=quote.timestamp,
                execution_timestamp=execution_ts,
                signal_timestamp=signal_ts,
                slippage_bps=self._cfg.slippage_bps,
                commission=commission,
            )
            self._fills.append(fill)
            self._ledger.append(
                ShadowEventType.FILL,
                payload=fill.as_dict(),
                timestamp=now,
            )
            self._account.apply_fill(side_u, clip_qty, price, commission)
            position = self._positions.apply_fill(
                order.symbol, side_u, clip_qty, price
            )
            self._ledger.append(
                ShadowEventType.POSITION_UPDATE,
                payload=position.as_dict(),
                timestamp=now,
            )
            fills.append(fill)
        return fills

    def _clips(self, quantity: int) -> list[int]:
        """§10 — one fill by default; clipped (partial) fills on request."""
        clip = int(self._cfg.max_clip_quantity)
        if clip <= 0 or quantity <= clip:
            return [quantity]
        sizes = [clip] * (quantity // clip)
        if quantity % clip:
            sizes.append(quantity % clip)
        return sizes

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{_day_stamp(self._clock())}-{self._seq:06d}"


__all__ = ["ShadowExecution"]
