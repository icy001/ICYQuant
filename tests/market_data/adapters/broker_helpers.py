"""Shared test doubles for the broker adapter tests (Commit 014).

Kept out of ``conftest.py`` on purpose: these are plain classes and
factory functions, not pytest fixtures, and they are reused by the
adapter / reconnect / subscription / E2E suites.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, Optional

from services.market_data.adapters.broker import (
    BrokerMarketDataAdapter,
    BrokerMarketDataProvider,
    SimulatedBrokerProvider,
)
from services.market_data.config.broker_config import BrokerMarketDataConfig
from services.market_data.exceptions.broker_market_data_error import (
    BrokerConnectionLostError,
)

#: China Standard Time — A-share exchange timezone.
CST = timezone(timedelta(hours=8), "Asia/Shanghai")

#: The Commit 002 universe, as fixed by the spec.
SEED_SYMBOLS = [
    "159852",
    "513050",
    "159890",
    "159559",
    "159569",
    "515880",
    "159871",
    "513310",
    "501225",
    "161116",
    "165520",
]

#: 2026-09-08 is a Tuesday → continuous trading 09:30–11:30.
TRADING_DAY = (2026, 9, 8)


def cst(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:
    """Build a tz-aware China Standard Time datetime."""
    return datetime(
        year, month, day, hour, minute, second, microsecond, tzinfo=CST
    )


class VirtualClock:
    """Manually advanced clock, so E2E tests never depend on wall time."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> datetime:
        self.now = self.now + timedelta(seconds=seconds)
        return self.now

    def set(self, value: datetime) -> datetime:
        self.now = value
        return self.now


def make_config(**overrides: Any) -> BrokerMarketDataConfig:
    """Broker config tuned for fast, deterministic tests."""
    base: dict = {
        "provider": "simulated",
        "timeout_seconds": 0.0,
        "reconnect_seconds": 0.0,
        "max_reconnect_attempts": 3,
    }
    base.update(overrides)
    return BrokerMarketDataConfig(**base)


class ScriptedProvider(BrokerMarketDataProvider):
    """Provider that replays an explicit list of frames.

    A frame may be:

    * a ``Mapping`` — handed to the adapter as-is;
    * an ``Exception`` instance — raised from ``poll`` (drop injection).

    Once the script is exhausted ``on_exhausted`` is invoked (wired to
    ``adapter.stop``) and ``poll`` returns ``None``, so ``list(
    adapter.stream())`` terminates instead of spinning forever.
    """

    def __init__(
        self,
        frames: Iterable[Any],
        *,
        name: str = "scripted",
    ) -> None:
        self._frames = list(frames)
        self._name = name
        self._cursor = 0
        self._alive = False
        self._subscribed: list[str] = []
        self.on_exhausted: Optional[Callable[[], None]] = None
        self.subscribe_calls: list[list[str]] = []

    @property
    def name(self) -> str:
        return self._name

    def open(self, config: BrokerMarketDataConfig) -> None:
        self._alive = True

    def close(self) -> None:
        self._alive = False

    def subscribe(self, symbols: list[str]) -> None:
        self._subscribed = list(symbols)
        self.subscribe_calls.append(list(symbols))

    def unsubscribe(self, symbols: list[str]) -> None:
        self._subscribed = [s for s in self._subscribed if s not in symbols]

    def poll(self, timeout: float) -> Optional[Mapping[str, Any]]:
        if not self._alive:
            raise BrokerConnectionLostError("scripted link is down")
        if self._cursor >= len(self._frames):
            if self.on_exhausted is not None:
                self.on_exhausted()
            return None
        frame = self._frames[self._cursor]
        self._cursor += 1
        if isinstance(frame, Exception):
            raise frame
        return frame

    def is_alive(self) -> bool:
        return self._alive


def make_adapter(
    provider: Optional[BrokerMarketDataProvider] = None,
    *,
    config: Optional[BrokerMarketDataConfig] = None,
    clock: Optional[VirtualClock] = None,
    latency_ms: int = 0,
    **kwargs: Any,
) -> BrokerMarketDataAdapter:
    """Build a broker adapter wired for deterministic tests.

    ``sleep`` is a no-op (no real reconnect delay).  When a
    :class:`VirtualClock` is supplied the adapter stamps
    ``received_timestamp`` from it, offset by ``latency_ms`` so
    ``MarketQuote.latency_ms`` is assertable.
    """
    if provider is None:
        provider = SimulatedBrokerProvider(seed=42)
    received_clock: Optional[Callable[[], datetime]] = None
    if clock is not None:
        offset = timedelta(milliseconds=latency_ms)
        received_clock = lambda: clock.now + offset  # noqa: E731
    return BrokerMarketDataAdapter(
        provider,
        config=config or make_config(),
        clock=received_clock,
        sleep=lambda _seconds: None,
        **kwargs,
    )


def run_script(
    frames: Iterable[Any],
    *,
    config: Optional[BrokerMarketDataConfig] = None,
    symbols: Iterable[str] = ("159852",),
    max_quotes: Optional[int] = None,
    clock: Optional[VirtualClock] = None,
    latency_ms: int = 0,
) -> tuple[BrokerMarketDataAdapter, ScriptedProvider, list]:
    """Run a scripted provider through a full connect→subscribe→stream
    cycle and return ``(adapter, provider, quotes)``."""
    provider = ScriptedProvider(frames)
    adapter = make_adapter(
        provider,
        config=config,
        clock=clock,
        latency_ms=latency_ms,
        max_quotes=max_quotes,
    )
    provider.on_exhausted = adapter.stop
    adapter.connect()
    adapter.subscribe(list(symbols))
    return adapter, provider, list(adapter.stream())


def raw_frame(
    symbol: str = "159852",
    *,
    last: Any = "1.050",
    bid: Any = "1.049",
    ask: Any = "1.050",
    timestamp: Any = None,
    received: Any = None,
    **extra: Any,
) -> dict:
    """A vendor-shaped raw quote frame (Chinese field names, §3)."""
    frame: dict = {
        "证券代码": symbol,
        "证券名称": f"ETF {symbol}",
        "最新价": last,
        "买一价": bid,
        "卖一价": ask,
        "买一量": 1200,
        "卖一量": 3400,
        "成交量": 123400,
        "成交额": "129876.00",
        "昨收": "1.040",
        "开盘": "1.045",
        "最高": "1.060",
        "最低": "1.030",
        "行情时间": timestamp if timestamp is not None else cst(
            *TRADING_DAY, 10, 31
        ),
    }
    if received is not None:
        frame["received_timestamp"] = received
    frame.update(extra)
    return frame


__all__ = [
    "CST",
    "SEED_SYMBOLS",
    "TRADING_DAY",
    "cst",
    "VirtualClock",
    "make_config",
    "ScriptedProvider",
    "make_adapter",
    "run_script",
    "raw_frame",
]
