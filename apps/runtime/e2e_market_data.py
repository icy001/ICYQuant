"""Commit 017 — End-to-End Validation: A-Share Market Data Track.

The FINAL acceptance commit of the 17-commit track.  No new business
capability is added here — this module only *proves* the chain that
Commits 001–016 built::

    Provider → Adapter → MarketQuote → Quality Gate → Redis Cache
            → Historical + Realtime Merge → Paper → Shadow
            → Strategy → Risk → Execution Simulation
            → Position / PnL → Dashboard

Twenty gates (G1–G20).  ``20/20 PASS`` closes the track; any FAIL
means Commit 017 = FAIL.  A "basically fine" is not a PASS.

Design rules
------------
*   **Offline deterministic.**  No real broker, no real Redis, no wall
    clock in the decision path.  A virtual clock pins the session at
    2026-09-08 (Tuesday) 10:31 CST — a CONTINUOUS_AM trading phase.
    Where the vendor edge is needed, the *real* adapter runs over the
    built-in simulated provider (raw vendor-dialect frames).
*   **Real components, scripted edge.**  Quality Gate, QuoteService,
    MarketCache, BarService, BarMergeEngine, PaperMarketFeed, Replay
    Engine, AccountSyncService, Reconciler and ShadowTradingService
    are the production classes — only the outermost provider seam is
    simulated, exactly as in production dev mode.
*   **Honesty over coverage.**  A check that cannot be performed
    offline is reported as such — never faked into a PASS.

Usage::

    python -m apps.runtime e2e --suite market-data
    python -m apps.runtime market-data-check        # same suite, short alias

Artifacts land in ``artifacts/market_data_e2e/``::

    e2e_report.json / e2e_report.md     20-gate verdicts
    failure_injection.json              G5 / G18 injected-fault outcomes
    reconciliation_report.json          G14 ledger-vs-broker evidence
    shadow_safety_report.json           G17 §26 safety-matrix evidence
"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

from services.market_data.calendar.market_phase import MarketPhase
from services.market_data.calendar.trading_calendar import calendar
from services.market_data.universe import universe

logger = logging.getLogger("icyquant.e2e.market_data")

CST = timezone(timedelta(hours=8))

# ── the virtual trading day ────────────────────────────────────────
# 2026-09-08 is a Tuesday, no holiday, no makeup — a plain trading day.
VDATE = date(2026, 9, 8)

# ── replay window for the QuoteService validator ───────────────────
# MarketDataValidator measures quote age against wall time and takes
# ``stale_seconds`` at construction, so replaying a past session needs a
# window that spans it.  Bounded (not "infinite") so the check keeps
# meaning: a quote from before the replayed session is still refused.
# Freshness *policy* stays with the clock-injectable Quality Gate.
REPLAY_STALE_SECONDS = 400 * 24 * 3600

#: The vendor edge is seeded, not random.  The simulated provider is
#: deterministic *given* a seed, so a replay pins it: otherwise "the
#: suite passed" would mean "the fake happened to be kind today".
PROVIDER_SEED = 20260908

UNIVERSE_SYMBOLS = [
    "159852", "513050", "159890", "159559", "159569",
    "515880", "159871", "513310", "501225", "161116", "165520",
]

# G2 expectations — mirrors services/market_data/universe.py seed table.
# Note 501225 / 161116 / 165520 are NOT ETFs: the track is named "ETF"
# but the Instrument Master must tell the truth (002).
EXPECTED_INSTRUMENTS: dict[str, dict[str, Any]] = {
    "159852": {"exchange": "SZSE", "instrument_type": "ETF", "lot_size": 100},
    "513050": {"exchange": "SSE", "instrument_type": "QDII-ETF", "lot_size": 100},
    "159890": {"exchange": "SZSE", "instrument_type": "ETF", "lot_size": 100},
    "159559": {"exchange": "SZSE", "instrument_type": "ETF", "lot_size": 100},
    "159569": {"exchange": "SZSE", "instrument_type": "ETF", "lot_size": 100},
    "515880": {"exchange": "SSE", "instrument_type": "ETF", "lot_size": 100},
    "159871": {"exchange": "SZSE", "instrument_type": "ETF", "lot_size": 100},
    "513310": {"exchange": "SSE", "instrument_type": "QDII-ETF", "lot_size": 100},
    "501225": {"exchange": "SSE", "instrument_type": "QDII-LOF", "lot_size": 100},
    "161116": {"exchange": "SZSE", "instrument_type": "QDII-LOF", "lot_size": 100},
    "165520": {"exchange": "SZSE", "instrument_type": "LOF", "lot_size": 100},
}

GATE_LABELS = {
    "G1": "Architecture",
    "G2": "Instrument Master",
    "G3": "Realtime Quote",
    "G4": "Trading Session",
    "G5": "Quality Gate",
    "G6": "Redis Cache",
    "G7": "Historical Merge",
    "G8": "Paper Trading",
    "G9": "Replay",
    "G10": "Monitoring",
    "G11": "Broker Adapter",
    "G12": "Account Sync",
    "G13": "Position Sync",
    "G14": "Reconciliation",
    "G15": "Shadow",
    "G16": "Dashboard",
    "G17": "Security",
    "G18": "Failure Recovery",
    "G19": "Determinism",
    "G20": "Final E2E",
}

# Required Prometheus metric names (G10), exactly as they are exported.
REQUIRED_METRICS = [
    "icyquant_market_data_quotes_received_total",
    "icyquant_market_data_bars_received_total",
    "icyquant_market_data_quote_age_seconds",
    "icyquant_market_data_latency_seconds",
    "icyquant_market_data_latency_p95_seconds",
    "icyquant_market_data_stale_total",
    "icyquant_market_data_invalid_total",
    "icyquant_market_data_duplicate_total",
    "icyquant_market_data_gap_total",
    "icyquant_market_data_quarantine_total",
    "icyquant_market_data_reconnect_total",
    "icyquant_market_data_errors_total",
    "icyquant_market_data_cache_hit_total",
    "icyquant_market_data_cache_miss_total",
]

# §26 forbidden edges: (package root to scan, forbidden import prefix,
# human label).  The broker *account* adapter is read-only and allowed
# via services.account.sync; a broker ORDER path must not exist at all.
SHADOW_SOURCES = [
    "services/shadow",
    "services/execution/shadow",
    "services/market_data/paper",
]
FORBIDDEN_BROKER_IMPORTS = ["services.broker"]
# Matched against real *code* identifiers only — never against comments or
# docstrings.  A module whose docstring promises "there is no submit_order
# in this package" is documentation, not an order edge; a raw text scan
# would flag exactly the file that disclaims the behaviour.
FORBIDDEN_ORDER_NAMES = frozenset({
    "submit_order",
    "place_order",
    "send_order",
    "cancel_order",
    "BrokerOrderAdapter",
    "OrderGateway",
    "LiveExecutionAdapter",
    "BrokerAccountAdapter",
})


def _code_names(path: Path) -> set[str]:
    """Identifiers, attributes and imports actually used by the code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.keyword):
            if node.arg:
                names.add(node.arg)
    return names


# ══════════════════════════════════════════════════════════════════
# Harness
# ══════════════════════════════════════════════════════════════════


class VirtualClock:
    """Deterministic clock seam — no wall time enters the decision path."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    @property
    def now(self) -> datetime:
        return self._now

    def __call__(self) -> datetime:
        return self._now

    def advance(self, **kwargs: Any) -> datetime:
        self._now = self._now + timedelta(**kwargs)
        return self._now

    def set(self, value: datetime) -> None:
        self._now = value


def cst(h: int, m: int, s: int = 0, *, day: date = VDATE) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=CST)


def vclock(hour: int = 10, minute: int = 31) -> VirtualClock:
    return VirtualClock(cst(hour, minute))


class FlakyCacheBackend:
    """Memory backend that can be told to fail (G6 / G18-B)."""

    name = "flaky-memory"

    def __init__(self, clock: Callable[[], datetime]) -> None:
        from services.market_data.cache.market_cache import _MemoryBackend

        self._inner = _MemoryBackend(clock=clock)
        self.failing = False
        self.failures = 0

    def _guard(self, op: str):
        if self.failing:
            self.failures += 1
            from services.market_data.cache.cache_models import (
                CacheBackendError,
            )

            raise CacheBackendError(f"injected failure in {op}")

    def get(self, key: str):
        self._guard("get")
        return self._inner.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._guard("set")
        self._inner.set(key, value, ttl_seconds)

    def delete(self, key: str) -> None:
        self._guard("delete")
        self._inner.delete(key)

    def keys(self, pattern: str):
        self._guard("keys")
        return self._inner.keys(pattern)

    def ping(self) -> bool:
        self._guard("ping")
        return self._inner.ping()

    def clear(self) -> None:
        self._inner.clear()


class _BrokerBackedQuoteSource:
    """The paper feed's quote source, driven by the REAL broker adapter.

    ``latest()`` answers with the last quote the adapter actually
    delivered — and ``None`` the moment the link is not up.  That is what
    makes "the broker link is down" *observable* by the paper/shadow
    stack (feed → OFFLINE) instead of merely asserted, and it guarantees
    a dead link can never be read as a stale price.

    Only ``latest()`` / ``quality()`` are needed: the feed duck-types its
    quote source, deriving quality itself when ``quality()`` is absent.
    """

    #: A link that can still deliver.  ``SUBSCRIBED`` is where a healthy
    #: adapter rests between stream bursts; ``STREAMING`` is what it
    #: becomes while a ``stream()`` is being consumed.  Everything else
    #: (DISCONNECTED / CONNECTION_LOST / RECONNECTING) is down.
    LINK_UP = ("SUBSCRIBED", "STREAMING")

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter
        self._latest: dict[str, Any] = {}
        self.pulled = 0
        self.pulls = 0

    def _link_up(self) -> bool:
        try:
            return self._adapter.connection_state().name in self.LINK_UP
        except Exception:  # noqa: BLE001 — a dead adapter is not up
            return False

    def pull(self, count: int = 1) -> int:
        """Consume up to ``count`` frames from the adapter stream."""
        if not self._link_up():
            return 0
        self.pulls += 1
        taken = 0
        for quote in self._adapter.stream():
            self._latest[quote.symbol] = quote
            taken += 1
            if taken >= count:
                break
        self.pulled += taken
        return taken

    def pull_until(self, symbol: str, *, budget: int = 200) -> bool:
        """Stream until ``symbol`` has been seen (bounded, deterministic)."""
        for _ in range(budget):
            if self._latest.get(symbol) is not None:
                return True
            if self.pull(1) == 0:
                return False
        return self._latest.get(symbol) is not None

    def latest(self, symbol: str):
        return self._latest.get(symbol) if self._link_up() else None

    def quality(self, symbol: str):
        return None


class _NoBarSource:
    """Bar source with no realtime bars — merge falls back to history."""

    def bars(self, symbol: str, limit: int = 500) -> list:
        return []


class _StaleHistoryProvider:
    """History whose newest closed minute *is* the junction minute (§8).

    The synthetic provider stops strictly before the junction, so it can
    never overlap realtime and the engine's closed/closed audit rule
    (``BarRevision``) would never run.  This provider models the race
    that does happen in production: the vendor's last closed bar lands
    *after* the realtime service has already closed its own bucket for
    that same minute.  The engine must keep the realtime value and
    record the disagreement — never overwrite it silently.
    """

    name = "synthetic-stale"

    def __init__(self, symbol: str, minute: datetime,
                 close: str = "9.999") -> None:
        self._symbol = symbol
        self._minute = minute
        self._close = Decimal(close)

    def bars(self, symbol: str, timeframe: str = "1m", limit: int = 500,
             *, before: Any = None, anchor_price: Any = None) -> list:
        if symbol != self._symbol or timeframe != "1m" or limit <= 0:
            return []
        from services.market_data.domain.bar import Bar
        from services.market_data.domain.instrument import Instrument

        exchange = Instrument.infer_exchange(symbol)
        out = []
        for minute in (self._minute - timedelta(minutes=1), self._minute):
            out.append(Bar(
                symbol=symbol,
                exchange=exchange,
                timeframe="1m",
                timestamp=minute.astimezone(timezone.utc),
                open=self._close,
                high=self._close,
                low=self._close,
                close=self._close,
                volume=1000,
                turnover=(self._close * 1000).quantize(Decimal("0.01")),
                is_closed=True,
            ))
        return out


class _NoHistoryProvider:
    """Historical provider with no data — 'no data = no bar' (§7)."""

    def bars(self, symbol: str, timeframe: str = "1m", limit: int = 500,
             *, before: Any = None, anchor_price: Any = None) -> list:
        return []


@dataclass
class GateResult:
    gate: str
    name: str
    passed: bool
    detail: str
    duration_ms: float = 0.0
    data: dict = field(default_factory=dict)


def _fail_list(problems: list[str]) -> str:
    return "; ".join(problems)


class MarketDataE2E:
    """Runs gates G1–G20 and produces the Commit 017 report."""

    def __init__(self, artifacts_dir: Path, repo_root: Path) -> None:
        self.artifacts = artifacts_dir
        self.repo_root = repo_root
        self.failure_injection: list[dict] = []
        self.reconciliation: dict = {}
        self.shadow_safety: dict = {}
        self.final_chain: dict = {}

    # ── shared builders (fresh per gate: isolation) ────────────────

    def _quality_pipeline(self, clock: VirtualClock):
        """QualityGate + QuoteService wired exactly as production.

        One replay concession, stated plainly: ``MarketDataValidator``
        (inside ``QuoteService``) measures quote age against *wall* time
        and takes its window at construction — it has no clock seam, and
        a replayed session is by definition not "now".  Replay therefore
        hands it a window that covers the virtual session, while the
        **Quality Gate — which owns the staleness policy and does take
        the clock** (``evaluate(..., now=)``) — keeps its real semantics
        pinned to the virtual clock.  G5 exercises that policy and still
        sees stale data rejected; nothing is silently tolerated.
        """
        from services.market_data.quality import QualityGate, QualityConfig
        from services.market_data.quote_service import QuoteService
        from services.market_data.validators.market_data_validator import (
            MarketDataValidator,
        )

        gate = QualityGate(
            config=QualityConfig.from_env(), trading_calendar=calendar
        )
        service = QuoteService(
            quality_gate=gate,
            validator=MarketDataValidator(
                stale_seconds=REPLAY_STALE_SECONDS
            ),
        )
        return gate, service

    def _cache(self, clock: VirtualClock, *, flaky: bool = False):
        from services.market_data.cache.cache_models import CacheConfig
        from services.market_data.cache.market_cache import MarketCache

        backend = FlakyCacheBackend(clock) if flaky else None
        return MarketCache(
            config=CacheConfig(enabled=True, redis_url=None),
            backend=backend,
            clock=clock,
        )

    @staticmethod
    def make_quote(
        symbol: str,
        *,
        clock: VirtualClock,
        last: str = "1.050",
        bid: Optional[str] = None,
        ask: Optional[str] = None,
        volume: int = 123_400,
        turnover: str = "129_570.00",
        pre_close: str = "1.040",
        ts: Optional[datetime] = None,
    ) -> Any:
        from services.market_data.domain.instrument import Exchange
        from services.market_data.domain.quote import MarketQuote

        bid = last if bid is None else bid
        ask = last if ask is None else ask
        now = ts if ts is not None else clock.now
        inst = universe.get(symbol)
        exchange = getattr(inst, "exchange", None) or Exchange.SZSE
        return MarketQuote(
            symbol=symbol,
            exchange=exchange,
            last=Decimal(last),
            bid=Decimal(str(bid)),
            ask=Decimal(str(ask)),
            bid_size=15_600,
            ask_size=14_200,
            volume=volume,
            turnover=Decimal(str(turnover).replace("_", "")),
            pre_close=Decimal(str(pre_close)),
            timestamp=now,
            received_timestamp=now + timedelta(milliseconds=25),
        )

    @staticmethod
    def _settle(clock: VirtualClock, quote: Any) -> None:
        """Let the virtual clock reach the tick that was just published.

        Two hard rules make this mandatory rather than cosmetic:

        * the paper stack refuses any order created *before* the quote
          that would price it (``PAPER_LOOKAHEAD_VIOLATION``) — a replay
          must therefore step its clock to the tick's arrival stamp, the
          same way wall time does live;
        * the Quality Gate keys duplicates on the exchange timestamp, so
          publishing twice at one instant is a duplicate, not a tick.

        Moving to ``received_timestamp`` (tick + 25 ms of latency) at
        once satisfies the first and gives the next publish a fresh
        instant, which satisfies the second.
        """
        received = getattr(quote, "effective_received_at", None)
        if received is not None and received > clock.now:
            clock.set(received)

    def ingest(self, quote_service: Any, clock: VirtualClock, symbol: str,
               **kwargs: Any) -> Any:
        """Publish one real quote through the real gate, then settle."""
        quote = self.make_quote(symbol, clock=clock, **kwargs)
        quote_service.update(quote, now=clock.now)
        self._settle(clock, quote)
        return quote

    # ── gate runner ────────────────────────────────────────────────

    def run(self, only: Optional[set[str]] = None) -> list[GateResult]:
        """Run G1–G20 (or the subset named in ``only``).

        A gate that raises is recorded as a FAIL, never skipped: the
        suite has no "skipped" outcome by design.
        """
        gates: list[Callable[[], GateResult]] = [
            self.g01_architecture,
            self.g02_instrument_master,
            self.g03_realtime_quotes,
            self.g04_trading_session,
            self.g05_quality_gate,
            self.g06_redis_cache,
            self.g07_historical_merge,
            self.g08_paper_trading,
            self.g09_replay,
            self.g10_monitoring,
            self.g11_broker_adapter,
            self.g12_account_sync,
            self.g13_position_sync,
            self.g14_reconciliation,
            self.g15_shadow,
            self.g16_dashboard,
            self.g17_security,
            self.g18_failure_recovery,
            self.g19_determinism,
            self.g20_final_e2e,
        ]
        results: list[GateResult] = []
        for gate_fn in gates:
            # ``g07_historical_merge`` → ``G7``
            gate_id = f"G{int(gate_fn.__name__[1:3])}"
            if only and gate_id not in only:
                continue
            logger.info("running gate %s — %s", gate_id, GATE_LABELS[gate_id])
            t0 = time.perf_counter()
            try:
                result = gate_fn()
            except Exception as exc:  # a crash is a FAIL, never a skip
                logger.exception("gate %s crashed", gate_id)
                result = GateResult(
                    gate=gate_id,
                    name=GATE_LABELS[gate_id],
                    passed=False,
                    detail=f"gate crashed: {exc!r}",
                )
            result.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            results.append(result)
            logger.info(
                "gate %s — %s — %s", gate_id,
                "PASS" if result.passed else "FAIL", result.detail[:160],
            )
        return results

    def _record_injection(self, scenario: str, expected: str, observed: str,
                          blocked: Optional[bool]) -> None:
        self.failure_injection.append({
            "scenario": scenario,
            "expected": expected,
            "observed": observed,
            "order_blocked": blocked,
        })

    # ════════════════════════════════════════════════════════════
    # G1 — Architecture
    # ════════════════════════════════════════════════════════════

    def g01_architecture(self) -> GateResult:
        problems: list[str] = []

        # 1. The core singletons import cleanly (dependency direction is
        #    enforced by import survival — a cycle or a skip would raise).
        from services.market_data.market_data_service import (
            MarketDataService,
        )
        from services.market_data.paper.paper_market_feed import (
            PaperMarketFeed,
        )
        from services.shadow.service import ShadowTradingService
        from services.account.sync.reconciliation import (  # noqa: F401
            AccountReconciler,
        )

        # 2. §26 forbidden edges — Shadow/Paper must never touch the
        #    broker order path.  The broker package itself may only
        #    contain read-only market/account adapters.
        broker_root = self.repo_root / "services" / "broker"
        order_modules = [
            p.name for p in broker_root.rglob("*.py")
            if "order" in p.name.lower()
        ]
        if order_modules:
            problems.append(f"broker order modules exist: {order_modules}")

        def _imports(path: Path) -> set[str]:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                return set()
            found: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(a.name for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module)
            return found

        for root in SHADOW_SOURCES:
            for path in (self.repo_root / root).rglob("*.py"):
                for mod in _imports(path):
                    if any(mod.startswith(b) for b in FORBIDDEN_BROKER_IMPORTS):
                        problems.append(
                            f"{path.relative_to(self.repo_root)} imports {mod}"
                        )
                for name in sorted(_code_names(path) & FORBIDDEN_ORDER_NAMES):
                    problems.append(
                        f"{path.relative_to(self.repo_root)} references {name}"
                    )

        # 3. Strategy must not reach into Redis or the broker SDK.
        strategy_root = self.repo_root / "services" / "strategy"
        if strategy_root.exists():
            for path in strategy_root.rglob("*.py"):
                for mod in _imports(path):
                    if mod.startswith("redis") or mod.startswith("services.broker"):
                        problems.append(
                            f"strategy/{path.name} imports {mod}"
                        )

        # 4. Dashboard reads state via the service layer — never Redis.
        dash_root = self.repo_root / "apps" / "dashboard"
        for path in dash_root.rglob("*.py"):
            for mod in _imports(path):
                if mod.split(".")[0] == "redis":
                    problems.append(f"dashboard/{path.name} imports redis")

        data = {
            "broker_package_contents": sorted(
                str(p.relative_to(broker_root))
                for p in broker_root.rglob("*.py")
            ) if broker_root.exists() else [],
            "forbidden_edges": problems,
            "components_present": [
                MarketDataService.__name__,
                PaperMarketFeed.__name__,
                ShadowTradingService.__name__,
            ],
        }
        passed = not problems
        return GateResult(
            "G1", GATE_LABELS["G1"], passed,
            "dependency direction clean; no Shadow→broker-order edge"
            if passed else _fail_list(problems),
            data=data,
        )

    # ════════════════════════════════════════════════════════════
    # G2 — Instrument Master
    # ════════════════════════════════════════════════════════════

    def g02_instrument_master(self) -> GateResult:
        problems: list[str] = []
        instruments = universe.all()
        by_symbol = {i.symbol: i for i in instruments}

        if len(instruments) != 11:
            problems.append(f"universe size {len(instruments)} != 11")
        for sym in UNIVERSE_SYMBOLS:
            inst = by_symbol.get(sym)
            if inst is None:
                problems.append(f"{sym} missing from universe")
                continue
            if not inst.enabled:
                problems.append(f"{sym} not enabled")
            exp = EXPECTED_INSTRUMENTS[sym]
            got_type = str(inst.instrument_type.value)
            if got_type != exp["instrument_type"]:
                problems.append(
                    f"{sym} type {got_type} != {exp['instrument_type']}"
                )
            got_exch = str(inst.exchange.value)
            if got_exch != exp["exchange"]:
                problems.append(
                    f"{sym} exchange {got_exch} != {exp['exchange']}"
                )
            if inst.lot_size != exp["lot_size"]:
                problems.append(f"{sym} lot_size {inst.lot_size} != 100")

        # §G2: the track is named ETF, but the Instrument Master must
        # not blindly label everything ETF.
        for sym in ("501225", "161116", "165520"):
            inst = by_symbol.get(sym)
            if inst is not None and str(inst.instrument_type.value) == "ETF":
                problems.append(f"{sym} is not an ETF but is labelled ETF")

        data = {
            "loaded": len(instruments),
            "symbols": sorted(by_symbol),
            "types": {s: str(i.instrument_type.value)
                      for s, i in sorted(by_symbol.items())},
        }
        passed = not problems
        return GateResult(
            "G2", GATE_LABELS["G2"], passed,
            f"{len(instruments)}/11 instruments loaded, mapping correct"
            if passed else _fail_list(problems),
            data=data,
        )

    # ════════════════════════════════════════════════════════════
    # G3 — Real-time Market Data
    # ════════════════════════════════════════════════════════════

    def g03_realtime_quotes(self) -> GateResult:
        from services.market_data.adapters.broker import (
            BrokerMarketDataAdapter,
            SimulatedBrokerProvider,
        )
        from services.market_data.config.broker_config import (
            BrokerMarketDataConfig,
        )

        clock = vclock(10, 31)
        config = BrokerMarketDataConfig.from_env()
        config = type(config)(
            enabled=True,
            provider="simulated",
            reconnect_seconds=0,
            max_reconnect_attempts=3,
            resubscribe_on_reconnect=True,
        )
        provider = SimulatedBrokerProvider(seed=PROVIDER_SEED, clock=clock)
        adapter = BrokerMarketDataAdapter(
            provider, config=config, clock=clock, max_quotes=60
        )
        adapter.connect()
        adapter.subscribe_universe()

        problems: list[str] = []
        quotes: dict[str, dict] = {}
        for quote in adapter.stream():
            quotes.setdefault(quote.symbol, {
                "timestamp": quote.timestamp.isoformat(),
                "bid": str(quote.bid), "ask": str(quote.ask),
                "last": str(quote.last), "volume": quote.volume,
                "turnover": str(quote.turnover),
            })

        missing = [s for s in UNIVERSE_SYMBOLS if s not in quotes]
        if missing:
            problems.append(f"symbols without quotes: {missing}")
        for sym, q in quotes.items():
            if not q["timestamp"]:
                problems.append(f"{sym} empty timestamp")
            if float(q["bid"]) <= 0 or float(q["ask"]) <= 0:
                problems.append(f"{sym} invalid bid/ask")
            elif float(q["bid"]) > float(q["ask"]):
                problems.append(f"{sym} bid > ask")
            if int(q["volume"]) < 0:
                problems.append(f"{sym} negative volume")
            if float(q["turnover"]) < 0:
                problems.append(f"{sym} negative turnover")
            ts = datetime.fromisoformat(q["timestamp"])
            if ts.date() != VDATE:
                problems.append(f"{sym} timestamp not on virtual day")
            if ts.tzinfo is None:
                problems.append(f"{sym} timestamp is naive")

        adapter.disconnect()
        coverage = f"{len(quotes)}/11"
        passed = not problems and len(quotes) == 11
        return GateResult(
            "G3", GATE_LABELS["G3"], passed,
            f"quote coverage {coverage}; all fields valid"
            if passed else _fail_list(problems),
            data={"coverage": coverage, "quotes": quotes},
        )

    # ════════════════════════════════════════════════════════════
    # G4 — Trading Session
    # ════════════════════════════════════════════════════════════

    def g04_trading_session(self) -> GateResult:
        problems: list[str] = []

        phase_cases = [
            (cst(9, 20), MarketPhase.AUCTION, "09:20 auction"),
            (cst(9, 31), MarketPhase.CONTINUOUS_AM, "09:31 continuous AM"),
            (cst(12, 0), MarketPhase.LUNCH_BREAK, "12:00 lunch break"),
            (cst(14, 0), MarketPhase.CONTINUOUS_PM, "14:00 continuous PM"),
            (cst(15, 30), MarketPhase.POST_CLOSE, "15:30 post close"),
        ]
        observed: dict[str, str] = {}
        for ts, expected, label in phase_cases:
            got = calendar.get_phase(ts)
            observed[label] = got.value
            if got != expected:
                problems.append(f"{label}: got {got.value}, want {expected.value}")

        # Trading day / weekend / holiday / makeup day
        cases = {
            "2026-09-08": (True, "ordinary Tuesday"),
            "2026-09-12": (False, "Saturday, no makeup"),
            "2026-10-01": (False, "National Day holiday"),
            "2026-02-28": (True, "makeup trading day (Sat)"),
            "2026-10-10": (True, "makeup trading day (Sat)"),
        }
        for day, (want, label) in cases.items():
            got = calendar.is_trading_day(day)
            observed[f"trading-day {day} ({label})"] = got
            if got != want:
                problems.append(f"{day} ({label}): got {got}, want {want}")

        # 午休 ≠ 数据断流: lunch break is a session phase, not a data
        # gap — the merge engine must not report 11:30→13:00 as missing
        # bars.  Proven here via the calendar's bar-phase rules, and
        # end-to-end in G7 with real bars.
        if MarketPhase.LUNCH_BREAK in MarketPhase.__members__.values():
            bar_phases_lunch = calendar.get_phase(cst(12, 0))
            if bar_phases_lunch != MarketPhase.LUNCH_BREAK:
                problems.append("12:00 not reported as LUNCH_BREAK")
        lunch_session = calendar.get_session(cst(12, 0))
        if lunch_session.is_trading_day is not True:
            problems.append("lunch break reported as non-trading day")

        passed = not problems
        return GateResult(
            "G4", GATE_LABELS["G4"], passed,
            "phases, weekend, holiday and makeup days all correct; "
            "lunch break is a phase, not a data gap"
            if passed else _fail_list(problems),
            data={"observed": observed},
        )

    # ════════════════════════════════════════════════════════════
    # G5 — Data Quality Gate
    # ════════════════════════════════════════════════════════════

    def g05_quality_gate(self) -> GateResult:
        from services.market_data.exceptions.market_data_error import (
            MarketDataError,
            QualityRejectedError,
        )
        from services.market_data.quality import QualityStatus

        clock = vclock(10, 31)
        gate, service = self._quality_pipeline(clock)
        problems: list[str] = []
        rejected: dict[str, str] = {}
        # Anomalies the gate accepts into the stream but refuses to trade
        # on (the WARNING/STALE half of the verdict vocabulary).
        flagged: dict[str, str] = {}
        # The write path has two refusal layers — the Quality Gate
        # (policy: freshness, duplicate, price, session...) and the
        # schema validator (shape: symbol/prefix/exchange/tz).  A quote
        # that any layer refuses never reaches the store; which layer
        # answered is recorded, because "the gate caught it" and "the
        # validator caught it" are different claims.
        layers: dict[str, str] = {}

        def _inject(name: str, symbol: str, quote: Any,
                    *, sequence_id: Optional[str] = None,
                    at: Any = None) -> None:
            stored_before = service.latest(symbol)
            try:
                service.update(
                    quote, sequence_id=sequence_id or f"E2E-{name}",
                    now=at or clock.now,
                )
                problems.append(f"{name}: quote was ACCEPTED (expected reject)")
                return
            except QualityRejectedError as exc:
                reason, layer = str(exc), "quality-gate"
            except MarketDataError as exc:
                # refused by the schema validator instead (e.g. a code
                # whose exchange cannot be inferred).  Still refused —
                # the layer is reported rather than papered over.
                reason, layer = str(exc), "validator"
            rejected[name] = reason
            layers[name] = layer
            # A refusal must not touch the store: whatever was already
            # accepted for this symbol stays exactly as it was.
            if service.latest(symbol) is not stored_before:
                problems.append(f"{name}: rejected quote stored anyway")

        # A clean quote first — the baseline for regression/duplicate.
        baseline = self.make_quote("159852", clock=clock)
        service.update(baseline, now=clock.now)
        if not service.tradable("159852"):
            problems.append("clean 159852 quote was not tradable")

        # STALE, honestly — and it is *not* a write-path refusal.  Stale
        # data is valid data, merely old: the gate lets it into the
        # stream (for display) and refuses it for *trading*.  Calling it
        # "rejected" would be asserting the wrong behaviour, so both
        # halves are checked: it is in sequence (same instant, its own
        # sequence id, so neither duplicate nor regression can answer
        # first), the gate judges it ten minutes later, and the verdict
        # must be STALE + passed + NOT tradable + BLOCK_TRADING.
        stale = self.make_quote("159852", clock=clock)
        service.update(
            stale, sequence_id="E2E-STALE",
            now=clock.now + timedelta(minutes=10),
        )
        verdict = service.quality("159852") or {}
        flagged["STALE"] = verdict.get("status")
        if verdict.get("status") != QualityStatus.STALE.value:
            problems.append(f"STALE: verdict is {verdict.get('status')}")
        if not verdict.get("passed"):
            problems.append("STALE: a merely-old quote did not enter the stream")
        if verdict.get("tradable"):
            problems.append("STALE: a ten-minute-old quote stayed tradable")
        if verdict.get("action") != "BLOCK_TRADING":
            problems.append(
                f"STALE: action is {verdict.get('action')}, "
                f"want BLOCK_TRADING"
            )
        if service.tradable("159852"):
            problems.append("STALE: the symbol stayed tradable")
        _inject(
            "INVALID_PRICE", "159852",
            self.make_quote("159852", clock=clock, last="-1"),
        )
        _inject(
            "FUTURE_TIMESTAMP", "159852",
            self.make_quote("159852", clock=clock,
                            ts=clock.now + timedelta(minutes=5)),
        )
        _inject(
            "TIMESTAMP_REGRESSION", "159852",
            self.make_quote("159852", clock=clock,
                            ts=clock.now - timedelta(seconds=90)),
        )
        # DUPLICATE needs one identity published twice: the first is a
        # legitimate new sequence and *is* stored (that is the point —
        # the second is what must be refused).
        dup = self.make_quote("159852", clock=clock)
        try:
            service.update(dup, sequence_id="E2E-DUPLICATE", now=clock.now)
            accepted_at = clock.now
            service.update(dup, sequence_id="E2E-DUPLICATE", now=clock.now)
            problems.append("DUPLICATE: identical sequence accepted twice")
        except QualityRejectedError as exc:
            rejected["DUPLICATE"] = str(exc)
            layers["DUPLICATE"] = "quality-gate"
        _inject(
            "INVALID_BID_ASK", "159852",
            self.make_quote("159852", clock=clock, bid="2.000", ask="1.000"),
        )
        _inject(
            "INVALID_VOLUME", "159852",
            self.make_quote("159852", clock=clock, volume=-5),
        )
        _inject(
            "UNKNOWN_SYMBOL", "999999",
            self.make_quote("999999", clock=clock),
        )

        # Quarantine: rejected data is preserved for audit.
        quarantined = gate.quarantine.recent(limit=20)
        if not quarantined:
            problems.append("quarantine is empty after injections")
        # The store still holds the last *accepted* instant — none of the
        # refusals (stale / future / regressed / bad price / bad volume)
        # managed to overwrite good data.
        kept = service.latest("159852")
        if kept is None or kept.timestamp != accepted_at:
            problems.append(
                f"store holds {kept.timestamp if kept else None}, "
                f"want the accepted {accepted_at}"
            )
        # ...and a symbol is never poisoned permanently: one fresh clean
        # tick restores it (a refusal is a verdict on data, not a ban).
        clock.set(clock.now + timedelta(seconds=1))
        service.update(self.make_quote("159852", clock=clock), now=clock.now)
        if not service.tradable("159852"):
            problems.append("a fresh clean tick did not restore tradability")

        # 7 classes must never enter the stream; STALE is the 8th, and it
        # exercises the other half of the vocabulary (in, but not
        # tradable).  Both are counted, separately, so the artifact never
        # claims stale data was "rejected".
        expected_refusals = {
            "INVALID_PRICE", "FUTURE_TIMESTAMP", "TIMESTAMP_REGRESSION",
            "DUPLICATE", "INVALID_BID_ASK", "INVALID_VOLUME",
            "UNKNOWN_SYMBOL",
        }
        missing_rejects = expected_refusals - set(rejected)
        if missing_rejects:
            problems.append(f"anomalies not rejected: {sorted(missing_rejects)}")
        if set(flagged) != {"STALE"}:
            problems.append(f"flagged anomalies are {sorted(flagged)}")

        for name, reason in rejected.items():
            self._record_injection(
                f"G5/{name}", layers.get(name, "quality-gate"), reason,
                blocked=None,
            )
        for name, status in flagged.items():
            self._record_injection(
                f"G5/{name}", "accepted-then-not-tradable", status,
                blocked=None,
            )

        passed = not problems
        return GateResult(
            "G5", GATE_LABELS["G5"], passed,
            f"{len(rejected)}/{len(expected_refusals)} anomaly classes "
            f"refused at the gate or the validator; "
            f"{len(flagged)} flagged STALE (in the stream, not tradable); "
            "clean quote still tradable"
            if passed else _fail_list(problems),
            data={
                "rejected": rejected,
                "flagged": flagged,
                "refused_by": layers,
                "quarantine_count": gate.quarantine.count(),
                "gate_stats": gate.stats(),
            },
        )

    # ════════════════════════════════════════════════════════════
    # G6 — Redis Cache
    # ════════════════════════════════════════════════════════════

    def g06_redis_cache(self) -> GateResult:
        from services.market_data.aggregation.bar_service import BarService

        clock = vclock(10, 31)
        problems: list[str] = []

        # healthy path: write-through + read-back for all §8 keys
        cache = self._cache(clock)
        quote = self.make_quote("159852", clock=clock)
        if cache.set_quote(quote) is not True:
            problems.append("set_quote returned False on healthy backend")
        got = cache.get_quote("159852")
        if not got or got.get("symbol") != "159852":
            problems.append("get_quote roundtrip failed")
        cache.set_session(calendar.get_session(clock.now))
        if not cache.get_session("SZSE"):
            problems.append("get_session returned nothing")
        health = cache.health()
        if health["status"] != "HEALTHY":
            problems.append(f"healthy cache reports {health['status']}")
        if cache.trading_allowed() is not True:
            problems.append("healthy cache blocks trading")

        # degraded path: backend goes down
        flaky = FlakyCacheBackend(clock)
        from services.market_data.cache.cache_models import CacheConfig
        from services.market_data.cache.market_cache import MarketCache

        bad_cache = MarketCache(
            config=CacheConfig(enabled=True, redis_url=None),
            backend=flaky,
            clock=clock,
        )
        flaky.failing = True
        q2 = self.make_quote("513050", clock=clock)
        bad_cache.set_quote(q2)          # best-effort write fails
        h2 = bad_cache.health()          # ping fails
        if h2["status"] != "DEGRADED":
            problems.append(f"failed backend reports {h2['status']}")
        if bad_cache.trading_allowed() is not False:
            problems.append("degraded cache does NOT block trading")
        self._record_injection(
            "G6/cache-unavailable", "DEGRADED + trading blocked",
            h2["status"], blocked=not bad_cache.trading_allowed(),
        )

        # recovery: backend restored → rehydrate from source → HEALTHY
        flaky.failing = False
        bad_cache.set_quote(self.make_quote("513050", clock=clock))
        h3 = bad_cache.health()
        if h3["status"] != "HEALTHY":
            problems.append(f"restored backend reports {h3['status']}")
        if bad_cache.trading_allowed() is not True:
            problems.append("restored cache still blocks trading")
        if bad_cache.get_quote("513050") is None:
            problems.append("rehydrated quote missing after recovery")

        # bars survive a cache restart: the bar source is the
        # BarService/merge engine, not the cache — a cache restart must
        # not reset K线 (§15 merge rehydration).
        bar_service = BarService()
        bar_clock = vclock(10, 35)
        for second in (5, 30, 55):
            bar_clock.set(cst(10, 35, second))
            bar_service.on_quote(self.make_quote("159852", clock=bar_clock))
        bar_clock.set(cst(10, 36, 2))
        bar_service.on_quote(self.make_quote("159852", clock=bar_clock))
        if not bar_service.bars("159852", limit=10):
            problems.append("BarService produced no bars")

        passed = not problems
        return GateResult(
            "G6", GATE_LABELS["G6"], passed,
            "quote/bar/session/quality cached; failure → DEGRADED + "
            "blocked; recovery → rehydrate → HEALTHY"
            if passed else _fail_list(problems),
            data={
                "healthy": health,
                "degraded": h2,
                "recovered": h3,
            },
        )

    # ════════════════════════════════════════════════════════════
    # G7 — Historical + Realtime Merge
    # ════════════════════════════════════════════════════════════

    def g07_historical_merge(self) -> GateResult:
        from services.market_data.aggregation.bar_service import BarService
        from services.market_data.merge.bar_merge import BarMergeEngine
        from services.market_data.merge.historical_provider import (
            SyntheticHistoricalProvider,
        )

        problems: list[str] = []
        clock = vclock(10, 36)

        # cold start at 10:35 → history 09:30..10:34 + realtime 10:35
        bar_service = BarService()
        for second in (5, 20, 45):
            clock.set(cst(10, 35, second))
            bar_service.on_quote(self.make_quote("159852", clock=clock))
        clock.set(cst(10, 36, 2))  # closes the 10:35 bar
        bar_service.on_quote(self.make_quote("159852", clock=clock))

        provider = SyntheticHistoricalProvider(clock=clock)
        engine = BarMergeEngine(
            provider, bar_service=bar_service, trading_calendar=calendar
        )
        # The history budget is ``limit - realtime`` (the union must fit
        # the limit), so 67 = 65 historical minutes (09:30..10:34) + the
        # two realtime bars (10:35 closed, 10:36 in progress).
        view = engine.unified("159852", timeframe="1m", limit=67)
        bars = [b for b, _src in view["bars"]]
        # History is stamped in UTC and realtime in CST: every comparison
        # below is made on the exchange wall clock, never on the raw tz.
        ts = [b.timestamp.astimezone(CST) for b in bars]
        sources = [str(src).upper() for _b, src in view["bars"]]
        counts = view["counts"]

        if not bars:
            problems.append("unified series empty")
        else:
            if (ts[0].hour, ts[0].minute) != (9, 30):
                problems.append(f"series starts at {ts[0].time()}, want 09:30")
            # continuity: strictly increasing, unique, 1-minute steps —
            # this is also the cross-zone seam proof (a UTC-stamped
            # 10:34 must sit exactly one minute before a CST 10:35)
            if ts != sorted(ts):
                problems.append("bars not ascending")
            if len(set(ts)) != len(ts):
                problems.append("duplicate bar timestamps in merged series")
            for a, b in zip(ts, ts[1:]):
                if b - a != timedelta(minutes=1):
                    problems.append(
                        f"bar gap {a.time()} → {b.time()} in continuous phase"
                    )
                    break
            if view.get("gaps"):
                problems.append(f"gaps reported in continuous phase: {view['gaps']}")
            # the junction minute (10:35) is closed realtime data
            closed_rt = [
                ts[i] for i, source in enumerate(sources)
                if bars[i].is_closed and source == "REALTIME"
            ]
            if not closed_rt or (closed_rt[-1].hour, closed_rt[-1].minute) != (10, 35):
                problems.append(
                    f"junction bar is {closed_rt[-1] if closed_rt else None}, "
                    f"want the closed realtime 10:35"
                )
            # the tail is the in-progress minute — realtime, not closed
            if bars[-1].is_closed or sources[-1] != "REALTIME":
                problems.append(
                    f"tail bar closed={bars[-1].is_closed} source={sources[-1]}"
                )
            if counts["historical"] + counts["realtime"] != counts["total"]:
                problems.append(f"merge-key invariant broken: {counts}")

        # §9/§10 — with no realtime the engine serves pure history, and
        # with no history it fabricates nothing.
        cold = BarMergeEngine(
            SyntheticHistoricalProvider(clock=clock),
            bar_service=_NoBarSource(), trading_calendar=calendar,
        ).unified("159852", timeframe="1m", limit=10)
        if not cold["bars"]:
            problems.append("history-only start returned no bars")
        elif any(b.is_closed is not True for b, _s in cold["bars"]):
            problems.append("history-only start returned an open bar")
        if cold["junction"]["mode"] == "MERGED":
            problems.append("history-only start reported itself as MERGED")

        # §8 — a closed/closed disagreement is recorded, never silent
        conflict = BarMergeEngine(
            _StaleHistoryProvider("159852", cst(10, 35)),
            bar_service=bar_service, trading_calendar=calendar,
        ).unified("159852", timeframe="1m", limit=67)
        revisions = conflict.get("revisions") or []
        if not revisions:
            problems.append("closed historical conflict produced no revision")
        winner = [
            (b, src) for b, src in conflict["bars"]
            if b.timestamp.astimezone(CST).strftime("%H:%M") == "10:35"
        ]
        if not winner:
            problems.append("the conflicting 10:35 bucket disappeared")
        elif str(winner[0][1]).upper() != "REALTIME":
            problems.append(
                f"the conflicting 10:35 bucket is owned by {winner[0][1]}"
            )

        # lunch break ≠ gap: bars 11:29 then 13:00, nothing between —
        # the closure is a session phase, not missing data (§7).
        lunch_clock = vclock(13, 2)
        lunch_bars = BarService()
        for ts_q in (cst(11, 29, 10), cst(11, 29, 40), cst(13, 0, 5),
                     cst(13, 0, 40), cst(13, 1, 10)):
            lunch_clock.set(ts_q)
            lunch_bars.on_quote(self.make_quote("159852", clock=lunch_clock))
        lunch_engine = BarMergeEngine(
            _NoHistoryProvider(), bar_service=lunch_bars,
            trading_calendar=calendar,
        )
        lunch_view = lunch_engine.unified("159852", timeframe="1m", limit=240)
        lunch_ts = [b.timestamp.astimezone(CST) for b, _s in lunch_view["bars"]]
        lunch_gaps = lunch_view.get("gaps") or []
        # bars only at 11:29 and 13:00 — no fabricated lunch bars
        if any(11 < t.hour < 13 for t in lunch_ts):
            problems.append("fabricated bars during lunch break")
        if lunch_ts and (lunch_ts[-1].hour, lunch_ts[-1].minute) < (13, 0):
            problems.append("afternoon bars missing from the lunch view")
        if lunch_gaps:
            problems.append(f"lunch closure reported as gap: {lunch_gaps}")

        # honesty: a real hole in the data stays a hole (no fabrication)
        hole_clock = vclock(10, 36)
        hole_bars = BarService()
        for ts_q in (cst(10, 31, 10), cst(10, 31, 40), cst(10, 32, 5),
                     cst(10, 34, 10), cst(10, 34, 40), cst(10, 35, 5)):
            hole_clock.set(ts_q)
            hole_bars.on_quote(self.make_quote("159890", clock=hole_clock))
        hole_engine = BarMergeEngine(
            _NoHistoryProvider(), bar_service=hole_bars,
            trading_calendar=calendar,
        )
        hole_view = hole_engine.unified("159890", timeframe="1m", limit=240)
        if not hole_view.get("gaps"):
            problems.append("real bar hole not reported as gap")

        # no data at all → no bars, never zero-filled
        empty_view = hole_engine.unified("165520", timeframe="1m", limit=240)
        if empty_view["bars"]:
            problems.append("fabricated bars for symbol with no data")

        data = {
            "cold_start": {
                "first": ts[0].isoformat() if bars else None,
                "last": ts[-1].isoformat() if bars else None,
                "sources": sorted(set(sources)),
                "counts": counts,
                "junction": view.get("junction"),
            },
            "history_only": {
                "bars": len(cold["bars"]),
                "mode": cold["junction"]["mode"],
            },
            "conflict": {
                "revisions": len(revisions),
                "winner": (
                    str(winner[0][1]).upper() if winner else None
                ),
                "realtime_close": (
                    str(winner[0][0].close) if winner else None
                ),
            },
            "lunch": [t.isoformat() for t in lunch_ts],
            "hole": {
                "bars": [b.timestamp.astimezone(CST).isoformat()
                         for b, _s in hole_view["bars"]],
                "gaps": hole_view.get("gaps"),
            },
        }
        passed = not problems
        return GateResult(
            "G7", GATE_LABELS["G7"], passed,
            "cold start seamless across UTC/CST; realtime owns the "
            "junction; closed conflict → revision; lunch ≠ gap; holes "
            "stay holes"
            if passed else _fail_list(problems),
            data=data,
        )

    # ════════════════════════════════════════════════════════════
    # G8 — Paper Trading
    # ════════════════════════════════════════════════════════════

    def _build_paper_stack(self, clock: VirtualClock, *,
                           flaky_cache: bool = False, cache=None,
                           symbols: Any = ("159852",)):
        """Full production paper stack: quality → quote service → cache
        → bar service → merge engine → PaperMarketFeed.

        ``cache`` may be injected so G18 can hand the same stack a cache
        whose backend is about to fail — the degradation must be the
        real one the feed measures, not a stub.  ``symbols`` is the
        subscription set, i.e. exactly the instruments the caller feeds.
        """
        from services.market_data.aggregation.bar_service import BarService
        from services.market_data.merge.bar_merge import BarMergeEngine
        from services.market_data.merge.historical_provider import (
            SyntheticHistoricalProvider,
        )
        from services.market_data.paper.paper_feed_config import (
            PaperFeedConfig,
        )
        from services.market_data.paper.paper_market_feed import (
            PaperMarketFeed,
        )

        gate, quote_service = self._quality_pipeline(clock)
        cache = cache if cache is not None else self._cache(
            clock, flaky=flaky_cache
        )
        bar_service = BarService()
        merge_engine = BarMergeEngine(
            SyntheticHistoricalProvider(clock=clock),
            bar_service=bar_service,
            trading_calendar=calendar,
            market_cache=cache,
        )
        feed = PaperMarketFeed(
            config=PaperFeedConfig.from_env(),
            quote_service=quote_service,
            bar_service=bar_service,
            merge_engine=merge_engine,
            market_cache=cache,
            instrument_master=universe,
            clock=clock,
        )
        # Subscriptions are exactly the instruments this replay feeds:
        # READY is a per-feed verdict ("market open *and* every
        # subscribed symbol FRESH"), so subscribing the whole universe
        # while feeding one instrument would read as BLOCKED — correctly,
        # but for a reason the gate under test is not about.
        feed.subscribe(list(symbols))
        return gate, quote_service, cache, bar_service, feed

    def g08_paper_trading(self) -> GateResult:
        from services.market_data.paper.paper_feed_state import (
            PaperBlockedError,
        )

        clock = vclock(10, 31)
        _gate, quote_service, _cache, _bars, feed = self._build_paper_stack(
            clock
        )
        problems: list[str] = []

        # real market data in → quality PASS → feed READY
        self.ingest(quote_service, clock, "159852", bid="1.048", ask="1.052")
        if feed.state.value != "READY":
            problems.append(f"feed state {feed.state.value}, want READY")

        # BUY: gate allows, fill prices at the ASK (§9)
        decision = feed.check_order("159852", side="BUY", quantity=200)
        if not decision.allowed:
            problems.append(f"BUY blocked: {decision.reason} {decision.detail}")
        else:
            buy_fill = feed.fill("159852", "BUY", 200, at=clock.now)
            if buy_fill.price != Decimal("1.052"):
                problems.append(f"BUY filled at {buy_fill.price}, want ask 1.052")
            if "ASK" not in str(buy_fill.price_source).upper():
                problems.append(f"BUY price source {buy_fill.price_source}")

        # SELL: fill prices at the BID
        sell_fill = feed.fill("159852", "SELL", 200, at=clock.now)
        if sell_fill.price != Decimal("1.048"):
            problems.append(f"SELL filled at {sell_fill.price}, want bid 1.048")

        # lot size enforced (A-share: multiples of 100)
        odd = feed.check_order("159852", side="BUY", quantity=150)
        if odd.allowed:
            problems.append("odd lot 150 was allowed")

        # no quote → no invention (§9: never invent a price)
        no_quote = feed.check_order("515880", side="BUY", quantity=100)
        if no_quote.allowed:
            problems.append("fill allowed without any quote")

        # A Paper fill is not a broker order: the disclaimer is part of
        # the contract and Paper order ids live in their own namespace.
        from services.market_data.paper.paper_market_feed import DISCLAIMER

        if "NO REAL MONEY" not in DISCLAIMER.upper():
            problems.append(f"disclaimer missing: {DISCLAIMER!r}")
        try:
            feed.fill("513050", "BUY", 100, at=clock.now)
            problems.append("fill on quoteless symbol did not raise")
        except PaperBlockedError:
            pass  # expected — the gate refuses

        passed = not problems
        return GateResult(
            "G8", GATE_LABELS["G8"], passed,
            "BUY@ask / SELL@bid simulated from real quotes; lot size "
            "enforced; no quote → no fill; PAPER disclaimer present"
            if passed else _fail_list(problems),
            data={"feed_state": feed.state.value},
        )

    # ════════════════════════════════════════════════════════════
    # G9 — Replay
    # ════════════════════════════════════════════════════════════

    def g09_replay(self) -> GateResult:
        from services.market_data.replay.replay_config import ReplayConfig
        from services.market_data.replay.replay_engine import ReplayEngine

        problems: list[str] = []
        engine = ReplayEngine(
            config=ReplayConfig(enabled=True, default_limit=45, max_limit=120),
            autostart=False,
        )
        window = {
            "start": cst(9, 30),
            "end": cst(15, 0),
        }

        # Deterministic Replay: same input + same config = same event
        # sequence, at every pacing (1x / 10x / 100x).
        digests: dict[str, str] = {}
        for speed in (1, 10, 100):
            engine.set_speed(speed)
            run = engine.load(["159852"], limit=45, **window)
            digests[f"{speed}x"] = run.digest
            if run.events_total == 0:
                problems.append(f"{speed}x loaded 0 events")
        if len(set(digests.values())) != 1:
            problems.append(f"digests differ across speeds: {digests}")

        # stepped manual replay matches the planned timeline twice
        sequences: list[list] = []
        for _ in range(2):
            engine.set_speed(0)
            engine.load(["159852"], limit=45, **window)
            emitted = []
            while True:
                event = engine.step()
                if event is None:
                    break
                emitted.append((event.sequence, event.bar_id))
            sequences.append(emitted)
        if sequences[0] != sequences[1]:
            problems.append("manual step replay is not reproducible")
        manual_digest = hashlib.sha1(
            "|".join(bid for _seq, bid in sequences[0]).encode("utf-8")
        ).hexdigest()
        if manual_digest != digests["1x"]:
            problems.append("stepped sequence digest != load digest")

        passed = not problems
        return GateResult(
            "G9", GATE_LABELS["G9"], passed,
            "deterministic replay: identical event sequence at 1x/10x/"
            "100x and across repeated manual runs"
            if passed else _fail_list(problems),
            data={
                "digests": digests,
                "events": len(sequences[0]) if sequences else 0,
            },
        )

    # ════════════════════════════════════════════════════════════
    # G10 — Monitoring
    # ════════════════════════════════════════════════════════════

    def g10_monitoring(self) -> GateResult:
        from services.market_data.monitoring import market_data_metrics as mdm
        from services.market_data.monitoring.monitoring_models import (
            MarketDataHealth,
        )

        problems: list[str] = []
        # §23 — every required metric exists, by the name Prometheus
        # actually exports.  prometheus_client keeps the declared name on
        # ``_name`` and appends ``_total`` only when a Counter is
        # exported, so the check reconstructs the exported name rather
        # than trusting the constant.
        declared: dict[str, str] = {}
        for const_name in (
            "QUOTES_RECEIVED", "BARS_RECEIVED", "QUOTE_AGE", "LATENCY",
            "LATENCY_P95", "STALE_TOTAL", "INVALID_TOTAL",
            "DUPLICATE_TOTAL", "GAP_TOTAL", "QUARANTINE_TOTAL",
            "RECONNECT_TOTAL", "ERRORS_TOTAL", "CACHE_HIT_TOTAL",
            "CACHE_MISS_TOTAL",
        ):
            metric = getattr(mdm, const_name, None)
            if metric is None:
                problems.append(f"metric constant {const_name} missing")
                continue
            name = getattr(metric, "_name", None)
            if not name:
                continue
            exported = (
                f"{name}_total"
                if type(metric).__name__ == "Counter" else name
            )
            declared[const_name] = exported
        missing_metrics = [
            required for required in REQUIRED_METRICS
            if required not in declared.values()
        ]
        if missing_metrics:
            problems.append(
                f"metrics not declared: {sorted(missing_metrics)}"
            )
        counters = getattr(mdm, "_COUNTER_SOURCES", {})
        for key in ("quotes_received_total", "bars_received_total",
                    "stale_events_total", "bar_gap_total"):
            if key not in counters:
                problems.append(f"counter source {key} missing")

        # health vocabulary visible to Dashboard / Grafana
        states = {s.value for s in MarketDataHealth}
        for needed in ("HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE"):
            if needed not in states:
                problems.append(f"health state {needed} missing")

        # The sync path consumes the documented snapshot shape and must
        # never raise — including when it is handed something else.
        clock = vclock(10, 31)
        _gate, service = self._quality_pipeline(clock)
        service.update(self.make_quote("159852", clock=clock), now=clock.now)
        for junk in (None, object(), [1, 2, 3], "not a snapshot"):
            mdm.update_from_snapshot(junk)     # never raises, by contract

        stats = service.stats()
        views = service.snapshot()
        if not isinstance(views, list) or not views:
            problems.append("QuoteService.snapshot() returned no views")
        age_ms = (
            (views[0].get("quality") or {}).get("quote_age_ms")
            if views else None
        )
        mdm.update_from_snapshot({
            "quotes_received_total": stats.get("quotes_accepted", 0),
            "bars_received_total": 0,
            "stale_events_total": stats.get("quality_rejected", 0),
            "invalid_quote_total": stats.get("quotes_rejected", 0),
            "metrics": {"latency": {"avg_ms": 25.0, "p95_ms": 31.0}},
            "symbols": {"items": views},
        })
        # the sync must reach the labelled series, not just not-raise
        try:
            gauge = mdm.QUOTE_AGE.labels(symbol="159852")._value.get()
        except Exception:  # noqa: BLE001 — client optional / private API
            gauge = None
        if gauge is not None and age_ms is not None:
            if abs(gauge - age_ms / 1000.0) > 1e-9:
                problems.append(
                    f"quote_age gauge {gauge}s != verdict {age_ms}ms"
                )
        observed = {
            "declared": declared,
            "health_states": sorted(states),
            "quotes_accepted": stats.get("quotes_accepted"),
            "quote_age_seconds": gauge,
            "prometheus_client": mdm.available(),
        }
        passed = not problems
        return GateResult(
            "G10", GATE_LABELS["G10"], passed,
            f"{len(REQUIRED_METRICS)}/{len(REQUIRED_METRICS)} metrics "
            "declared by their exported names; sync path never raises; "
            "HEALTHY/DEGRADED/BLOCKED/OFFLINE vocabulary intact"
            if passed else _fail_list(problems),
            data=observed,
        )

    # ════════════════════════════════════════════════════════════
    # G11 — Broker Adapter
    # ════════════════════════════════════════════════════════════

    def g11_broker_adapter(self) -> GateResult:
        from services.market_data.adapters.broker import (
            BrokerConnectionState,
            BrokerMarketDataAdapter,
            SimulatedBrokerProvider,
            SubscriptionState,
        )
        from services.market_data.config.broker_config import (
            BrokerMarketDataConfig,
        )

        clock = vclock(10, 31)
        config = BrokerMarketDataConfig.from_env()
        config = type(config)(
            enabled=True,
            provider="simulated",
            reconnect_seconds=0,
            max_reconnect_attempts=3,
            resubscribe_on_reconnect=True,
        )
        provider = SimulatedBrokerProvider(seed=PROVIDER_SEED, clock=clock)
        adapter = BrokerMarketDataAdapter(
            provider, config=config, clock=clock, max_quotes=80
        )
        adapter.connect()
        adapter.subscribe_universe()

        problems: list[str] = []
        first_quotes: set[str] = set()
        for quote in adapter.stream():
            first_quotes.add(quote.symbol)
            if len(first_quotes) >= 3:
                break
        if not first_quotes:
            problems.append("no quotes before disconnect")

        # inject a broker disconnect mid-stream
        provider.simulate_disconnect()
        resubscribes_before = len(provider.subscribe_calls)
        reconnected_quotes: set[str] = set()
        for quote in adapter.stream():
            reconnected_quotes.add(quote.symbol)
            if len(reconnected_quotes) >= 3:
                break
        state = adapter.connection_state()
        if state is not BrokerConnectionState.STREAMING:
            problems.append(f"state after reconnect: {state.value}")
        if adapter.reconnect_count() < 1:
            problems.append("adapter counted no reconnect")
        if len(provider.subscribe_calls) <= resubscribes_before:
            problems.append("adapter did not RESUBSCRIBE after reconnect")
        if adapter.subscription_state() is not SubscriptionState.SUBSCRIBED:
            problems.append(
                f"subscription state {adapter.subscription_state().value}"
            )
        if not reconnected_quotes:
            problems.append("no quotes resumed after reconnect")

        adapter.disconnect()
        passed = not problems
        return GateResult(
            "G11", GATE_LABELS["G11"], passed,
            "connect → subscribe → stream; disconnect → reconnect → "
            "RESUBSCRIBE → quotes resumed"
            if passed else _fail_list(problems),
            data={
                "subscribe_calls": len(provider.subscribe_calls),
                "quotes_before": sorted(first_quotes),
                "quotes_after": sorted(reconnected_quotes),
            },
        )

    # ════════════════════════════════════════════════════════════
    # G12 — Account Sync
    # ════════════════════════════════════════════════════════════

    def g12_account_sync(self) -> GateResult:
        from services.account.sync.config import AccountSyncConfig
        from services.account.sync.service import build_default_account_service

        config = AccountSyncConfig.from_env()
        service = build_default_account_service(config, account_id="E2E001")
        problems: list[str] = []

        service.connect()
        snapshots = [service.sync() for _ in range(3)]
        last = snapshots[-1]

        balance = last.balance
        for field_name in ("total_asset", "cash", "available_cash",
                           "frozen_cash", "market_value"):
            value = getattr(balance, field_name, None)
            if value is None:
                problems.append(f"balance field {field_name} is None")

        if service.last_successful_sync("E2E001") is None:
            problems.append("last successful sync not recorded")
        if last.sync_latency_ms is None:
            problems.append("sync latency not recorded")

        # §7 — snapshot history is append-only: #1..#3 all retained.
        # The store serves newest-first; the invariant under test is that
        # nothing was overwritten, not the sort order of the view.
        history = service.snapshots("E2E001", limit=50)
        if len(history) < 3:
            problems.append(f"snapshot history has {len(history)} < 3")
        sequences = [s.sequence for s in history]
        if sequences != sorted(sequences, reverse=True):
            problems.append(f"snapshot view is not newest-first: {sequences}")
        if set(sequences) != set(range(1, len(sequences) + 1)):
            problems.append(
                f"snapshot history is not append-only: {sequences}"
            )

        # §12 — STALE / ERROR surface as blocking states
        stale_ids = service.mark_stale()  # virtual clock: nothing stale yet
        if not isinstance(stale_ids, list):
            problems.append("mark_stale did not return a list")
        # ERROR: disconnect the adapter then sync
        service.adapter.disconnect()
        try:
            service.sync()
            problems.append("sync succeeded on a disconnected adapter")
        except Exception:
            pass  # expected — a broken channel must raise, not fake data
        if not service.new_orders_blocked():
            problems.append("ERROR state does not block new orders")
        self._record_injection(
            "G12/adapter-disconnect", "sync ERROR + orders blocked",
            service.state("E2E001"), blocked=service.new_orders_blocked(),
        )

        passed = not problems
        return GateResult(
            "G12", GATE_LABELS["G12"], passed,
            "balance fields + latency captured; 3 snapshots retained in "
            "order; disconnect → ERROR → orders blocked"
            if passed else _fail_list(problems),
            data={
                "snapshots": len(history),
                "sequences": sequences,
                "state_after_disconnect": service.state("E2E001"),
            },
        )

    # ════════════════════════════════════════════════════════════
    # G13 — Position Sync
    # ════════════════════════════════════════════════════════════

    def _account_service(self, account_id: str, *, prices=None, ledger=None):
        """Real account-sync service; only the provider/price seams are
        scripted (simulated provider + mapping price provider)."""
        from services.account.sync.config import AccountSyncConfig
        from services.account.sync.service import (
            build_default_account_service,
            demo_ledger,
        )
        from services.account.sync.valuation import MappingPriceProvider

        service = build_default_account_service(
            AccountSyncConfig.from_env(),
            price_provider=(
                None if prices is None else MappingPriceProvider(prices)
            ),
            ledger=ledger if ledger is not None else demo_ledger(account_id),
            account_id=account_id,
        )
        service.connect()
        return service

    @staticmethod
    def _ledger_reader(account_id: str, *, q159852: int = 10000):
        """Ledger mirroring the simulated broker, with a knob to deviate
        (G14's mismatch case).  Cost/market-value legs are left unset on
        purpose: those checks are *skipped*, never faked."""
        from services.account.sync.ledger import (
            InMemoryPositionLedgerReader,
            LedgerPosition,
        )

        reader = InMemoryPositionLedgerReader()
        reader.set_positions(
            account_id,
            [
                LedgerPosition(
                    account_id=account_id, symbol="159852",
                    quantity=q159852, available_quantity=q159852,
                ),
                LedgerPosition(
                    account_id=account_id, symbol="159559",
                    quantity=20000, available_quantity=0,
                ),
                LedgerPosition(
                    account_id=account_id, symbol="513050",
                    quantity=5000, available_quantity=5000,
                ),
            ],
        )
        return reader

    def g13_position_sync(self) -> GateResult:
        problems: list[str] = []
        account_id = "E2E013"
        price_159852 = Decimal("1.100")
        # Only one symbol carries a real Market Data price — the other two
        # must stay *unvalued*, never valued at a fabricated zero.
        service = self._account_service(
            account_id, prices={"159852": str(price_159852)}
        )
        snapshot = service.sync(account_id)
        positions = {p.symbol: p for p in snapshot.positions}

        if len(positions) != 3:
            problems.append(f"synced {len(positions)} positions, want 3")

        for symbol, pos in sorted(positions.items()):
            for field_name in (
                "quantity", "available_quantity", "frozen_quantity",
                "average_cost",
            ):
                if getattr(pos, field_name, None) is None:
                    problems.append(f"{symbol}: {field_name} is None")
            if not pos.consistent:
                problems.append(
                    f"{symbol}: inconsistent — {pos.inconsistencies()}"
                )
            if not pos.is_valid:
                problems.append(
                    f"{symbol}: invalid — {pos.inconsistencies()}"
                )
            if pos.available_quantity > pos.quantity:
                problems.append(f"{symbol}: available > quantity")

        # §3 / A股 T+1 — today's buy is frozen: 20000 held, 0 sellable.
        # ``available = quantity`` would be the classic silent T+1 bug.
        t1 = positions.get("159559")
        if t1 is None:
            problems.append("159559 missing from the synced snapshot")
        else:
            if t1.quantity != Decimal("20000"):
                problems.append(f"159559 quantity {t1.quantity} != 20000")
            if t1.available_quantity != Decimal("0"):
                problems.append(
                    f"159559 available {t1.available_quantity}, want 0 (T+1)"
                )
            if t1.frozen_quantity != Decimal("20000"):
                problems.append(
                    f"159559 frozen {t1.frozen_quantity}, want 20000 (T+1)"
                )
            if t1.available_quantity == t1.quantity and t1.quantity > 0:
                problems.append(
                    "159559 available_quantity was derived from quantity — "
                    "the A-share T+1 lock is lost"
                )
            if not t1.consistent:
                problems.append("T+1 position is not quantity = available + frozen")

        # §18 — valuation comes from the one Market Data price system.
        priced = positions.get("159852")
        if priced is None:
            problems.append("159852 missing from the synced snapshot")
        elif priced.market_price is None:
            problems.append("159852 has a price but no market_price")
        else:
            if priced.market_price != price_159852:
                problems.append(
                    f"159852 market_price {priced.market_price} != "
                    f"{price_159852}"
                )
            want_value = price_159852 * priced.quantity
            if priced.market_value != want_value:
                problems.append(
                    f"159852 market_value {priced.market_value} != {want_value}"
                )
            want_pnl = (price_159852 - priced.average_cost) * priced.quantity
            if priced.unrealized_pnl != want_pnl:
                problems.append(
                    f"159852 unrealized_pnl {priced.unrealized_pnl} != {want_pnl}"
                )

        for symbol in ("159559", "513050"):
            pos = positions.get(symbol)
            if pos is None:
                continue
            if pos.market_price is not None or pos.market_value is not None:
                problems.append(
                    f"{symbol} was valued without a Market Data price "
                    "(fabricated valuation)"
                )
            if pos.unrealized_pnl is not None:
                problems.append(f"{symbol} invented an unrealized_pnl")

        # The same rule one level down: an explicit ``None`` price never
        # becomes a market value of 0.
        unlocked = positions.get("159559")
        if unlocked is not None:
            revalued = unlocked.with_valuation(None)
            if revalued.market_value is not None:
                problems.append(
                    "Position.with_valuation(None) produced a market_value"
                )

        passed = not problems
        return GateResult(
            "G13", GATE_LABELS["G13"], passed,
            "3 positions synced; quantity/available/frozen/cost present; "
            "T+1 20000/0/20000 preserved; valuation only from real prices"
            if passed else _fail_list(problems),
            data={
                "symbols": sorted(positions),
                "t_plus_1": {
                    "symbol": "159559",
                    "quantity": str(t1.quantity) if t1 else None,
                    "available_quantity": (
                        str(t1.available_quantity) if t1 else None
                    ),
                    "frozen_quantity": (
                        str(t1.frozen_quantity) if t1 else None
                    ),
                },
            },
        )

    # ════════════════════════════════════════════════════════════
    # G14 — Reconciliation
    # ════════════════════════════════════════════════════════════

    def g14_reconciliation(self) -> GateResult:
        problems: list[str] = []
        account_id = "E2E014"

        # A) broker == ledger → RECONCILED, orders allowed
        matched_ledger = self._ledger_reader(account_id)
        service = self._account_service(account_id, ledger=matched_ledger)
        service.sync(account_id)
        ok_report = service.report(account_id)
        if ok_report is None:
            problems.append("no reconciliation report after sync")
        else:
            if ok_report.failed:
                problems.append(
                    f"matched books reported FAIL ({ok_report.status})"
                )
            if ok_report.status != "RECONCILED":
                problems.append(
                    f"matched books status {ok_report.status}, "
                    "want RECONCILED"
                )
            if ok_report.matched == 0:
                problems.append("no item was actually compared")
        if service.new_orders_blocked(account_id):
            problems.append("matched books still block new orders")

        # B) broker = 10000, ledger = 8000 → MISMATCH → new orders blocked
        deviating = self._ledger_reader(account_id, q159852=8000)
        bad_service = self._account_service(account_id, ledger=deviating)
        bad_service.sync(account_id)
        bad_report = bad_service.report(account_id)
        if bad_report is None:
            problems.append("no reconciliation report for the mismatch case")
        else:
            if not bad_report.failed:
                problems.append(
                    f"ledger 8000 vs broker 10000 reported {bad_report.status} "
                    f"({bad_report.outcome})"
                )
            if bad_report.status != "MISMATCH":
                problems.append(
                    f"mismatch status {bad_report.status}, want MISMATCH"
                )
            if bad_report.mismatch == 0:
                problems.append("MISMATCH status but zero mismatch items")
            items = bad_report.items_for("159852")
            if not items:
                problems.append("no 159852 comparison item")
            else:
                qty_items = [
                    i for i in items if i.check == "POSITION_QUANTITY"
                ]
                if not qty_items:
                    problems.append("no POSITION_QUANTITY check for 159852")
                else:
                    item = qty_items[0]
                    if item.broker_value != Decimal("10000"):
                        problems.append(
                            f"broker side reads {item.broker_value}, want 10000"
                        )
                    if item.ledger_value != Decimal("8000"):
                        problems.append(
                            f"ledger side reads {item.ledger_value}, want 8000"
                        )
        if not bad_service.new_orders_blocked(account_id):
            problems.append("MISMATCH does not block new orders")
        self._record_injection(
            "G14/position-mismatch", "MISMATCH + new orders blocked",
            (bad_report.status if bad_report else "no report"),
            blocked=bad_service.new_orders_blocked(account_id),
        )

        # C) §9 — the reconciler only *reports*: neither side was edited.
        after = {p.symbol: p for p in bad_service.latest(account_id).positions}
        broker_qty = after["159852"].quantity
        if broker_qty != Decimal("10000"):
            problems.append(
                f"broker position was tampered with ({broker_qty}) to clear "
                "the mismatch"
            )
        ledger_after = {
            p.symbol: p for p in deviating.positions(account_id)
        }
        if ledger_after["159852"].quantity != Decimal("8000"):
            problems.append(
                f"ledger position was auto-corrected to "
                f"{ledger_after['159852'].quantity} — a mismatch must never "
                "be silently fixed"
            )

        # D) books agree again → RECONCILED → orders allowed
        restored = self._ledger_reader(account_id)
        good_service = self._account_service(account_id, ledger=restored)
        good_service.sync(account_id)
        restored_report = good_service.report(account_id)
        if restored_report is None or restored_report.failed:
            problems.append("restored books did not reconcile")
        if good_service.new_orders_blocked(account_id):
            problems.append("restored books still block new orders")

        self.reconciliation = {
            "reconciled": ok_report.as_dict() if ok_report else None,
            "mismatch": bad_report.as_dict() if bad_report else None,
            "restored": (
                restored_report.as_dict() if restored_report else None
            ),
            "blocked_while_mismatched": bad_service.new_orders_blocked(
                account_id
            ),
            "ledger_untouched": (
                str(ledger_after["159852"].quantity)
                if "159852" in ledger_after else None
            ),
        }

        passed = not problems
        return GateResult(
            "G14", GATE_LABELS["G14"], passed,
            "10000/10000 → RECONCILED; 10000/8000 → MISMATCH + orders "
            "blocked; neither side auto-edited; restore → RECONCILED"
            if passed else _fail_list(problems),
            data={
                "matched_items": ok_report.matched if ok_report else 0,
                "mismatch_items": bad_report.mismatch if bad_report else 0,
            },
        )

    # ════════════════════════════════════════════════════════════
    # G15 — Shadow (the headline acceptance)
    # ════════════════════════════════════════════════════════════

    def _shadow_stack(self, clock: VirtualClock, *, prices=None,
                      account_id: str = "E2E015", feed=None,
                      quote_service=None, ledger=None, config=None,
                      symbols: Any = ("159852",)):
        """Real market data → quality → session → paper feed → shadow.

        ``feed``/``quote_service``/``ledger`` may be injected so G18 can
        run the same production service over a broker-backed feed or a
        deviating ledger — never a mocked shadow.
        """
        from services.execution.shadow.shadow_order import new_intent_id
        from services.shadow.service import (
            AccountSyncReference,
            ShadowTradingService,
        )
        from services.shadow.shadow_config import ShadowConfig

        _gate, built_quotes, _cache, _bars, built_feed = (
            self._build_paper_stack(clock, symbols=symbols)
        )
        quote_service = built_quotes if quote_service is None else quote_service
        feed = built_feed if feed is None else feed
        account = self._account_service(account_id, prices=prices,
                                        ledger=ledger)
        account.sync(account_id)
        service = ShadowTradingService(
            config=config or ShadowConfig(
                enabled=True,
                initial_capital=Decimal("1000000"),
                slippage_bps=0.0,
                commission_bps=0.0,
                ledger_path=None,
            ),
            feed=feed,
            account_reference=AccountSyncReference(account),
            clock=clock,
        )
        return service, quote_service, feed, account, new_intent_id

    def g15_shadow(self) -> GateResult:
        from services.execution.shadow.shadow_order import OrderIntent
        from services.shadow.shadow_gate import ShadowGateReason

        problems: list[str] = []
        clock = vclock(10, 31)
        account_id = "E2E015"
        service, quote_service, feed, account, new_intent_id = (
            self._shadow_stack(
                clock, account_id=account_id,
                symbols=("159852", "159559", "513050"),
            )
        )

        # Real market data in — the shadow session has nothing else.
        for symbol in ("159852", "159559", "513050"):
            self.ingest(quote_service, clock, symbol)
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        if feed.state.value != "READY":
            problems.append(f"feed {feed.state.value}, want READY")

        service.start()
        status = service.status()
        if status["mode"] != "SHADOW":
            problems.append(f"mode {status['mode']} != SHADOW")
        if status["real_orders_enabled"] is not False:
            problems.append("real_orders_enabled is not False")
        if status["feed"]["state"] != "READY":
            problems.append(f"status feed {status['feed']['state']}")

        # §19 — the strategy signal is logged before the intent exists.
        service.record_signal({
            "symbol": "159852", "side": "BUY", "quantity": 200,
            "strategy_id": "e2e-momentum", "reason": "price breakout",
        })
        intent = OrderIntent(
            intent_id=new_intent_id(),
            symbol="159852",
            side="BUY",
            quantity=200,
            strategy_id="e2e-momentum",
            timestamp=clock.now,
        )
        order = service.submit_intent(intent)

        if order.status != "FILLED":
            problems.append(f"order {order.status}: {order.reason}")
        if not order.order_id.startswith("SHD-"):
            problems.append(f"order id {order.order_id} not namespaced SHD-")
        if order.filled_quantity != 200:
            problems.append(f"filled {order.filled_quantity}, want 200")
        if order.avg_fill_price != Decimal("1.052"):
            problems.append(
                f"filled at {order.avg_fill_price}, want the ask 1.052"
            )

        fills = service.fills()
        if len(fills) != 1:
            problems.append(f"{len(fills)} fills, want 1")
        else:
            fill = fills[0]
            if not fill["fill_id"].startswith("SHDF-"):
                problems.append(
                    f"fill id {fill['fill_id']} not namespaced SHDF-"
                )
            if "ASK" not in str(fill["price_source"]).upper():
                problems.append(f"fill price source {fill['price_source']}")
            if Decimal(str(fill["price"])) != Decimal("1.052"):
                problems.append(f"fill price {fill['price']} != 1.052")
            if fill["commission"] is None:
                problems.append("fill has no commission field")

        # Shadow position — a second, isolated ledger (§15/§17).
        positions = {p["symbol"]: p for p in service.positions()}
        pos = positions.get("159852")
        if pos is None:
            problems.append("no shadow position after the fill")
        else:
            if pos["quantity"] != 200:
                problems.append(f"shadow quantity {pos['quantity']} != 200")
            if Decimal(str(pos["avg_cost"])) != Decimal("1.052"):
                problems.append(f"avg_cost {pos['avg_cost']} != 1.052")
            want_mv = Decimal("1.050") * 200      # marked at the last price
            if Decimal(str(pos["market_value"])) != want_mv:
                problems.append(
                    f"position market_value {pos['market_value']} != {want_mv}"
                )
            want_upnl = (Decimal("1.050") - Decimal("1.052")) * 200
            if Decimal(str(pos["unrealized_pnl"])) != want_upnl:
                problems.append(
                    f"unrealized {pos['unrealized_pnl']} != {want_upnl}"
                )

        # §23 PnL card — the identities must hold exactly.
        pnl = service.pnl()
        cash = Decimal(pnl["cash"])
        mv = Decimal(pnl["market_value"])
        equity = Decimal(pnl["equity"])
        total = Decimal(pnl["total_pnl"])
        if cash != Decimal("1000000") - Decimal("1.052") * 200:
            problems.append(f"shadow cash {cash} is not capital − notional")
        if equity != cash + mv:
            problems.append(f"equity {equity} != cash {cash} + mv {mv}")
        if total != equity - Decimal("1000000"):
            problems.append(f"total_pnl {total} != equity − capital")
        if Decimal(pnl["unrealized_pnl"]) != (Decimal("1.050") - Decimal("1.052")) * 200:
            problems.append(f"pnl unrealized {pnl['unrealized_pnl']}")
        if Decimal(pnl["realized_pnl"]) != 0:
            problems.append("a pure BUY produced realized PnL")

        # §19 decision trail: signal → intent → fill → position update
        events = service.events()
        chain = [e["type"] for e in events]
        for expected in ("SIGNAL", "ORDER_INTENT", "FILL", "POSITION_UPDATE"):
            if expected not in chain:
                problems.append(f"decision trail missing {expected}")
        if chain and chain[0] != "SESSION_STARTED":
            problems.append(f"trail starts with {chain[0]}")
        order_idx = [
            i for i, t in enumerate(chain)
            if t in ("SIGNAL", "ORDER_INTENT", "FILL", "POSITION_UPDATE")
        ]
        if order_idx != sorted(order_idx):
            problems.append(f"decision trail out of order: {chain}")

        # §18 — the broker side is strictly read-only: the comparison is
        # informational and the account book is untouched by the trade.
        comparison = service.broker_comparison()
        if comparison["real_orders_enabled"] is not False:
            problems.append("broker comparison says real orders are enabled")
        row_159852 = next(
            (r for r in comparison["rows"] if r["symbol"] == "159852"), None
        )
        if row_159852 is None:
            problems.append("no 159852 row in the broker comparison")
        else:
            if row_159852["broker_quantity"] != 10000:
                problems.append(
                    f"broker quantity changed to "
                    f"{row_159852['broker_quantity']} — Shadow wrote to the "
                    "broker book"
                )
            if row_159852["shadow_quantity"] != 200:
                problems.append(
                    f"shadow quantity {row_159852['shadow_quantity']} != 200"
                )
        broker_after = {
            p.symbol: p for p in account.latest(account_id).positions
        }
        if broker_after["159852"].quantity != Decimal("10000"):
            problems.append("the broker position moved after a shadow fill")

        # §24 — every blocking reason is reachable and named.
        blocked: dict[str, str] = {}

        def _blocked(name: str, intent_obj) -> None:
            decision = service.gate.evaluate(intent_obj)
            if decision.allowed:
                problems.append(f"{name}: gate allowed (expected block)")
            else:
                blocked[name] = decision.reason

        _blocked("EXCESS_NOTIONAL", OrderIntent(
            intent_id=new_intent_id(), symbol="159852", side="BUY",
            quantity=200000, strategy_id="e2e",
        ))
        _blocked("SHORT_SELL", OrderIntent(
            intent_id=new_intent_id(), symbol="513050", side="SELL",
            quantity=100, strategy_id="e2e",
        ))
        # The cash check only fires once the *notional cap* has passed —
        # so this probe runs on its own book: tiny capital, raised cap.
        # Otherwise EXCESS_NOTIONAL would answer first and the cash path
        # would never actually be exercised.
        from services.shadow.shadow_config import ShadowConfig

        poor_clock = vclock(10, 31)
        poor, poor_quotes, _poor_feed, _poor_acct, poor_new = (
            self._shadow_stack(
                poor_clock, account_id="E2E015b",
                config=ShadowConfig(
                    enabled=True,
                    initial_capital=Decimal("1000"),
                    max_order_notional=Decimal("10000000"),
                    slippage_bps=0.0,
                    commission_bps=0.0,
                    ledger_path=None,
                ),
            )
        )
        self.ingest(
            poor_quotes, poor_clock, "159852", bid="1.048", ask="1.052"
        )
        poor.start()
        poor_decision = poor.gate.evaluate(OrderIntent(
            intent_id=poor_new(), symbol="159852", side="BUY",
            quantity=5000, strategy_id="e2e",
        ))
        if poor_decision.allowed:
            problems.append(
                "INSUFFICIENT_CASH: a 5260 CNY order passed on 1000 CNY"
            )
        else:
            blocked["INSUFFICIENT_CASH"] = poor_decision.reason
        # a feed whose session has closed must stop new shadow orders
        clock.set(cst(16, 0))          # outside the trading session
        _blocked("SESSION_CLOSED", OrderIntent(
            intent_id=new_intent_id(), symbol="159852", side="BUY",
            quantity=200, strategy_id="e2e",
        ))

        expected_reasons = {
            "EXCESS_NOTIONAL": ShadowGateReason.EXCESS_NOTIONAL.value,
            "SHORT_SELL": ShadowGateReason.SHORT_SELL_BLOCKED.value,
            "INSUFFICIENT_CASH": ShadowGateReason.INSUFFICIENT_CASH.value,
        }
        for name, want in expected_reasons.items():
            got = blocked.get(name)
            if got != want:
                problems.append(f"{name}: reason {got}, want {want}")
        if blocked.get("SESSION_CLOSED") is None:
            problems.append("SESSION_CLOSED produced no block reason")

        for name, reason in sorted(blocked.items()):
            self._record_injection(
                f"G15/{name}", "shadow order blocked", reason, blocked=True,
            )

        passed = not problems
        return GateResult(
            "G15", GATE_LABELS["G15"], passed,
            "signal → intent → gate → simulated fill @ask → shadow "
            "position → PnL; broker read-only; 4 block codes reachable"
            if passed else _fail_list(problems),
            data={
                "order_id": order.order_id,
                "fill_id": fills[0]["fill_id"] if fills else None,
                "pnl": {
                    "cash": pnl["cash"], "equity": pnl["equity"],
                    "total_pnl": pnl["total_pnl"],
                },
                "decision_trail": chain,
                "blocked": blocked,
            },
        )

    # ════════════════════════════════════════════════════════════
    # G16 — Dashboard
    # ════════════════════════════════════════════════════════════

    def g16_dashboard(self) -> GateResult:
        problems: list[str] = []
        try:
            from apps.api.main import app
        except Exception as exc:  # noqa: BLE001
            return GateResult(
                "G16", GATE_LABELS["G16"], False,
                f"the API application could not be imported: {exc!r}",
            )

        routes = {getattr(r, "path", "") for r in app.routes}
        required_routes = {
            "market": [
                "/api/market-data/health",
                "/api/market-data/session",
                "/api/market-data/quotes",
                "/api/market-data/quotes/{symbol}",
                "/api/market-data/bars",
                "/api/market-data/quality",
            ],
            "account": [
                "/api/accounts",
                "/api/accounts/{account_id}",
                "/api/accounts/{account_id}/balance",
            ],
            "position": ["/api/accounts/{account_id}/positions"],
            "shadow": [
                "/api/shadow/status", "/api/shadow/orders",
                "/api/shadow/fills", "/api/shadow/positions",
                "/api/shadow/pnl", "/api/shadow/events",
            ],
            "monitoring": [
                "/api/dashboard/monitoring/center",
                "/api/dashboard/market-status",
                "/api/dashboard/market-cache",
                "/api/dashboard/reconciliation",
            ],
        }
        missing: dict[str, list[str]] = {}
        for area, wanted in required_routes.items():
            gone = [p for p in wanted if p not in routes]
            if gone:
                missing[area] = gone
                problems.append(f"{area} routes missing: {gone}")

        # The §22 banners must be in the shipped assets, not just in the
        # API payloads — otherwise a page could render unlabelled.
        static_root = self.repo_root / "apps" / "dashboard" / "static"
        markers = {
            "js/app.js": ["NO REAL MONEY", "PAPER"],
            "js/shadow.js": ["SHADOW", "DISABLED"],
        }
        for rel, needles in markers.items():
            path = static_root / rel
            if not path.exists():
                problems.append(f"static/{rel} is missing")
                continue
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                if needle not in text:
                    problems.append(
                        f"static/{rel} does not render {needle!r}"
                    )

        # The Shadow status payload itself must carry the §22 banner.
        clock = vclock(10, 31)
        service, quote_service, _feed, _acct, _new = (
            self._shadow_stack(clock, account_id="E2E016")
        )
        self.ingest(quote_service, clock, "159852")
        payload = service.status()
        if payload.get("mode") != "SHADOW":
            problems.append("shadow status has no SHADOW mode")
        if payload.get("real_orders_enabled") is not False:
            problems.append("shadow status does not disable real orders")
        if not isinstance(payload.get("counts"), dict):
            problems.append("shadow status has no counts block")

        # Monitoring vocabulary on the dashboard side.
        from services.account.domain.enums import AccountSyncHealth
        from services.market_data.monitoring.monitoring_models import (
            MarketDataHealth,
        )

        for enum_cls in (MarketDataHealth, AccountSyncHealth):
            values = {s.value for s in enum_cls}
            for needed in ("HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE"):
                if needed not in values:
                    problems.append(
                        f"{enum_cls.__name__} has no {needed} state"
                    )

        passed = not problems
        return GateResult(
            "G16", GATE_LABELS["G16"], passed,
            f"{sum(len(v) for v in required_routes.values())} dashboard "
            "endpoints present; PAPER / SHADOW banners rendered"
            if passed else _fail_list(problems),
            data={
                "routes_checked": sum(
                    len(v) for v in required_routes.values()
                ),
                "missing": missing,
                "api_route_total": len(routes),
            },
        )

    # ════════════════════════════════════════════════════════════
    # G17 — Security / Safety Gate (one-vote veto)
    # ════════════════════════════════════════════════════════════

    def g17_security(self) -> GateResult:
        from services.execution.shadow.shadow_order import OrderIntent
        from services.shadow.shadow_gate import ShadowGate
        from services.shadow.shadow_config import ShadowConfig
        from services.trading.mode import TradingMode

        problems: list[str] = []
        verdict: dict[str, Any] = {}

        # ── 1. code level: Shadow × BrokerOrderAdapter ─────────────
        forbidden_imports: list[str] = []
        forbidden_symbols: list[str] = []
        for rel in SHADOW_SOURCES:
            for path in (self.repo_root / rel).rglob("*.py"):
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if any(
                                alias.name.startswith(b)
                                for b in FORBIDDEN_BROKER_IMPORTS
                            ):
                                forbidden_imports.append(
                                    f"{path.name} → {alias.name}"
                                )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if any(
                            node.module.startswith(b)
                            for b in FORBIDDEN_BROKER_IMPORTS
                        ):
                            forbidden_imports.append(
                                f"{path.name} → {node.module}"
                            )
                forbidden_symbols.extend(
                    f"{path.name} → {name}"
                    for name in sorted(
                        _code_names(path) & FORBIDDEN_ORDER_NAMES
                    )
                )
        if forbidden_imports:
            problems.append(
                f"shadow imports the broker surface: {forbidden_imports}"
            )
        if forbidden_symbols:
            problems.append(
                f"shadow references order-submitting symbols: "
                f"{forbidden_symbols}"
            )
        verdict["shadow_broker_imports"] = forbidden_imports
        verdict["shadow_order_symbols"] = forbidden_symbols

        # ── 2. no broker order API exists at all ───────────────────
        from services.market_data.adapters.broker import (
            BrokerMarketDataAdapter,
        )

        order_like = sorted(
            name for name in dir(BrokerMarketDataAdapter)
            if "order" in name.lower()
            or any(
                verb in name.lower()
                for verb in ("place_", "submit_", "cancel_", "trade_")
            )
        )
        if order_like:
            problems.append(
                f"the broker adapter exposes an order surface: {order_like}"
            )
        verdict["broker_adapter_order_surface"] = order_like

        broker_pkg = self.repo_root / "services" / "broker"
        order_modules = sorted(
            str(p.relative_to(self.repo_root))
            for p in broker_pkg.rglob("*.py")
            if "order" in p.name.lower()
        )
        if order_modules:
            problems.append(f"broker order modules exist: {order_modules}")
        verdict["broker_order_modules"] = order_modules

        # ── 3. config level: SHADOW × LIVE ─────────────────────────
        for mode in (TradingMode.LIVE, TradingMode.PAPER):
            try:
                ShadowGate(
                    feed=None, account=None, positions=None,
                    config=ShadowConfig(enabled=True), mode=mode,
                )
                problems.append(
                    f"ShadowGate accepted mode {mode.value} — a shadow "
                    "session must refuse anything but SHADOW"
                )
            except ValueError:
                pass
            except Exception as exc:  # noqa: BLE001
                problems.append(
                    f"ShadowGate({mode.value}) raised {exc!r}, want the "
                    "documented ValueError"
                )
        shadow_gate = ShadowGate(
            feed=None, account=None, positions=None,
            config=ShadowConfig(enabled=True), mode=TradingMode.SHADOW,
        )
        if shadow_gate.mode is not TradingMode.SHADOW:
            problems.append("the default shadow gate is not in SHADOW mode")
        verdict["gate_mode"] = shadow_gate.mode.value

        # ── 4. CLI level: shadow × --live ──────────────────────────
        import contextlib
        import io

        from apps.runtime.__main__ import build_parser

        parser = build_parser()
        refused: list[str] = []
        for flag in ("--live", "--real-order", "--broker-order"):
            try:
                # argparse prints usage on refusal; that is expected, and
                # capturing it keeps the suite's own output readable.
                with contextlib.redirect_stderr(io.StringIO()):
                    parser.parse_args(["shadow", flag])
                problems.append(f"`shadow {flag}` was accepted by the CLI")
            except SystemExit:
                refused.append(flag)   # argparse rejected it, as intended
        if len(refused) != 3:
            problems.append(f"the CLI only refused {refused}")
        verdict["cli_flags_rejected"] = refused

        # ── 5. runtime: a real order proves the namespaces ─────────
        clock = vclock(10, 31)
        account_id = "E2E017"
        service, quote_service, feed, account, new_intent_id = (
            self._shadow_stack(clock, account_id=account_id)
        )
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        if feed.state.value != "READY":
            problems.append(f"feed {feed.state.value}, want READY")
        service.start()
        order = service.submit_intent(OrderIntent(
            intent_id=new_intent_id(), symbol="159852", side="BUY",
            quantity=200, strategy_id="e2e-safety",
        ))
        fills = service.fills()
        intent_ids = [
            e["payload"].get("intent_id")
            for e in service.events()
            if e["type"] == "ORDER_INTENT"
        ]
        verdict["order_id"] = order.order_id
        verdict["fill_id"] = fills[0]["fill_id"] if fills else None
        verdict["intent_id"] = intent_ids[0] if intent_ids else None

        if order.status != "FILLED":
            problems.append(f"the safety probe order was {order.status}")
        for label, value, prefix in (
            ("order", order.order_id, "SHD-"),
            ("fill", fills[0]["fill_id"] if fills else "", "SHDF-"),
            ("intent", intent_ids[0] if intent_ids else "", "SHIN-"),
        ):
            if not str(value).startswith(prefix):
                problems.append(
                    f"{label} id {value!r} is outside the {prefix} namespace "
                    "— it could collide with a broker id"
                )
        # A broker order id would have to come from somewhere; nothing in
        # the object graph belongs to the broker package.
        leaked: list[str] = []
        seen: set[int] = set()
        frontier: list[Any] = [service]
        for _depth in range(3):
            nxt: list[Any] = []
            for obj in frontier:
                if id(obj) in seen:
                    continue
                seen.add(id(obj))
                module = type(obj).__module__ or ""
                if module.startswith("services.broker"):
                    leaked.append(f"{type(obj).__name__} ({module})")
                attrs = getattr(obj, "__dict__", None)
                if isinstance(attrs, dict):
                    nxt.extend(attrs.values())
            frontier = nxt
        if leaked:
            problems.append(f"the shadow service holds broker objects: {leaked}")
        verdict["broker_objects_reachable"] = leaked
        verdict["broker_order_api_calls"] = 0

        # The read-only broker view is the *only* broker interaction.
        comparison = service.broker_comparison()
        if comparison["real_orders_enabled"] is not False:
            problems.append("the broker comparison enables real orders")
        if service.real_orders_enabled is not False:
            problems.append("the shadow service enables real orders")

        self.shadow_safety = {
            "verdict": "PASS" if not problems else "FAIL",
            "broker_order_api_calls": 0,
            "broker_order_modules": order_modules,
            "broker_adapter_order_surface": order_like,
            "shadow_broker_imports": forbidden_imports,
            "shadow_order_symbols": forbidden_symbols,
            "gate_mode": shadow_gate.mode.value,
            "rejected_gate_modes": ["LIVE", "PAPER"],
            "cli_flags_rejected": verdict.get("cli_flags_rejected"),
            "id_namespaces": {
                "intent": verdict.get("intent_id"),
                "order": verdict.get("order_id"),
                "fill": verdict.get("fill_id"),
            },
            "broker_objects_reachable": leaked,
            "real_orders_enabled": bool(service.real_orders_enabled),
            "problems": problems,
        }

        passed = not problems
        return GateResult(
            "G17", GATE_LABELS["G17"], passed,
            "0 broker order calls; SHD-/SHDF-/SHIN- namespaces; gate "
            "refuses LIVE/PAPER; CLI refuses --live"
            if passed else _fail_list(problems),
            data=verdict,
        )

    # ════════════════════════════════════════════════════════════
    # G18 — Failure Recovery
    # ════════════════════════════════════════════════════════════

    def _broker_feed(self, clock: VirtualClock, symbols=None):
        """A PaperMarketFeed whose quote source *is* the broker adapter.

        The only way "the broker link is down" can be observed by the
        paper/shadow stack rather than asserted: the instant the adapter
        leaves its subscribed/streaming state the source answers ``None``
        and the feed falls to OFFLINE on its own.
        """
        from services.market_data.adapters.broker import (
            BrokerMarketDataAdapter,
            SimulatedBrokerProvider,
        )
        from services.market_data.aggregation.bar_service import BarService
        from services.market_data.cache.cache_models import CacheConfig
        from services.market_data.cache.market_cache import MarketCache
        from services.market_data.config.broker_config import (
            BrokerMarketDataConfig,
        )
        from services.market_data.merge.bar_merge import BarMergeEngine
        from services.market_data.merge.historical_provider import (
            SyntheticHistoricalProvider,
        )
        from services.market_data.paper.paper_feed_config import (
            PaperFeedConfig,
        )
        from services.market_data.paper.paper_market_feed import (
            PaperMarketFeed,
        )

        base = BrokerMarketDataConfig.from_env()
        config = type(base)(
            enabled=True,
            provider="simulated",
            reconnect_seconds=0,
            max_reconnect_attempts=3,
            resubscribe_on_reconnect=True,
        )
        provider = SimulatedBrokerProvider(seed=PROVIDER_SEED, clock=clock)
        adapter = BrokerMarketDataAdapter(provider, config=config, clock=clock)
        source = _BrokerBackedQuoteSource(adapter)
        cache = MarketCache(
            config=CacheConfig(enabled=True, redis_url=None), clock=clock
        )
        bars = BarService()
        merge = BarMergeEngine(
            SyntheticHistoricalProvider(clock=clock),
            bar_service=bars,
            trading_calendar=calendar,
            market_cache=cache,
        )
        feed = PaperMarketFeed(
            config=PaperFeedConfig.from_env(),
            quote_service=source,
            bar_service=bars,
            merge_engine=merge,
            market_cache=cache,
            instrument_master=universe,
            clock=clock,
        )
        # The adapter needs its own subscription: connecting is not
        # enough to make it STREAMING, and a non-streaming adapter is
        # exactly what the source reports as "the broker link is down".
        adapter.connect()
        adapter.subscribe_universe()
        feed.subscribe(symbols or ["159852"])
        return adapter, provider, source, feed, bars, merge, cache

    def g18_failure_recovery(self) -> GateResult:
        from services.execution.shadow.shadow_order import OrderIntent
        from services.shadow.shadow_gate import ShadowGateReason

        problems: list[str] = []
        scenarios: dict[str, Any] = {}

        def _intent(intent_id: str, tag: str, **over):
            kwargs = dict(
                intent_id=intent_id, symbol="159852", side="BUY",
                quantity=100, strategy_id=f"e2e-{tag}",
            )
            kwargs.update(over)
            return OrderIntent(**kwargs)

        # ── A. the broker link dies → shadow refuses, then recovers ──
        clock = vclock(10, 31)
        adapter, provider, source, feed, _bars, _merge, _cache = (
            self._broker_feed(clock)
        )
        if not source.pull_until("159852"):
            problems.append("A: the broker stream never delivered 159852")
        if feed.state.value != "READY":
            problems.append(f"A: feed {feed.state.value} with a live link")

        service, _qs, _feed, _acct, new_intent_id = self._shadow_stack(
            clock, account_id="E2E018A", feed=feed
        )
        service.start()
        before = service.submit_intent(_intent(new_intent_id(), "a1"))
        if before.status != "FILLED":
            problems.append(f"A: live order {before.status} ({before.reason})")

        adapter.disconnect()
        if feed.state.value != "OFFLINE":
            problems.append(
                f"A: feed reads {feed.state.value} after the broker died"
            )
        dead = service.submit_intent(_intent(new_intent_id(), "a2"))
        if dead.status != "REJECTED":
            problems.append("A: an order was accepted with a dead broker link")
        elif dead.reason != ShadowGateReason.FEED_NOT_READY.value:
            problems.append(f"A: reason {dead.reason}")
        self._record_injection(
            "G18-A/broker-link-down", "FEED_NOT_READY", dead.reason,
            blocked=dead.status == "REJECTED",
        )

        adapter.connect()
        adapter.subscribe_universe()
        if not source.pull_until("159852"):
            problems.append("A: no quotes resumed after reconnect")
        if feed.state.value != "READY":
            problems.append(f"A: feed {feed.state.value} after recovery")
        after = service.submit_intent(_intent(new_intent_id(), "a3"))
        if after.status != "FILLED":
            problems.append(
                f"A: order after recovery {after.status} ({after.reason})"
            )
        scenarios["A_broker_link"] = {
            "before": before.status, "during": dead.status,
            "reason": dead.reason, "after": after.status,
            "reconnects": adapter.reconnect_count(),
            "quotes_after_recovery": source.pulled,
        }
        adapter.disconnect()

        # ── B. cache / Redis down → feed DEGRADED → shadow refuses ──
        clock = vclock(10, 31)
        backend = FlakyCacheBackend(clock)
        from services.market_data.cache.cache_models import CacheConfig
        from services.market_data.cache.market_cache import MarketCache

        cache = MarketCache(
            config=CacheConfig(enabled=True, redis_url=None),
            backend=backend, clock=clock,
        )
        _gate, quote_service, cache, _bars, feed = self._build_paper_stack(
            clock, cache=cache
        )
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        service, _qs, feed, _acct, new_intent_id = self._shadow_stack(
            clock, account_id="E2E018B", feed=feed, quote_service=quote_service
        )
        service.start()
        healthy = service.submit_intent(_intent(new_intent_id(), "b1"))
        if healthy.status != "FILLED":
            problems.append(f"B: warm-up order {healthy.status}")

        backend.failing = True
        # The degradation must be *recorded* by the cache's own failure
        # path — `trading_allowed()` reads the consecutive-failure count,
        # so simply flipping the stub is not enough.
        cache.set_quote(quote_service.latest("159852"))
        degraded_state = feed.state.value
        if degraded_state == "READY":
            problems.append(
                "B: the feed still reads READY with a failing cache backend"
            )
        degraded = service.submit_intent(_intent(new_intent_id(), "b2"))
        if degraded.status != "REJECTED":
            problems.append("B: an order was accepted on a degraded cache")
        self._record_injection(
            f"G18-B/cache-down (feed={degraded_state})", "FEED_NOT_READY",
            degraded.reason, blocked=degraded.status == "REJECTED",
        )

        backend.failing = False
        cache.health()          # the recovery probe clears the failure count
        recovered_state = feed.state.value
        if recovered_state != "READY":
            problems.append(f"B: feed {recovered_state} after the cache healed")
        healed = service.submit_intent(_intent(new_intent_id(), "b3"))
        if healed.status != "FILLED":
            problems.append(f"B: order after the cache healed {healed.status}")
        scenarios["B_cache"] = {
            "degraded_state": degraded_state, "during": degraded.status,
            "reason": degraded.reason, "recovered_state": recovered_state,
            "after": healed.status, "backend_failures": backend.failures,
        }

        # ── C. account sync ERROR → shadow refuses, then recovers ──
        clock = vclock(10, 31)
        service, quote_service, feed, account, new_intent_id = (
            self._shadow_stack(clock, account_id="E2E018C")
        )
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        service.start()
        warm = service.submit_intent(_intent(new_intent_id(), "c1"))
        if warm.status != "FILLED":
            problems.append(
                f"C: a healthy session refused the warm-up ({warm.reason})"
            )

        account.adapter.disconnect()
        try:
            account.sync("E2E018C")
            problems.append("C: sync succeeded on a disconnected adapter")
        except Exception:  # noqa: BLE001 — the break must raise
            pass
        if not account.new_orders_blocked("E2E018C"):
            problems.append("C: an account ERROR did not block new orders")
        blocked = service.submit_intent(_intent(new_intent_id(), "c2"))
        if blocked.status != "REJECTED":
            problems.append("C: shadow traded while the account sync was down")
        elif blocked.reason != ShadowGateReason.ACCOUNT_SYNC_BLOCKED.value:
            problems.append(f"C: reason {blocked.reason}")
        self._record_injection(
            "G18-C/account-sync-error",
            ShadowGateReason.ACCOUNT_SYNC_BLOCKED.value, blocked.reason,
            blocked=blocked.status == "REJECTED",
        )

        account.connect()
        account.sync("E2E018C")
        if account.new_orders_blocked("E2E018C"):
            problems.append("C: the account stayed blocked after reconnect")
        restored = service.submit_intent(_intent(new_intent_id(), "c3"))
        if restored.status != "FILLED":
            problems.append(
                f"C: order after recovery {restored.status} "
                f"({restored.reason})"
            )
        scenarios["C_account_sync"] = {
            "during": blocked.status, "reason": blocked.reason,
            "after": restored.status, "state": account.state("E2E018C"),
        }

        # ── D. reconciliation MISMATCH → shadow refuses, then heals ──
        clock = vclock(10, 31)
        ledger = self._ledger_reader("E2E018D", q159852=8000)
        service, quote_service, feed, account, new_intent_id = (
            self._shadow_stack(clock, account_id="E2E018D", ledger=ledger)
        )
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        service.start()
        report = account.report("E2E018D")
        if report is None or not report.failed:
            problems.append("D: the deviating ledger did not report a failure")
        mismatched = service.submit_intent(_intent(new_intent_id(), "d1"))
        if mismatched.status != "REJECTED":
            problems.append("D: shadow traded through a MISMATCH")
        elif mismatched.reason != ShadowGateReason.ACCOUNT_SYNC_BLOCKED.value:
            problems.append(f"D: reason {mismatched.reason}")
        self._record_injection(
            f"G18-D/reconciliation-{report.status if report else 'NONE'}",
            ShadowGateReason.ACCOUNT_SYNC_BLOCKED.value, mismatched.reason,
            blocked=mismatched.status == "REJECTED",
        )

        ledger.set_positions("E2E018D", self._ledger_reader(
            "E2E018D"
        ).positions("E2E018D"))
        account.sync("E2E018D")
        healed_report = account.report("E2E018D")
        if healed_report is not None and healed_report.failed:
            problems.append("D: the ledger fix did not clear the MISMATCH")
        after = service.submit_intent(_intent(new_intent_id(), "d2"))
        if after.status != "FILLED":
            problems.append(
                f"D: order after the ledger was fixed {after.status} "
                f"({after.reason})"
            )
        scenarios["D_reconciliation"] = {
            "mismatch_status": report.status if report else None,
            "during": mismatched.status, "reason": mismatched.reason,
            "after": after.status,
            "healed_status": healed_report.status if healed_report else None,
        }

        passed = not problems
        return GateResult(
            "G18", GATE_LABELS["G18"], passed,
            "4 injected faults (broker link / cache / account sync / "
            "reconciliation) each blocked new shadow orders and each "
            "recovered"
            if passed else _fail_list(problems),
            data=scenarios,
        )

    # ════════════════════════════════════════════════════════════
    # G19 — Determinism
    # ════════════════════════════════════════════════════════════

    def _shadow_digest(self, account_id: str) -> dict:
        """Replay one scripted shadow session and hash every artifact."""
        from services.execution.shadow.shadow_order import OrderIntent

        clock = vclock(10, 31)
        service, quote_service, _feed, _acct, new_intent_id = (
            self._shadow_stack(
                clock, account_id=account_id,
                symbols=("159852", "159559", "513050"),
            )
        )
        for symbol in ("159852", "159559", "513050"):
            self.ingest(quote_service, clock, symbol)
        self.ingest(
            quote_service, clock, "159852", bid="1.048", ask="1.052"
        )
        service.start()
        service.record_signal({
            "symbol": "159852", "side": "BUY", "quantity": 200,
            "strategy_id": "e2e-determinism",
        })
        for symbol, quantity in (("159852", 200), ("513050", 100)):
            service.submit_intent(OrderIntent(
                intent_id=new_intent_id(), symbol=symbol, side="BUY",
                quantity=quantity, strategy_id="e2e-determinism",
                timestamp=clock.now,
            ))
        payload = {
            "orders": [o.as_dict() for o in service.execution.orders()],
            "fills": service.fills(),
            "positions": service.positions(),
            "pnl": service.pnl(),
            "events": [
                {"type": e["type"], "payload": e["payload"]}
                for e in service.events()
            ],
        }
        canonical, ids = _canonicalise(payload)
        blob = json.dumps(
            canonical, ensure_ascii=False, sort_keys=True, default=str
        )
        shape_ok = all(
            re.fullmatch(r"(SHIN|SHD|SHDF)-[0-9A-F]{12}", raw)
            for raw in ids
        )
        return {
            "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "orders": len(payload["orders"]),
            "fills": len(payload["fills"]),
            "events": len(payload["events"]),
            "equity": payload["pnl"]["equity"],
            "ids": sorted(ids),
            "id_shape_ok": shape_ok,
            "payload": canonical,
            "raw_payload": payload,
        }

    def _provider_digest(self) -> dict:
        """The simulated vendor edge itself must be reproducible."""
        from services.market_data.adapters.broker import (
            BrokerMarketDataAdapter,
            SimulatedBrokerProvider,
        )
        from services.market_data.config.broker_config import (
            BrokerMarketDataConfig,
        )

        clock = vclock(10, 31)
        base = BrokerMarketDataConfig.from_env()
        config = type(base)(
            enabled=True, provider="simulated", reconnect_seconds=0,
            max_reconnect_attempts=3, resubscribe_on_reconnect=True,
        )
        provider = SimulatedBrokerProvider(seed=PROVIDER_SEED, clock=clock)
        adapter = BrokerMarketDataAdapter(
            provider, config=config, clock=clock, max_quotes=40
        )
        adapter.connect()
        adapter.subscribe_universe()
        frames = []
        for quote in adapter.stream():
            frames.append((
                quote.symbol, quote.timestamp.isoformat(),
                str(quote.last), str(quote.bid), str(quote.ask),
                quote.volume,
            ))
            if len(frames) >= 33:
                break
        adapter.disconnect()
        blob = json.dumps(frames, ensure_ascii=False, sort_keys=True)
        return {
            "sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            "frames": len(frames),
            "first": frames[0] if frames else None,
        }

    def g19_determinism(self) -> GateResult:
        problems: list[str] = []
        runs = [self._shadow_digest("E2E019") for _ in range(3)]
        digests = [r["sha256"] for r in runs]

        if len(set(digests)) != 1:
            problems.append(
                f"three identical shadow sessions produced "
                f"{len(set(digests))} different digests: {digests}"
            )
        first = runs[0]
        if first["orders"] != 2 or first["fills"] != 2:
            problems.append(
                f"the digest covers only {first['orders']} orders / "
                f"{first['fills']} fills — an empty run is trivially stable"
            )
        for idx in (1, 2):
            if runs[idx]["payload"] != first["payload"]:
                problems.append(
                    f"run {idx} differs from run 0 in the artifact payload"
                )

        # Ids are uuid4s by design, so the two things that must hold are:
        # the *shape* is the declared namespace, and no two runs share an
        # id — i.e. they were really generated, not hardcoded constants.
        if not all(r["id_shape_ok"] for r in runs):
            problems.append("generated ids left their declared namespace")
        if not first["ids"]:
            problems.append("the replay produced no order/fill ids at all")
        for idx in (1, 2):
            shared = set(runs[idx]["ids"]) & set(first["ids"])
            if shared:
                problems.append(f"run {idx} reused ids from run 0: {shared}")

        # The vendor edge must be reproducible too, or "deterministic"
        # would only mean "the fake at the top was constant".
        providers = [self._provider_digest() for _ in range(2)]
        if providers[0]["sha256"] != providers[1]["sha256"]:
            problems.append("the simulated provider stream is not reproducible")
        if providers[0]["frames"] < 33:
            problems.append(
                f"only {providers[0]['frames']} provider frames walked"
            )

        passed = not problems
        return GateResult(
            "G19", GATE_LABELS["G19"], passed,
            "3 shadow sessions → 1 digest; 2 seeded provider walks → "
            "1 digest; unique id namespaces; no wall clock in the "
            "decision path"
            if passed else _fail_list(problems),
            data={
                "shadow_sha256": digests[0],
                "shadow_runs": len(digests),
                "shadow_unique_digests": len(set(digests)),
                "ids_per_run": len(first["ids"]),
                "id_sample": first["ids"][:2],
                "provider_seed": PROVIDER_SEED,
                "provider_sha256": providers[0]["sha256"],
                "provider_frames": providers[0]["frames"],
                "equity": first["equity"],
            },
        )

    # ════════════════════════════════════════════════════════════
    # G20 — Final E2E (the whole chain, once)
    # ════════════════════════════════════════════════════════════

    def g20_final_e2e(self) -> GateResult:
        from services.execution.shadow.shadow_order import OrderIntent
        from services.market_data.adapters.broker import (
            SubscriptionState,
        )

        problems: list[str] = []
        chain: list[dict] = []
        clock = vclock(10, 31)
        account_id = "E2E020"

        def stage(name: str, ok: bool, detail: str, **evidence) -> bool:
            chain.append({
                "stage": name, "ok": bool(ok),
                "detail": detail, "evidence": evidence,
            })
            if not ok:
                problems.append(f"{name}: {detail}")
            return ok

        # 1) Provider → Adapter → MarketQuote (§1/§3)
        (adapter, provider, source, feed, bars, merge, cache) = (
            self._broker_feed(clock, symbols=UNIVERSE_SYMBOLS)
        )
        seen: set[str] = set()
        for _ in range(4):
            if source.pull(11) == 0:
                break
            for symbol in UNIVERSE_SYMBOLS:
                if source.latest(symbol) is not None:
                    seen.add(symbol)
        stage(
            "1 provider→adapter→quote",
            len(seen) == len(UNIVERSE_SYMBOLS)
            and adapter.subscription_state() is SubscriptionState.SUBSCRIBED,
            f"{len(seen)}/{len(UNIVERSE_SYMBOLS)} instruments streamed "
            f"({adapter.connection_state().value}/"
            f"{adapter.subscription_state().value})",
            instruments=len(seen),
            state=adapter.connection_state().value,
            subscription=adapter.subscription_state().value,
        )

        # 2) MarketQuote → Quality Gate (§5)
        gate, quote_service = self._quality_pipeline(clock)
        ingested: list[str] = []
        for symbol in UNIVERSE_SYMBOLS:
            quote = source.latest(symbol)
            if quote is None:
                continue
            quote_service.update(quote, now=clock.now)
            # the same gate-approved quote also feeds the realtime bar
            # side, so stage 4 merges two genuine sides (§7)
            bars.on_quote(quote)
            self._settle(clock, quote)
            ingested.append(symbol)
        verdicts = {s: quote_service.quality(s) for s in ingested}
        fresh = [
            s for s, v in verdicts.items()
            if v is not None and v.get("status") == "FRESH"
        ]
        stage(
            "2 quote→quality gate",
            len(ingested) == len(UNIVERSE_SYMBOLS)
            and len(fresh) == len(ingested),
            f"{len(fresh)}/{len(ingested)} quotes passed the gate as FRESH",
            ingested=len(ingested), fresh=len(fresh),
        )

        # 3) Quality → Cache (§6): the gate-approved quote is what is stored
        cached = 0
        for symbol in ingested:
            quote = quote_service.latest(symbol)
            if quote is None:
                continue
            if cache.set_quote(quote, quality=verdicts.get(symbol)):
                cached += 1
        hits = sum(
            1 for s in ingested if cache.get_quote(s) is not None
        )
        stage(
            "3 quality→cache",
            cached == len(ingested) and hits == len(ingested),
            f"{cached} writes, {hits} warm reads",
            writes=cached, hits=hits,
        )

        # 4) Merge: historical + realtime → one series (§7)
        series = merge.unified("159852", "1m", 30)
        merged = series["bars"]
        origins = sorted({str(src) for _bar, src in merged})
        stamps = [bar.timestamp.astimezone(CST) for bar, _src in merged]
        contiguous = all(
            b - a == timedelta(minutes=1) for a, b in zip(stamps, stamps[1:])
        )
        stage(
            "4 merged bars",
            len(merged) > 0
            and series["counts"]["total"] == len(merged)
            and series["counts"]["realtime"] >= 1
            and series["counts"]["historical"] >= 1
            and str(merged[-1][1]).upper() == "REALTIME"
            and contiguous,
            f"{len(merged)} bars "
            f"({series['counts']['historical']} historical + "
            f"{series['counts']['realtime']} realtime) from {origins}",
            bars=len(merged), counts=series["counts"],
            origins=origins,
            gaps=len(series.get("gaps") or []),
            junction=series.get("junction"),
        )

        # 5) Paper Trading: gate-approved quote → an allowed order (§8)
        decision = feed.check_order("159852", side="BUY", quantity=200)
        stage(
            "5 paper order decision",
            decision.allowed and decision.fill_price is not None,
            f"allowed={decision.allowed} fill={decision.fill_price} "
            f"from {decision.fill_price_source}",
            allowed=decision.allowed,
            fill_price=str(decision.fill_price),
            price_source=decision.fill_price_source,
        )

        # 6) Shadow: intent → gate → simulated fill (§16)
        account = self._account_service(account_id)
        from services.shadow.service import (
            AccountSyncReference,
            ShadowTradingService,
        )
        from services.shadow.shadow_config import ShadowConfig

        shadow = ShadowTradingService(
            config=ShadowConfig(
                enabled=True, initial_capital=Decimal("1000000"),
                slippage_bps=0.0, commission_bps=0.0, ledger_path=None,
            ),
            feed=feed,
            account_reference=AccountSyncReference(account),
            clock=clock,
        )
        shadow.start()
        shadow.record_signal({
            "symbol": "159852", "side": "BUY", "quantity": 200,
            "strategy_id": "e2e-final",
        })
        from services.execution.shadow.shadow_order import new_intent_id

        order = shadow.submit_intent(OrderIntent(
            intent_id=new_intent_id(), symbol="159852", side="BUY",
            quantity=200, strategy_id="e2e-final", timestamp=clock.now,
        ))
        fills = shadow.fills()
        fill_price = Decimal(str(fills[0]["price"])) if fills else None
        stage(
            "6 shadow execution",
            order.status == "FILLED" and len(fills) == 1,
            f"{order.order_id} {order.status} → "
            f"{fills[0]['fill_id'] if fills else 'no fill'} @ {fill_price}",
            order_id=order.order_id,
            fill_id=fills[0]["fill_id"] if fills else None,
            fill_price=str(fill_price),
        )
        # the fill must be the paper decision, not a re-derived price
        stage(
            "6b fill price = paper price",
            fill_price == decision.fill_price,
            f"shadow {fill_price} vs paper {decision.fill_price}",
            shadow=str(fill_price), paper=str(decision.fill_price),
        )

        # 7) Position / PnL (§23)
        positions = {p["symbol"]: p for p in shadow.positions()}
        pos = positions.get("159852")
        pnl = shadow.pnl()
        cash = Decimal(pnl["cash"])
        equity = Decimal(pnl["equity"])
        stage(
            "7 position & PnL",
            pos is not None
            and pos["quantity"] == order.filled_quantity
            and equity == cash + Decimal(pnl["market_value"])
            and Decimal(pnl["total_pnl"])
            == equity - Decimal("1000000"),
            f"{pos['quantity'] if pos else 0} shares, equity {equity}, "
            f"total {pnl['total_pnl']}",
            quantity=pos["quantity"] if pos else 0,
            cash=pnl["cash"], equity=pnl["equity"],
            total_pnl=pnl["total_pnl"],
            unrealized=pnl["unrealized_pnl"],
        )

        # 8) Account sync: the read-only broker side + T+1 (§24)
        account.sync(account_id)
        snapshot = account.latest(account_id)
        broker_positions = {p.symbol: p for p in snapshot.positions}
        t1 = broker_positions.get("159559")
        report = account.report(account_id)
        stage(
            "8 account sync & reconcile",
            t1 is not None
            and t1.available_quantity == 0
            and report is not None
            and not report.failed,
            f"159559 {t1.quantity}/{t1.available_quantity} (T+1), "
            f"reconcile={report.status if report else 'NONE'}",
            positions=len(broker_positions),
            t1_available=str(t1.available_quantity) if t1 else None,
            reconcile=report.status if report else None,
        )

        # 9) Dashboard: the same quote, read through the façade (§22)
        from services.market_data.market_data_service import (
            MarketDataService,
        )

        mds = MarketDataService(
            quote_service=quote_service,
            bar_service=bars,
            merge_engine=merge,
            market_cache=cache,
            universe=universe,
            clock=clock,
        )
        view = mds.quote("159852")
        view_ask = (
            Decimal(str(view["ask"])) if view.get("ask") is not None else None
        )
        stage(
            "9 dashboard read-back",
            view_ask is not None
            and view_ask == decision.fill_price
            and view["status"] == "LIVE",
            f"API {view['status']} ask={view_ask} == fill "
            f"{decision.fill_price}",
            status=view["status"], api_ask=str(view_ask),
            fill_price=str(decision.fill_price),
        )

        adapter.disconnect()

        verdict = {
            "stages": len(chain),
            "passed": sum(1 for c in chain if c["ok"]),
            "chain": chain,
            "shadow": shadow.status(),
            "reconciliation": report.status if report else None,
            "equity": pnl["equity"],
            "total_pnl": pnl["total_pnl"],
        }
        self.final_chain = verdict

        passed = not problems and all(c["ok"] for c in chain)
        return GateResult(
            "G20", GATE_LABELS["G20"], passed,
            f"the full chain ran end to end — "
            f"{verdict['passed']}/{verdict['stages']} stages, "
            f"equity {pnl['equity']}"
            if passed else _fail_list(problems),
            data=verdict,
        )


# ══════════════════════════════════════════════════════════════════
# Reports
# ══════════════════════════════════════════════════════════════════

ARTIFACT_DIR = Path("artifacts") / "market_data_e2e"

#: Every generated identifier the decision path emits.  ``new_intent_id()``
#: is a uuid4 **by design** — an id must be unique, not reproducible — so
#: determinism is asserted over the *decisions*, with ids normalised to
#: their order of first appearance.  Their shape is checked separately.
_ID_PATTERN = re.compile(r"\b(?:SHIN|SHD|SHDF)-[0-9A-F]{12}\b")


def _canonicalise(payload: Any) -> tuple[Any, dict[str, str]]:
    """Replace generated ids with stable placeholders, in order.

    Returns the canonical payload and the raw-id → placeholder map, so a
    caller can still assert that real ids were produced (and that no two
    runs produced the same ones).
    """
    seen: dict[str, str] = {}

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            def swap(match: "re.Match[str]") -> str:
                raw = match.group(0)
                return seen.setdefault(raw, f"<id#{len(seen) + 1}>")

            return _ID_PATTERN.sub(swap, node)
        if isinstance(node, dict):
            return {k: walk(v) for k, v in sorted(node.items())}
        if isinstance(node, (list, tuple)):
            return [walk(v) for v in node]
        return node

    return walk(payload), seen


def _dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _render_markdown(report: dict, runner: "MarketDataE2E") -> str:
    lines = [
        "# Commit 017 — End-to-End Validation: A-Share Market Data Track",
        "",
        f"**Gate: {report['gate']}** — "
        f"{report['passed']}/{report['total']} gates PASS",
        "",
        f"* suite: `{report['suite']}`",
        f"* virtual session: {report['virtual_session']['date']} "
        f"{report['virtual_session']['time']} "
        f"({report['virtual_session']['phase']})",
        f"* generated: {report['generated_at']} (provenance only — "
        "no wall clock enters the decision path)",
        "",
    ]
    repro = report.get("reproducibility") or {}
    if repro:
        lines += ["## Reproducibility", ""]
        lines.append(
            f"* decision digest: `{repro.get('decision_digest')}` "
            f"({repro.get('verified_by')})"
        )
        lines.append(
            f"* vendor stream digest: `{repro.get('provider_digest')}`"
        )
        for item in repro.get("stable") or []:
            lines.append(f"* reproduced: {item}")
        for item in repro.get("not_reproducible_by_design") or []:
            lines.append(
                f"* **not** reproducible by design — {item['what']}: "
                f"{item['why']} ({item['checked_by']})"
            )
        lines.append("")
    lines += [
        "## Gates",
        "",
        "| Gate | Name | Verdict | ms | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for gate in report["gates"]:
        mark = "PASS" if gate["passed"] else "**FAIL**"
        detail = str(gate["detail"]).replace("|", "\\|")
        lines.append(
            f"| {gate['gate']} | {gate['name']} | {mark} | "
            f"{gate['duration_ms']} | {detail[:180]} |"
        )
    lines += ["", "## Failure-injection matrix", ""]
    if runner.failure_injection:
        lines += [
            "Quote-level injections have no order to block (shown as `—`);",
            "their refusal is the finding. Order-level injections state",
            "whether the order was actually blocked.",
            "",
            "| Scenario | Expected | Observed | Order blocked |",
            "| --- | --- | --- | --- |",
        ]
        for row in runner.failure_injection:
            blocked = row["order_blocked"]
            lines.append(
                f"| {row['scenario']} | {row['expected']} | "
                f"{row['observed']} | "
                f"{'—' if blocked is None else blocked} |"
            )
        order_rows = [
            r for r in runner.failure_injection
            if r["order_blocked"] is not None
        ]
        lines += [
            "",
            f"* order-level injections: {len(order_rows)} — all blocked: "
            f"{all(r['order_blocked'] for r in order_rows)}",
            f"* quote-level injections: "
            f"{len(runner.failure_injection) - len(order_rows)} — refused "
            "before an order could exist",
        ]
    else:
        lines.append("_no faults injected_")

    lines += ["", "## Reconciliation evidence (G14)", ""]
    recon = runner.reconciliation or {}
    for name in ("reconciled", "mismatch", "restored"):
        snapshot = recon.get(name)
        if not snapshot:
            continue
        lines.append(
            f"* **{name}**: {snapshot.get('status')} — "
            f"matched {snapshot.get('matched')}, "
            f"mismatch {snapshot.get('mismatch')}"
        )
    lines.append(
        f"* orders blocked while mismatched: "
        f"{recon.get('blocked_while_mismatched')}"
    )
    lines.append(
        f"* ledger quantity after the reconciler ran: "
        f"{recon.get('ledger_untouched')} (never auto-corrected)"
    )

    lines += ["", "## Shadow safety matrix (G17)", ""]
    safety = runner.shadow_safety or {}
    lines += [
        f"* verdict: **{safety.get('verdict')}**",
        f"* broker order API calls: {safety.get('broker_order_api_calls')}",
        f"* broker modules defining orders: "
        f"{safety.get('broker_order_modules')}",
        f"* broker adapter order surface: "
        f"{safety.get('broker_adapter_order_surface')}",
        f"* shadow → broker imports: {safety.get('shadow_broker_imports')}",
        f"* shadow order symbols: {safety.get('shadow_order_symbols')}",
        f"* gate mode: {safety.get('gate_mode')} "
        f"(refused: {safety.get('rejected_gate_modes')})",
        f"* CLI flags refused: {safety.get('cli_flags_rejected')}",
        f"* id namespaces: {safety.get('id_namespaces')}",
        f"* real orders enabled: {safety.get('real_orders_enabled')}",
    ]

    chain = runner.final_chain or {}
    if chain:
        lines += ["", "## Final chain (G20)", ""]
        lines += ["| Stage | OK | Evidence |", "| --- | --- | --- |"]
        for row in chain.get("chain", []):
            lines.append(
                f"| {row['stage']} | {'yes' if row['ok'] else '**no**'} | "
                f"{str(row['evidence'])[:140]} |"
            )
    lines.append("")
    return "\n".join(lines)


def _reproducibility(results: list[GateResult]) -> dict:
    """State exactly what a re-run reproduces — and what it cannot.

    Two things in this suite are *deliberately* not reproducible, and
    saying so is the point: a report that claimed byte-stability while
    quietly embedding uuids and wall-clock latencies would be lying.
    Both exceptions are small, named, and each has its own gate proving
    the property they are there for.
    """
    by_gate = {r.gate: r.data for r in results}
    g19 = by_gate.get("G19", {}) or {}
    g17 = by_gate.get("G17", {}) or {}
    return {
        "verified_by": "G19",
        "decision_digest": g19.get("shadow_sha256"),
        "provider_digest": g19.get("provider_sha256"),
        "stable": [
            "every gate verdict and its detail",
            "shadow decisions: orders, fills, positions, pnl, events "
            "(ids normalised)",
            "the simulated vendor stream (seeded)",
        ],
        "not_reproducible_by_design": [
            {
                "what": "order / fill / intent ids",
                "why": "uuid4 — uniqueness is the requirement, not "
                       "repeatability",
                "checked_by": "G19: declared namespace shape, and no id "
                              "shared between runs",
                "observed": g19.get("id_sample"),
            },
            {
                "what": "account-sync latency",
                "why": "it measures the real broker round trip, i.e. "
                       "wall time, which a replay cannot pin",
                "checked_by": "G12: the sync is nevertheless fresh and "
                              "reconciled",
            },
        ],
        "cli_flags_refused": g17.get("cli_flags_rejected"),
    }


def generate_reports(runner: "MarketDataE2E",
                     results: list[GateResult]) -> dict:
    """Write the five Commit 017 artifacts and return the verdict."""
    artifacts = runner.artifacts
    artifacts.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    report = {
        "commit": "017",
        "suite": "market-data",
        "gate": "PASS" if passed == total else "FAIL",
        "passed": passed,
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reproducibility": _reproducibility(results),
        "virtual_session": {
            "date": VDATE.isoformat(),
            "time": "10:31",
            "timezone": "CST",
            "phase": MarketPhase.CONTINUOUS_AM.value,
        },
        "gates": [
            {
                "gate": r.gate, "name": r.name, "passed": r.passed,
                "detail": r.detail, "duration_ms": r.duration_ms,
                "data": r.data,
            }
            for r in results
        ],
    }
    _dump(artifacts / "e2e_report.json", report)
    (artifacts / "e2e_report.md").write_text(
        _render_markdown(report, runner), encoding="utf-8"
    )
    order_rows = [
        row for row in runner.failure_injection
        if row.get("order_blocked") is not None
    ]
    _dump(artifacts / "failure_injection.json", {
        "commit": "017",
        "scenarios": runner.failure_injection,
        "count": len(runner.failure_injection),
        # Only order-level injections can answer "did the order get
        # blocked?"; quote-level probe rows carry ``None`` by design.
        "order_level": len(order_rows),
        "all_orders_blocked": (
            all(row["order_blocked"] for row in order_rows)
            if order_rows else None
        ),
    })
    _dump(artifacts / "reconciliation_report.json", {
        "commit": "017",
        **runner.reconciliation,
    })
    _dump(artifacts / "shadow_safety_report.json", {
        "commit": "017",
        **runner.shadow_safety,
    })
    return report


def _print_summary(report: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        return
    print(
        f"COMMIT 017 MARKET DATA E2E — GATE: {report['gate']} "
        f"({report['passed']}/{report['total']})"
    )
    print(
        f"  virtual session {report['virtual_session']['date']} "
        f"{report['virtual_session']['time']} "
        f"{report['virtual_session']['timezone']} "
        f"({report['virtual_session']['phase']})"
    )
    for gate in report["gates"]:
        mark = "PASS" if gate["passed"] else "FAIL"
        print(
            f"  [{mark}] {gate['gate']} {gate['name']} "
            f"({gate['duration_ms']} ms)"
        )
        if not gate["passed"]:
            print(f"         {gate['detail']}")
    print(f"  artifacts → {ARTIFACT_DIR.as_posix()}/")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point (``python -m apps.runtime e2e``)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="market-data-e2e",
        description="Commit 017 — A-share market data track end-to-end "
                    "validation (20 gates, offline deterministic).",
    )
    parser.add_argument(
        "--suite", default="market-data", choices=["market-data"],
        help="which validation suite to run",
    )
    parser.add_argument(
        "--artifacts", default=None,
        help="artifact directory (default: artifacts/market_data_e2e)",
    )
    parser.add_argument(
        "--repo-root", default=None, help="repository root override",
    )
    parser.add_argument("--json", action="store_true", help="raw JSON output")
    parser.add_argument(
        "--gate", action="append", default=None, metavar="Gnn",
        help="run only the named gate(s), e.g. --gate G15",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else (
        Path(__file__).resolve().parents[2]
    )
    artifacts = (
        Path(args.artifacts).resolve() if args.artifacts
        else repo_root / ARTIFACT_DIR
    )
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    wanted = {g.upper() for g in args.gate} if args.gate else None
    runner = MarketDataE2E(artifacts, repo_root)
    results = runner.run(only=wanted)
    if wanted and not results:
        print(f"no gate matched {sorted(wanted)}", file=sys.stderr)
        return 2
    report = generate_reports(runner, results)
    _print_summary(report, as_json=args.json)
    return 0 if report["gate"] == "PASS" else 1


__all__ = [
    "GATE_LABELS",
    "GateResult",
    "MarketDataE2E",
    "VirtualClock",
    "generate_reports",
    "main",
]


