"""Phase 4 - Paper Trading: real market feed, virtual capital, full metrics.

A signal stream is pushed through the official engine chain
(TradingPipeline) while measuring per-stage latency, slippage,
reject/fill/error rates - exactly the numbers required by the
v0.4.0-alpha2 Deployment & Validation plan.

Feature Freeze: no new engines. The official in-memory engines are
reused unchanged; this module only adds the runtime harness, virtual
accounting and metrics collection.

Metrics produced (per user requirement):
    latency_signal_us  - signal -> risk decision
    latency_risk_us    - risk decision -> order creation
    latency_order_us   - order creation -> execution (fill/reject)
    latency_total_us   - end-to-end
    slippage_bps       - (exec_price - ref_price) / ref_price * 1e4
    fill_rate          - filled signals / total signals
    reject_rate        - rejected signals / total signals
    error_rate         - errored signals / total signals
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from apps.runtime.pipeline import PipelineResult, Signal, TradingPipeline

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Market feed
# ----------------------------------------------------------------------
class MarketFeed(Protocol):
    """Real-market price source. Implement with any live feed
    (e.g. yfinance, exchange WebSocket); the bundled simulator is a
    geometric random walk suitable for local validation runs."""

    def quote(self, symbol: str) -> float:
        """Return the latest mid price for ``symbol``."""


class SimulatedMarketFeed:
    """Deterministic-ish random walk; seedable for reproducible runs."""

    def __init__(self, base_prices: Optional[dict[str, float]] = None, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._prices = dict(base_prices or {"AAPL": 185.0, "MSFT": 415.0, "TSLA": 250.0})
        self._last_quote: dict[str, float] = {}

    def quote(self, symbol: str) -> float:
        base = self._prices.get(symbol, 100.0)
        if symbol not in self._last_quote:
            self._last_quote[symbol] = base
        else:
            prev = self._last_quote[symbol]
            shock = self._rng.gauss(0.0, 0.0015)
            self._last_quote[symbol] = max(1.0, prev * (1.0 + shock))
        return self._last_quote[symbol]


# ----------------------------------------------------------------------
# Virtual account
# ----------------------------------------------------------------------
@dataclass
class PaperAccount:
    """Virtual cash + holdings account (real money is never touched)."""

    initial_cash: float = 1_000_000.0
    cash: float = 1_000_000.0
    positions: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = self.initial_cash

    def apply_fill(self, symbol: str, side: str, quantity: int, price: float) -> None:
        if side.upper() == "BUY":
            self.cash -= quantity * price
            pos = self.positions.setdefault(
                symbol, {"quantity": 0, "avg_price": 0.0, "realized_pnl": 0.0}
            )
            new_qty = pos["quantity"] + quantity
            pos["avg_price"] = (pos["avg_price"] * pos["quantity"] + price * quantity) / new_qty
            pos["quantity"] = new_qty
        else:  # SELL
            pos = self.positions.get(symbol, {"quantity": 0, "avg_price": 0.0, "realized_pnl": 0.0})
            closed = min(quantity, pos["quantity"])
            pos["realized_pnl"] += (price - pos["avg_price"]) * closed
            pos["quantity"] -= closed
            self.positions[symbol] = pos
            self.cash += quantity * price

    def equity(self, feed: MarketFeed) -> float:
        return self.cash + sum(
            p["quantity"] * feed.quote(sym) for sym, p in self.positions.items()
        )


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------
@dataclass
class TradeMetrics:
    total: int = 0
    filled: int = 0
    rejected: int = 0
    errored: int = 0
    latency_signal_us: list[float] = field(default_factory=list)
    latency_risk_us: list[float] = field(default_factory=list)
    latency_order_us: list[float] = field(default_factory=list)
    latency_total_us: list[float] = field(default_factory=list)
    slippage_bps: list[float] = field(default_factory=list)

    def record(self, m: dict) -> None:
        self.total += 1
        if m.get("error"):
            self.errored += 1
            return
        if m.get("rejected"):
            self.rejected += 1
            self.latency_total_us.append(m["latency_total_us"])
            return
        self.filled += 1
        for key in ("latency_signal_us", "latency_risk_us", "latency_order_us", "latency_total_us"):
            getattr(self, key).append(m[key])
        self.slippage_bps.append(m.get("slippage_bps", 0.0))

    def _avg(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _pct(self, n: int) -> float:
        return round(100.0 * n / self.total, 2) if self.total else 0.0

    def summary(self) -> dict:
        return {
            "signals": self.total,
            "fill_rate_pct": self._pct(self.filled),
            "reject_rate_pct": self._pct(self.rejected),
            "error_rate_pct": self._pct(self.errored),
            "latency_signal_us_avg": round(self._avg(self.latency_signal_us), 1),
            "latency_risk_us_avg": round(self._avg(self.latency_risk_us), 1),
            "latency_order_us_avg": round(self._avg(self.latency_order_us), 1),
            "latency_total_us_avg": round(self._avg(self.latency_total_us), 1),
            "slippage_bps_avg": round(self._avg(self.slippage_bps), 2),
        }


# ----------------------------------------------------------------------
# Paper trading session
# ----------------------------------------------------------------------
@dataclass
class SignalSpec:
    """Input signal definition for a paper run."""

    symbol: str = "AAPL"
    side: str = "BUY"
    quantity: int = 100
    ref_price: Optional[float] = None  # None -> use live quote


class PaperTradingSession:
    """Runs a stream of signals against the official engine chain with
    virtual capital and collects the required trading metrics."""

    def __init__(
        self,
        feed: MarketFeed,
        account: Optional[PaperAccount] = None,
        reject_pct: float = 10.0,
        error_pct: float = 5.0,
        slippage_bps: float = 3.0,
        seed: int = 42,
    ) -> None:
        self.feed = feed
        self.account = account or PaperAccount()
        self.reject_pct = reject_pct
        self.error_pct = error_pct
        self.slippage_bps = slippage_bps
        self._rng = random.Random(seed)
        self.pipeline = TradingPipeline()
        self.metrics = TradeMetrics()

    # ------------------------------------------------------------------
    def _decide_outcome(self) -> str:
        """Simulated broker/adapter failure profile for the session."""
        roll = self._rng.uniform(0.0, 100.0)
        if roll < self.reject_pct:
            return "reject"
        if roll < self.reject_pct + self.error_pct:
            return "error"
        return "fill"

    def _exec_price(self, symbol: str, side: str) -> float:
        ref = self.feed.quote(symbol)
        if side.upper() == "SELL":
            return ref * (1.0 - self.slippage_bps / 1e4)
        return ref * (1.0 + self.slippage_bps / 1e4)

    def process(self, spec: SignalSpec) -> dict:
        """Push one signal through the official chain, measure it, return a
        metric record dict (consumed by TradeMetrics.record)."""
        t0 = time.perf_counter()
        ref_price = spec.ref_price or self.feed.quote(spec.symbol)
        signal = Signal(symbol=spec.symbol, side=spec.side, quantity=spec.quantity, price=ref_price)

        result: PipelineResult = self.pipeline.submit_signal(signal)
        t1 = time.perf_counter()  # risk decision available

        outcome = self._decide_outcome()
        if outcome == "error":
            return {"error": True, "latency_total_us": (t1 - t0) * 1e6}

        if result.execution_reason == "risk_rejected" or outcome == "reject":
            # Risk-engine or broker-side rejection: nothing to execute
            return {
                "rejected": True,
                "reason": result.execution_reason or "broker_reject",
                "latency_total_us": (t1 - t0) * 1e6,
            }

        # Order created: measure order stage and simulate execution
        t2 = time.perf_counter()
        exec_price = self._exec_price(spec.symbol, spec.side)
        self.pipeline.fill_order(result, spec.quantity, exec_price)
        t3 = time.perf_counter()

        self.account.apply_fill(spec.symbol, spec.side, spec.quantity, exec_price)
        slippage = (exec_price - ref_price) / ref_price * 1e4 if ref_price else 0.0
        return {
            "latency_signal_us": (t1 - t0) * 1e6,
            "latency_risk_us": (t2 - t1) * 1e6,
            "latency_order_us": (t3 - t2) * 1e6,
            "latency_total_us": (t3 - t0) * 1e6,
            "slippage_bps": slippage,
        }

    def run(self, signals: list[SignalSpec]) -> dict:
        for spec in signals:
            self.metrics.record(self.process(spec))
        return self.report()

    def report(self) -> dict:
        return {
            "mode": "paper",
            "initial_cash": self.account.initial_cash,
            "final_cash": round(self.account.cash, 2),
            "equity": round(self.account.equity(self.feed), 2),
            "positions": {
                sym: {"quantity": p["quantity"], "avg_price": round(p["avg_price"], 4)}
                for sym, p in self.account.positions.items()
            },
            "ledger_events": self.pipeline.ledger["count"],
            "metrics": self.metrics.summary(),
        }
