"""Paper Trading ← PaperMarketFeed adapter (Commit 009 §13 / §18).

Commit 009 explicitly does **not** build a second Paper engine::

    PaperTradingSession          (existing engine, unchanged)
           │
           ├── signal
           ├── order
           ├── execution
           └── position
                  ↑
        PaperMarketFeedAdapter

``apps.runtime.paper_trading.PaperTradingSession`` already runs the
official engine chain, ledger, metrics and virtual accounting.  All
Commit 009 adds is the *data* underneath it, through two seams:

*   :class:`PaperMarketFeedAdapter` implements the engine's
    ``MarketFeed`` protocol (``quote(symbol) -> float``) on top of the
    real market pipeline, and additionally exposes the book-aware
    ``fill_price`` plus the ``check_order`` gate.
*   :class:`RealMarketPaperSession` subclasses ``PaperTradingSession``
    overriding exactly two hooks — ``_exec_price`` (§5 book pricing)
    and ``process`` (§8/§10/§11 order gate) — leaving the engine
    chain, accounting and metrics untouched.

Strategy logic is not modified and never sees any of this: it only
ever receives normal market data.
"""
from __future__ import annotations

import logging
from typing import Optional

from apps.runtime.paper_trading import PaperTradingSession, SignalSpec
from services.market_data.paper import (
    DISCLAIMER,
    FillPriceSource,
    PaperFeedError,
    PaperMarketFeed,
    PaperOrderDecision,
    paper_market_feed,
)

logger = logging.getLogger(__name__)

__all__ = [
    "PaperMarketFeedAdapter",
    "RealMarketPaperSession",
    "DISCLAIMER",
]


class PaperMarketFeedAdapter:
    """Adapts :class:`PaperMarketFeed` to the ``MarketFeed`` protocol.

    ``quote()`` returns the mid price (the engine uses it for signal
    reference and equity valuation); ``fill_price()`` returns the §5
    book price used for simulated execution.
    """

    def __init__(
        self,
        feed: Optional[PaperMarketFeed] = None,
        *,
        fallback_price: float = 0.0,
        strict: bool = False,
    ) -> None:
        self._feed = feed or paper_market_feed
        self._fallback = float(fallback_price)
        # strict=True surfaces a lookahead/block instead of falling
        # back to the last known price (used by the test gate).
        self._strict = strict
        self._last_good: dict[str, float] = {}
        self._last_error: Optional[str] = None

    # ── feed access ────────────────────────────────────────────

    @property
    def feed(self) -> PaperMarketFeed:
        return self._feed

    @property
    def disclaimer(self) -> str:
        return DISCLAIMER

    @property
    def last_error(self) -> Optional[str]:
        """Why the most recent ``quote()`` fell back (§17)."""
        return self._last_error

    # ── MarketFeed protocol ────────────────────────────────────

    def quote(self, symbol: str) -> float:
        """Latest mid price for ``symbol`` (valuation / reference).

        Never raises mid-run: a missing quote falls back to the last
        known price so equity valuation cannot explode, while
        ``last_error`` records the §17 reason.
        """
        quote = self._feed.latest_quote(symbol)
        if quote is None:
            self._last_error = PaperFeedError.QUOTE_UNAVAILABLE.value
            return self._last_good.get(symbol, self._fallback)
        mid = (quote.bid + quote.ask) / 2 if quote.bid > 0 and quote.ask > 0 else quote.last
        price = float(mid)
        self._last_good[symbol] = price
        self._last_error = None
        return price

    # ── book-aware pricing (§5) ────────────────────────────────

    def fill_price(self, symbol: str, side: str) -> float:
        """BUY → ASK, SELL → BID, fallback LAST (§5)."""
        price, _source = self._feed.fill_price(symbol, side)
        return float(price)

    def fill_price_with_source(
        self, symbol: str, side: str
    ) -> tuple[float, FillPriceSource]:
        price, source = self._feed.fill_price(symbol, side)
        return float(price), source

    # ── order gate (§8 / §10 / §11 / §17) ──────────────────────

    def check_order(
        self,
        symbol: str,
        *,
        side: str = "BUY",
        quantity: Optional[int] = None,
        order_timestamp=None,
    ) -> PaperOrderDecision:
        return self._feed.check_order(
            symbol, side=side, quantity=quantity, order_timestamp=order_timestamp
        )

    def preview_fill(
        self, symbol: str, side: str, quantity: int, order_timestamp=None
    ) -> PaperOrderDecision:
        return self._feed.preview_fill(
            symbol, side, quantity, order_timestamp=order_timestamp
        )

    # ── view (§12 / §14) ───────────────────────────────────────

    def status(self, symbols=None) -> dict:
        payload = self._feed.status(symbols)
        payload["last_error"] = self._last_error
        return payload

    def state(self) -> str:
        return self._feed.state.value


class RealMarketPaperSession(PaperTradingSession):
    """``PaperTradingSession`` fed by real A-share market data (§13).

    Only the two seams Commit 009 requires are overridden::

        _exec_price  → book-aware fill price (§5)
        process      → lot size / quality / session gate (§8/§10/§11)

    Everything else — pipeline, risk, ledger, accounting, metrics —
    is the existing engine, unchanged.
    """

    def __init__(
        self,
        feed: Optional[PaperMarketFeedAdapter] = None,
        *,
        account=None,
        reject_pct: float = 0.0,
        error_pct: float = 0.0,
        seed: int = 42,
    ) -> None:
        # Phase 1 real-data runs must not inject synthetic reject /
        # error profiles: a rejection now means a real data reason.
        adapter = feed or PaperMarketFeedAdapter()
        self.adapter = adapter
        self.decisions: list[PaperOrderDecision] = []
        # slippage lives in PaperFeedConfig (§6), not in the session
        super().__init__(
            adapter,
            account=account,
            reject_pct=reject_pct,
            error_pct=error_pct,
            slippage_bps=0.0,
            seed=seed,
        )

    # ── seam 1: fill price (§5) ────────────────────────────────

    def _exec_price(self, symbol: str, side: str) -> float:
        """Price the fill from the real book, not from a mid + guess."""
        return self.adapter.fill_price(symbol, side)

    # ── seam 2: order gate (§8/§10/§11/§17) ────────────────────

    def process(self, spec: SignalSpec) -> dict:
        """Gate the order on real data before it reaches the engine.

        A blocked order never enters the pipeline: it is recorded with
        its §17 reason and reported as rejected, so every Paper block
        leaves a trace and none of them silently become a fill.
        """
        decision = self.adapter.check_order(
            spec.symbol, side=spec.side, quantity=spec.quantity
        )
        self.decisions.append(decision)
        if not decision.allowed:
            logger.info(
                "paper order blocked: %s %s %s — %s",
                spec.side,
                spec.quantity,
                spec.symbol,
                decision.reason,
            )
            return {
                "rejected": True,
                "reason": decision.reason,
                "detail": decision.detail,
                "latency_total_us": 0.0,
            }
        return super().process(spec)

    # ── view (§12 / §14) ───────────────────────────────────────

    def blocked_decisions(self) -> list[dict]:
        """Every blocked order with its reason (audit view, §17)."""
        return [d.as_dict() for d in self.decisions if not d.allowed]

    def status(self, symbols=None) -> dict:
        return self.adapter.status(symbols)

    def report(self) -> dict:
        payload = super().report()
        payload["environment"] = "PAPER"
        payload["disclaimer"] = DISCLAIMER
        payload["feed_state"] = self.adapter.state()
        payload["blocked_orders"] = len(self.blocked_decisions())
        return payload
