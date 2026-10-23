"""Replay market data source (Commit 012 §12 / §17).

Plugs the replay engine into the Commit 001 adapter contract *and* into
the Commit 009 Paper Market Feed, so neither knows replay exists::

    MockMarketDataAdapter     ─┐
    ReplayMarketDataAdapter   ─┼─► MarketDataAdapter        (001 contract)
    BrokerMarketDataAdapter   ─┘                    (Commit 014)

    ReplayMarketDataAdapter   ───► PaperMarketFeed          (§17)

§12 — never fabricate a quote
-----------------------------

Replay reconstructs **trades**, not a Level-1 book.  Every quote this
source produces therefore carries ``bid = ask = 0`` and a ``last`` taken
from the replayed bar's close.  Paper's ``fill_price`` already falls back
to LAST when no book is present, so pricing stays honest — and a
consumer that *needs* a book finds zeros rather than invented depths.

§17 — this is how Paper gets a REPLAY source
--------------------------------------------

``PaperMarketFeed`` reads through a duck-typed quote service
(``latest(symbol)`` / ``quality(symbol)``).  This class implements both,
which is the whole wiring story::

    feed = PaperMarketFeed(
        quote_service=adapter,       # ← replay instead of the live pipeline
        clock=lambda: engine.now,    # ← virtual clock, not wall clock (§26)
        source="REPLAY",
    )

Paper's session / lookahead guards then run against **virtual** time, so
"09:45" in a replay is judged exactly like 09:45 on the live day.

Import surface::

    from services.market_data.replay import ReplayMarketDataAdapter

    adapter = ReplayMarketDataAdapter(max_quotes=3)
    adapter.engine.start(["159852"], date="2026-09-10", speed=100)
    adapter.connect()
    adapter.subscribe(["159852"])
    for quote in adapter.stream():
        ...
"""
from __future__ import annotations

from typing import Iterator, Optional

from ..domain.bar import Bar
from ..domain.quote import MarketQuote
from .replay_engine import ReplayEngine, replay_engine
from .replay_state import ReplayBlockedError, ReplayError, ReplayState


class ReplayMarketDataAdapter:
    """Streams replayed events as trade-only quotes (001 + §17).

    Mirrors the surface of
    :class:`~services.market_data.adapters.mock.MockMarketDataAdapter`
    (``name`` / ``connected`` / ``connect`` / ``disconnect`` /
    ``subscribe`` / ``unsubscribe`` / ``stream``) plus the two methods
    :class:`~services.market_data.paper.paper_market_feed.PaperMarketFeed`
    needs from a quote service.
    """

    def __init__(
        self,
        engine: Optional[ReplayEngine] = None,
        *,
        max_quotes: Optional[int] = None,
    ) -> None:
        self._engine = engine or replay_engine
        self._connected = False
        self._subscribed: set[str] = set()
        self._max_quotes = max_quotes
        self._quote_count = 0

    # ── 001 contract ─────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "replay"

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def engine(self) -> ReplayEngine:
        return self._engine

    @property
    def quote_count(self) -> int:
        return self._quote_count

    @property
    def subscribed(self) -> list[str]:
        return sorted(self._subscribed)

    def connect(self) -> None:
        """Attach to a loaded replay window.

        There is nothing to dial: if no timeline is loaded there is
        nothing to stream, so we refuse with a typed error instead of
        yielding an empty feed that looks like a quiet market.
        """
        if self._connected:
            raise ReplayBlockedError(
                ReplayError.ALREADY_RUNNING, detail="adapter already connected"
            )
        if self._engine.events_total == 0:
            raise ReplayBlockedError(
                ReplayError.NOT_READY,
                detail="engine.load()/start() before adapter.connect()",
            )
        self._connected = True

    def disconnect(self) -> None:
        """Detach (safe to call when never connected)."""
        self._connected = False

    def subscribe(self, symbols: list[str]) -> None:
        """Restrict the stream to ``symbols`` (must be in the run)."""
        self._require_connected()
        run = self._engine.run
        known = set(run.symbols) if run else set()
        for symbol in symbols:
            code = str(symbol).strip()
            if not code:
                continue
            if known and code not in known:
                raise ReplayBlockedError(
                    ReplayError.UNKNOWN_SYMBOL,
                    symbol=code,
                    detail="symbol is not part of the loaded replay window",
                )
            self._subscribed.add(code)

    def unsubscribe(self, symbols: list[str]) -> None:
        """Stop streaming ``symbols`` (no-op for unknown symbols)."""
        for symbol in symbols:
            self._subscribed.discard(str(symbol).strip())

    def stream(self) -> Iterator[MarketQuote]:
        """Yield quotes for the subscribed symbols until the run ends.

        The generator drives the engine, so §6 pacing and the §5 virtual
        clock advance together with delivery.
        """
        self._require_connected()
        if self._engine.state in (
            ReplayState.COMPLETED,
            ReplayState.STOPPED,
        ):
            raise ReplayBlockedError(
                ReplayError.TERMINATED,
                detail="run is over — reset()/load() to stream again",
            )
        if not self._subscribed:
            raise ReplayBlockedError(
                ReplayError.NOT_READY, detail="subscribe() before stream()"
            )
        for event in self._engine.frames():
            if event.symbol not in self._subscribed:
                continue
            if (
                self._max_quotes is not None
                and self._quote_count >= self._max_quotes
            ):
                return
            self._quote_count += 1
            yield event.as_quote()

    # ── §17 quote-service surface (PaperMarketFeed) ──────────────

    def latest(self, symbol: str) -> Optional[MarketQuote]:
        """Current quote for ``symbol`` — the newest knowable instant.

        Returns ``None`` before the first event for that symbol, which is
        exactly how a live feed behaves outside its first tick.
        """
        event = self._engine.current(str(symbol).strip())
        if event is None:
            return None
        return event.as_quote()

    def quality(self, symbol: str) -> Optional[dict]:
        """Quality view for ``symbol``, derived from the 006 verdict.

        A replay is never *stale* — it is current by construction, and
        claiming otherwise would be a lie about the virtual clock.  What
        it *can* be is **invalid**: the event carries the Commit 006
        ``BarQuality`` verdict, and a replayed bar that failed the gate
        is surfaced as ``INVALID`` (and would have been quarantined at
        load time, so this is a belt-and-braces path for
        ``enforce_quality=False`` runs).

        ``tradable`` follows the trading calendar phase: during a
        replayed lunch break or outside a session, Paper must not fill.
        """
        event = self._engine.current(str(symbol).strip())
        if event is None:
            return None
        reasons = list(event.quality.get("reasons", []) or [])
        valid = bool(event.quality.get("valid", True))
        return {
            "status": "FRESH" if valid else "INVALID",
            "tradable": bool(valid and event.tradable),
            "reasons": reasons,
            "quote_age_ms": 0.0,
            "source": self.name,
            "phase": event.phase,
        }

    def bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        """Replayed 1m bars for ``symbol``, oldest first (§11).

        Lets this adapter double as Paper Trading's ``bar_service``, so
        the §28 chain — Replay → MarketBar → Quality Gate → Paper Feed —
        runs on replayed bars instead of today's merged series.  Only
        bars already emitted are visible; the cursor is the lookahead
        boundary (§26).
        """
        events = self._engine.emitted(str(symbol).strip(), limit=limit)
        return [event.bar for event in events if event.bar is not None]

    # ── helpers ──────────────────────────────────────────────────

    def _require_connected(self) -> None:
        if not self._connected:
            raise ReplayBlockedError(
                ReplayError.NOT_READY,
                detail=f"{self.name}: connect() first",
            )

    def as_dict(self) -> dict:
        """Wiring view used by the API / dashboard."""
        return {
            "adapter": self.name,
            "connected": self.connected,
            "subscribed": self.subscribed,
            "quote_count": self.quote_count,
            "max_quotes": self._max_quotes,
            "engine_state": self._engine.state.value,
            "replay_id": (
                self._engine.run.replay_id if self._engine.run else None
            ),
        }


__all__ = ["ReplayMarketDataAdapter"]
