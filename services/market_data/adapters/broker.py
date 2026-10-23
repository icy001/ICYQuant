"""Broker / provider market data adapter (Commit 014 §2 / §5 / §7 / §10).

This module is the *only* place where a vendor SDK is allowed to touch
ICYQuant.  It implements the Commit 001 :class:`MarketDataAdapter`
contract on top of a pluggable :class:`BrokerMarketDataProvider`::

    Broker / Market Data Provider      (vendor SDK, untrusted)
                │
                ▼
       BrokerMarketDataProvider        (open/close/subscribe/poll)
                │
                ▼
      BrokerMarketDataAdapter          (lifecycle + reconnect + health)
                │  raw dict
                ▼
       BrokerQuoteNormalizer           (→ MarketQuote)
                │
                ▼
      Commit 006 Quality Gate → Cache  (downstream, unchanged)

Layering (§5)
-------------
The core system knows ``MarketDataAdapter`` and ``MarketQuote`` — never
"provider A's SDK", "provider B's field names" or "provider C's wire
protocol".  Swapping brokers (or Mock → Replay → Broker, §13) is a
wiring change, not a rewrite::

    BrokerMarketDataAdapter
            ├── Provider A   (registered as a factory)
            ├── Provider B
            └── Provider C

Responsibilities (§9 / §12)
---------------------------
* Parse + map the vendor payload into ``MarketQuote`` (via the
  normalizer) — **no business judgement**.  ``last = -1`` is passed
  through so the Quality Gate can quarantine it.
* Run the connection lifecycle and, critically, **resubscribe after a
  reconnect** (§7).  Otherwise the adapter would report ``CONNECTED``
  while silently receiving nothing, and Paper/Strategy would trade on
  a dead feed.
* Expose *three distinct* health dimensions for Commit 013 Monitoring:

  ==================  ==============================================
  connection health   state / reconnect count / last error
  subscription health state (DESYNCED after a drop, until resubscribe)
  market-data health  last message time + age (staleness source)
  ==================  ==============================================

* **Never** touch Redis (§12) — asynchrony with Commit 007 Cache is
  deliberate, so the adapter stays unit-testable in isolation.
* **Never** create a second alerting system (§10) — a lost link is
  reported as state and Commit 013 raises ``MARKET_DATA_OFFLINE``.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Iterator, Mapping, Optional

from ..config.broker_config import BrokerMarketDataConfig
from ..domain.instrument import Instrument
from ..domain.quote import MarketQuote
from ..exceptions.broker_market_data_error import (
    BrokerConfigError,
    BrokerConnectionError,
    BrokerConnectionLostError,
    BrokerErrorCode,
    BrokerMarketDataError,
    BrokerMessageError,
    BrokerProviderUnknownError,
    BrokerReconnectError,
    BrokerSubscriptionError,
)
from ..exceptions.market_data_error import AdapterAlreadyConnectedError
from ..normalizers.broker_quote_normalizer import (
    BrokerQuoteNormalizer,
    normalize_symbol,
)
from ..universe import Universe
from ..universe import universe as default_universe
from .base import MarketDataAdapter

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# State model (§7)
# ══════════════════════════════════════════════════════════════════


class BrokerConnectionState(str, Enum):
    """Connection lifecycle of a broker adapter (§7).

    Happy path::

        DISCONNECTED → CONNECTING → CONNECTED → SUBSCRIBED → STREAMING

    Failure path::

        STREAMING → CONNECTION_LOST → RECONNECTING → CONNECTED
                  → (resubscribe) → STREAMING
    """

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    SUBSCRIBED = "SUBSCRIBED"
    STREAMING = "STREAMING"
    CONNECTION_LOST = "CONNECTION_LOST"
    RECONNECTING = "RECONNECTING"


class SubscriptionState(str, Enum):
    """Subscription health, kept **separate** from connection health (§7).

    A live socket with a lost subscription is the dangerous case:
    ``CONNECTED`` but no data.  After a reconnect the adapter is
    ``DESYNCED`` until it has re-subscribed.
    """

    UNSUBSCRIBED = "UNSUBSCRIBED"
    SUBSCRIBED = "SUBSCRIBED"
    DESYNCED = "DESYNCED"


# ══════════════════════════════════════════════════════════════════
# Provider contract (§5)
# ══════════════════════════════════════════════════════════════════


class BrokerMarketDataProvider(ABC):
    """Vendor SDK wrapper: raw connection + raw frames (§5).

    A provider is thin by design — it dials, subscribes and hands back
    *raw* payloads.  All mapping to ``MarketQuote`` happens in
    :class:`BrokerQuoteNormalizer`, so a new broker only needs a new
    provider (registered via :func:`register_provider`).

    ``poll`` blocks up to ``timeout`` seconds and returns one raw frame,
    ``None`` on timeout, and raises :class:`BrokerConnectionLostError`
    when the link drops (§10).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. ``"simulated"`` or ``"broker-x"``."""

    @abstractmethod
    def open(self, config: BrokerMarketDataConfig) -> None:
        """Dial the provider using ``config``.

        Also used for reconnects (§7) — implementations must be
        idempotent-safe and raise :class:`BrokerConnectionError` on
        failure.
        """

    @abstractmethod
    def close(self) -> None:
        """Tear the connection down.  Safe to call when not open."""

    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None:
        """Register interest in ``symbols`` at the provider."""

    @abstractmethod
    def unsubscribe(self, symbols: list[str]) -> None:
        """Drop interest in ``symbols`` at the provider."""

    @abstractmethod
    def poll(self, timeout: float) -> Optional[Mapping[str, Any]]:
        """Return the next raw frame, or ``None`` on timeout."""

    @abstractmethod
    def is_alive(self) -> bool:
        """Whether the underlying link is currently usable."""


# ── provider registry (§5) ─────────────────────────────────────────

ProviderFactory = Callable[[BrokerMarketDataConfig], BrokerMarketDataProvider]

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def register_provider(
    name: str, factory: ProviderFactory, *, replace: bool = False
) -> None:
    """Register a provider factory under ``name`` (§5).

    Real broker SDK integrations call this from their own module so the
    core never imports a vendor library.
    """
    key = (name or "").strip().lower()
    if not key:
        raise BrokerConfigError("provider name must not be empty")
    if key in _PROVIDER_FACTORIES and not replace:
        raise BrokerConfigError(
            f"provider {name!r} is already registered",
            provider=name,
        )
    _PROVIDER_FACTORIES[key] = factory


def unregister_provider(name: str) -> None:
    """Remove a provider factory (test / teardown helper)."""
    _PROVIDER_FACTORIES.pop((name or "").strip().lower(), None)


def provider_names() -> list[str]:
    """Registered provider names, sorted."""
    return sorted(_PROVIDER_FACTORIES)


def build_provider(config: BrokerMarketDataConfig) -> BrokerMarketDataProvider:
    """Instantiate the provider named by ``config.provider`` (§5).

    Raises :class:`BrokerProviderUnknownError` when nothing is
    registered under that name.
    """
    key = (config.provider or "").strip().lower()
    factory = _PROVIDER_FACTORIES.get(key)
    if factory is None:
        raise BrokerProviderUnknownError(
            f"no provider registered for {config.provider!r} "
            f"(registered: {provider_names()})",
            provider=config.provider,
        )
    return factory(config)


# ══════════════════════════════════════════════════════════════════
# Built-in simulated provider (dev / test only)
# ══════════════════════════════════════════════════════════════════

_SIM_BASE_PRICES: dict[str, Decimal] = {
    "159852": Decimal("1.050"),
    "513050": Decimal("1.620"),
    "159890": Decimal("0.950"),
    "159559": Decimal("0.820"),
    "159569": Decimal("1.280"),
    "515880": Decimal("0.690"),
    "159871": Decimal("1.150"),
    "513310": Decimal("2.350"),
    "501225": Decimal("1.480"),
    "161116": Decimal("1.050"),
    "165520": Decimal("1.320"),
}
_SIM_TICK = Decimal("0.001")


class SimulatedBrokerProvider(BrokerMarketDataProvider):
    """Dev / test provider speaking the *broker wire dialect* (§14).

    Unlike :class:`~services.market_data.adapters.mock.MockMarketDataAdapter`
    this provider emits **raw vendor-shaped payloads** — Chinese field
    names, a vendor ``行情时间``, string prices — so it exercises the
    :class:`BrokerQuoteNormalizer` and the reconnect path end-to-end
    without a real broker.

    It is **simulated data, never market data**: it is only used when
    ``MARKET_DATA_PROVIDER=simulated`` (the default outside production),
    and it logs a warning when opened.  It fabricates nothing beyond a
    seeded random walk around a fixed base price.

    Failure injection is deliberately supported so reconnect /
    resubscribe can be verified:

    * ``drop_after``       — drop the link after N delivered frames
    * ``fault_every``      — drop every N frames (long-running soak tests)
    * ``reopen_failures``  — fail the next N ``open()`` calls, so the
      reconnect-exhausted path (→ ``BrokerReconnectError``) is reachable
    * ``simulate_disconnect()`` — force a drop from outside

    ``clock`` is a test seam: it pins the emitted ``行情时间`` so the
    deterministic Quality-Gate / Paper E2E can run against a fixed
    trading session instead of wall-clock time.
    """

    def __init__(
        self,
        *,
        seed: Optional[int] = None,
        exchange_lag_ms: int = 0,
        drop_after: Optional[int] = None,
        fault_every: Optional[int] = None,
        reopen_failures: int = 0,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._exchange_lag_ms = max(0, exchange_lag_ms)
        self._drop_after = drop_after
        self._fault_every = fault_every
        self._reopen_failures = max(0, reopen_failures)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._alive = False
        self._subscribed: list[str] = []
        self._prices: dict[str, Decimal] = {}
        self._volumes: dict[str, int] = {}
        self._turnovers: dict[str, Decimal] = {}
        self._delivered = 0
        self._drop_count = 0
        self._open_calls = 0
        self._failed_opens = 0
        #: every ``subscribe`` call, in order — lets tests assert that a
        #: reconnect triggered an automatic resubscribe (§7).
        self.subscribe_calls: list[list[str]] = []

    # ── provider contract ─────────────────────────────────────

    @property
    def name(self) -> str:
        return "simulated"

    def open(self, config: BrokerMarketDataConfig) -> None:
        if self._open_calls >= 1 and self._failed_opens < self._reopen_failures:
            self._failed_opens += 1
            raise BrokerConnectionError(
                "simulated broker failed to reopen",
                provider=self.name,
                attempt=self._failed_opens,
            )
        self._alive = True
        self._open_calls += 1
        logger.warning(
            "SimulatedBrokerProvider opened (SIMULATED data, not market "
            "data) — endpoint=%s",
            config.endpoint or "-",
        )

    def close(self) -> None:
        self._alive = False

    def subscribe(self, symbols: list[str]) -> None:
        if not self._alive:
            raise BrokerConnectionLostError(
                "cannot subscribe on a closed simulated link"
            )
        for symbol in symbols:
            if symbol not in self._subscribed:
                self._subscribed.append(symbol)
            self._prices.setdefault(
                symbol, _SIM_BASE_PRICES.get(symbol, Decimal("1.000"))
            )
            self._volumes.setdefault(symbol, 0)
            self._turnovers.setdefault(symbol, Decimal("0"))
        self.subscribe_calls.append(list(symbols))

    def unsubscribe(self, symbols: list[str]) -> None:
        for symbol in symbols:
            if symbol in self._subscribed:
                self._subscribed.remove(symbol)

    def poll(self, timeout: float) -> Optional[Mapping[str, Any]]:
        if not self._alive:
            raise BrokerConnectionLostError("simulated broker link is down")
        if self._drop_after is not None and self._delivered >= self._drop_after:
            self._drop_after = None
            self.simulate_disconnect()
            raise BrokerConnectionLostError("simulated broker link dropped")
        if self._fault_every and self._delivered and (
            self._delivered % self._fault_every == 0
        ):
            self.simulate_disconnect()
            raise BrokerConnectionLostError(
                "simulated broker periodic fault"
            )
        if not self._subscribed:
            return None
        symbol = self._rng.choice(self._subscribed)
        self._delivered += 1
        return self._build_frame(symbol)

    def is_alive(self) -> bool:
        return self._alive

    # ── test support ──────────────────────────────────────────

    def simulate_disconnect(self) -> None:
        """Force the link down so the adapter runs its reconnect flow."""
        self._alive = False
        self._drop_count += 1

    @property
    def delivered(self) -> int:
        return self._delivered

    @property
    def open_calls(self) -> int:
        return self._open_calls

    @property
    def drop_count(self) -> int:
        return self._drop_count

    @property
    def subscribed(self) -> list[str]:
        return list(self._subscribed)

    # ── frame construction ────────────────────────────────────

    def _build_frame(self, symbol: str) -> dict:
        base = self._prices[symbol]
        pct = Decimal(str(self._rng.uniform(-0.002, 0.002)))
        price = (base * (1 + pct)).quantize(_SIM_TICK)
        if price < _SIM_TICK:
            price = _SIM_TICK
        self._prices[symbol] = price

        bid = price - _SIM_TICK if price > _SIM_TICK else price
        ask = price

        bid_size = self._rng.randint(10, 200) * 100
        ask_size = self._rng.randint(10, 200) * 100
        traded = self._rng.randint(100, 500) * 100
        self._volumes[symbol] += traded
        self._turnovers[symbol] += Decimal(traded) * price

        now = self._clock()
        exchange_ts = now - timedelta(milliseconds=self._exchange_lag_ms)
        instrument = default_universe.get(symbol)

        return {
            "证券代码": symbol,
            "证券名称": instrument.name if instrument else symbol,
            "最新价": str(price),
            "买一价": str(bid),
            "卖一价": str(ask),
            "买一量": bid_size,
            "卖一量": ask_size,
            "成交量": self._volumes[symbol],
            "成交额": f"{self._turnovers[symbol]:.2f}",
            "昨收": str(base),
            "开盘": str(base),
            "最高": str(max(base, price)),
            "最低": str(min(base, price)),
            "行情时间": exchange_ts,
        }


def _default_simulated_factory(
    config: BrokerMarketDataConfig,
) -> BrokerMarketDataProvider:
    return SimulatedBrokerProvider()


register_provider("simulated", _default_simulated_factory)
register_provider("mock", _default_simulated_factory)


# ══════════════════════════════════════════════════════════════════
# The adapter (§2)
# ══════════════════════════════════════════════════════════════════


class BrokerMarketDataAdapter(MarketDataAdapter):
    """Provider-backed :class:`MarketDataAdapter` (§2).

    Usage::

        adapter = BrokerMarketDataAdapter(
            SimulatedBrokerProvider(seed=7), config=cfg
        )
        adapter.connect()
        adapter.subscribe_universe()          # 11 enabled instruments (§6)
        for quote in adapter.stream():        # MarketQuote, not raw
            service.publish(quote)            # → Quality Gate → Cache

    ``stream()`` is a blocking generator; the caller drives the loop.
    """

    def __init__(
        self,
        provider: Optional[BrokerMarketDataProvider] = None,
        *,
        config: Optional[BrokerMarketDataConfig] = None,
        normalizer: Optional[BrokerQuoteNormalizer] = None,
        universe: Optional[Universe] = None,
        clock: Optional[Callable[[], datetime]] = None,
        sleep: Optional[Callable[[float], None]] = None,
        name: Optional[str] = None,
        max_quotes: Optional[int] = None,
    ) -> None:
        self._config = config or BrokerMarketDataConfig.from_env()
        self._provider = provider or build_provider(self._config)
        self._universe = universe or default_universe
        self._normalizer = normalizer or BrokerQuoteNormalizer(
            name=self._provider.name,
            volume_in_lots=self._config.volume_in_lots,
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleep = sleep or time.sleep
        self._name = name
        self._max_quotes = max_quotes

        self._state = BrokerConnectionState.DISCONNECTED
        self._subscription_state = SubscriptionState.UNSUBSCRIBED
        self._subscribed: set[str] = set()
        self._skipped: list[str] = []
        self._reconnect_count = 0
        self._last_message_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._quote_count = 0
        self._malformed_count = 0
        self._error_count = 0
        self._closed = False
        self._lock = threading.Lock()

    # ── MarketDataAdapter: identity ───────────────────────────

    @property
    def name(self) -> str:
        return self._name or self._provider.name

    @property
    def connected(self) -> bool:
        return self._state in (
            BrokerConnectionState.CONNECTED,
            BrokerConnectionState.SUBSCRIBED,
            BrokerConnectionState.STREAMING,
        )

    @property
    def provider(self) -> BrokerMarketDataProvider:
        return self._provider

    @property
    def config(self) -> BrokerMarketDataConfig:
        return self._config

    # ── lifecycle (§7) ────────────────────────────────────────

    def connect(self) -> None:
        if self._state is not BrokerConnectionState.DISCONNECTED:
            raise AdapterAlreadyConnectedError(
                f"{self.name}: already connected "
                f"(state={self._state.value})"
            )
        if not self._config.enabled:
            raise BrokerConfigError(
                "broker market data is disabled (MARKET_DATA_ENABLED=false)",
                provider=self._provider.name,
            )
        self._closed = False
        self._set_state(BrokerConnectionState.CONNECTING)
        try:
            self._provider.open(self._config)
        except BrokerMarketDataError as exc:
            self._last_error = str(exc)
            self._set_state(BrokerConnectionState.DISCONNECTED)
            raise
        except Exception as exc:  # noqa: BLE001 - vendor SDKs raise anything
            self._last_error = str(exc)
            self._set_state(BrokerConnectionState.DISCONNECTED)
            raise BrokerConnectionError(
                f"failed to open provider {self._provider.name}: {exc}",
                provider=self._provider.name,
            ) from exc
        self._set_state(BrokerConnectionState.CONNECTED)
        logger.info(
            "%s: connected via %s (%s)",
            self.name,
            self._provider.name,
            self._config.describe(),
        )

    def disconnect(self) -> None:
        if self._state is BrokerConnectionState.DISCONNECTED:
            return
        try:
            self._provider.close()
        except Exception as exc:  # noqa: BLE001 - teardown must not raise
            logger.warning("%s: error closing provider: %s", self.name, exc)
        self._subscribed.clear()
        self._subscription_state = SubscriptionState.UNSUBSCRIBED
        self._set_state(BrokerConnectionState.DISCONNECTED)
        logger.info("%s: disconnected", self.name)

    def stop(self) -> None:
        """Ask a running ``stream()`` loop to finish after the current
        frame (thread-safe)."""
        self._closed = True

    # ── subscriptions (§6) ────────────────────────────────────

    def subscribe(self, symbols: list[str]) -> None:
        self._require_connected()
        valid, unknown, disabled = self._validate_symbols(symbols)
        if unknown:
            raise BrokerSubscriptionError(
                f"unknown symbol(s) rejected: {unknown}",
                code=BrokerErrorCode.UNKNOWN_SYMBOL,
                provider=self._provider.name,
                unknown_symbols=unknown,
            )
        if disabled:
            self._skipped = list(disabled)
            logger.warning(
                "%s: skipping disabled instrument(s): %s",
                self.name,
                disabled,
            )
        if not valid:
            return
        try:
            self._provider.subscribe(valid)
        except BrokerMarketDataError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BrokerSubscriptionError(
                f"provider rejected subscription: {exc}",
                provider=self._provider.name,
                symbols=valid,
            ) from exc
        self._subscribed.update(valid)
        self._subscription_state = SubscriptionState.SUBSCRIBED
        if self._state is BrokerConnectionState.CONNECTED:
            self._set_state(BrokerConnectionState.SUBSCRIBED)
        logger.info("%s: subscribed %s", self.name, sorted(valid))

    def unsubscribe(self, symbols: list[str]) -> None:
        self._require_connected()
        targets = [normalize_symbol(s) for s in symbols]
        active = [s for s in targets if s in self._subscribed]
        if not active:
            return
        try:
            self._provider.unsubscribe(active)
        except BrokerMarketDataError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BrokerSubscriptionError(
                f"provider rejected unsubscribe: {exc}",
                provider=self._provider.name,
                symbols=active,
            ) from exc
        self._subscribed.difference_update(active)
        if not self._subscribed:
            self._subscription_state = SubscriptionState.UNSUBSCRIBED
            if self._state in (
                BrokerConnectionState.SUBSCRIBED,
                BrokerConnectionState.STREAMING,
            ):
                self._set_state(BrokerConnectionState.CONNECTED)

    def subscribe_universe(self) -> list[str]:
        """Subscribe to the Instrument Master universe (§6) — the adapter
        never keeps a second symbol list.

        Every registered code is handed to :meth:`subscribe`, which
        filters out disabled instruments and records them via
        :meth:`skipped_symbols` so Monitoring can see the omission.
        """
        self.subscribe([i.symbol for i in self._universe.all()])
        return self.subscribed_symbols()

    def _validate_symbols(
        self, symbols: list[str]
    ) -> tuple[list[str], list[str], list[str]]:
        valid: list[str] = []
        unknown: list[str] = []
        disabled: list[str] = []
        seen: set[str] = set()
        for raw in symbols:
            try:
                code = normalize_symbol(raw)
            except BrokerMessageError:
                unknown.append(str(raw))
                continue
            if code in seen:
                continue
            seen.add(code)
            instrument: Optional[Instrument] = self._universe.get(code)
            if instrument is None:
                unknown.append(code)
            elif not instrument.enabled:
                disabled.append(code)
            else:
                valid.append(code)
        return valid, unknown, disabled

    # ── streaming ─────────────────────────────────────────────

    def stream(self) -> Iterator[MarketQuote]:
        self._require_connected()
        if not self._subscribed:
            return
        self._set_state(BrokerConnectionState.STREAMING)
        while not self._closed:
            raw: Optional[Mapping[str, Any]]
            try:
                raw = self._provider.poll(self._config.timeout_seconds)
            except BrokerConnectionLostError as exc:
                self._last_error = str(exc)
                logger.warning("%s: connection lost: %s", self.name, exc)
                if not self._reconnect():
                    raise BrokerReconnectError(
                        "reconnect attempts exhausted; feed is offline",
                        provider=self._provider.name,
                        attempts=self._reconnect_count,
                        last_error=self._last_error,
                    ) from exc
                continue
            except BrokerMarketDataError as exc:
                self._error_count += 1
                self._last_error = str(exc)
                logger.warning("%s: provider error: %s", self.name, exc)
                continue
            except Exception as exc:  # noqa: BLE001 - vendor SDKs raise anything
                self._error_count += 1
                self._last_error = str(exc)
                logger.warning("%s: unexpected provider failure: %s", self.name, exc)
                continue

            if raw is None:
                continue

            try:
                quote = self._normalizer.normalize(
                    raw, received_timestamp=self._clock()
                )
            except BrokerMessageError as exc:
                # §9: a structurally broken frame is dropped, never
                # guessed at.  Bad *values* travel to the Quality Gate.
                self._malformed_count += 1
                self._last_error = str(exc)
                logger.warning("%s: dropping malformed frame: %s", self.name, exc)
                continue

            self._last_message_time = quote.effective_received_at
            self._quote_count += 1
            yield quote

            if self._max_quotes is not None and self._quote_count >= self._max_quotes:
                return

    # ── reconnect + resubscribe (§7) ──────────────────────────

    def _reconnect(self) -> bool:
        """Run the reconnect → resubscribe recovery flow (§7).

        Returns ``True`` once the stream may resume.  ``False`` means
        every attempt failed: the adapter is ``DISCONNECTED`` and
        Commit 013 reports ``MARKET_DATA_OFFLINE``.
        """
        self._set_state(BrokerConnectionState.CONNECTION_LOST)
        self._subscription_state = SubscriptionState.DESYNCED
        attempts = self._config.max_reconnect_attempts
        limit = attempts if attempts > 0 else None
        attempt = 0
        while limit is None or attempt < limit:
            attempt += 1
            self._set_state(BrokerConnectionState.RECONNECTING)
            self._sleep(max(0.0, self._config.reconnect_seconds))
            try:
                self._provider.open(self._config)
            except Exception as exc:  # noqa: BLE001
                self._last_error = str(exc)
                logger.warning(
                    "%s: reconnect attempt %s failed: %s",
                    self.name,
                    attempt,
                    exc,
                )
                continue
            self._reconnect_count += 1
            self._set_state(BrokerConnectionState.CONNECTED)
            if self._config.resubscribe_on_reconnect and self._subscribed:
                try:
                    self._provider.subscribe(sorted(self._subscribed))
                except Exception as exc:  # noqa: BLE001
                    self._last_error = str(exc)
                    logger.warning(
                        "%s: resubscribe failed after reconnect: %s",
                        self.name,
                        exc,
                    )
                    continue
                self._subscription_state = SubscriptionState.SUBSCRIBED
            self._set_state(BrokerConnectionState.STREAMING)
            logger.info(
                "%s: reconnected after %s attempt(s) (reconnect_count=%s)",
                self.name,
                attempt,
                self._reconnect_count,
            )
            return True
        logger.error("%s: reconnect attempts exhausted", self.name)
        self._last_error = "reconnect attempts exhausted"
        self._subscribed.clear()
        self._subscription_state = SubscriptionState.UNSUBSCRIBED
        self._set_state(BrokerConnectionState.DISCONNECTED)
        return False

    # ── health accessors for Commit 013 Monitoring (§10) ──────

    def is_connected(self) -> bool:
        """Whether the underlying link is currently up."""
        return self._provider.is_alive() and self.connected

    def last_message_time(self) -> Optional[datetime]:
        """Receive time of the most recent successful frame — the
        staleness source for ``quote_age_ms`` (Commit 013)."""
        return self._last_message_time

    def last_message_age_seconds(self) -> Optional[float]:
        """Seconds since the last frame, or ``None`` if none seen."""
        if self._last_message_time is None:
            return None
        delta = self._clock() - self._last_message_time
        return max(0.0, delta.total_seconds())

    def connection_state(self) -> BrokerConnectionState:
        """Current point in the §7 connection lifecycle."""
        return self._state

    def reconnect_count(self) -> int:
        """Successful reconnects since construction."""
        return self._reconnect_count

    def subscription_state(self) -> SubscriptionState:
        """Subscription health — ``DESYNCED`` after a drop, until
        resubscribe completes (§7)."""
        return self._subscription_state

    def subscribed_symbols(self) -> list[str]:
        """Currently subscribed codes, sorted."""
        return sorted(self._subscribed)

    def skipped_symbols(self) -> list[str]:
        """Instruments excluded because they are disabled (§6)."""
        return list(self._skipped)

    def stats(self) -> dict:
        """Counters for API / Dashboard."""
        return {
            "quotes": self._quote_count,
            "malformed": self._malformed_count,
            "errors": self._error_count,
            "reconnects": self._reconnect_count,
            "provider_opens": getattr(self._provider, "open_calls", None),
        }

    def health(self) -> dict:
        """The three health dimensions monitoring must keep apart (§7)."""
        age = self.last_message_age_seconds()
        last = self._last_message_time
        with self._lock:
            return {
                "adapter": self.name,
                "provider": self._provider.name,
                "connection": {
                    "state": self._state.value,
                    "connected": self.connected,
                    "alive": self._provider.is_alive(),
                    "reconnect_count": self._reconnect_count,
                    "last_error": self._last_error,
                },
                "subscription": {
                    "state": self._subscription_state.value,
                    "count": len(self._subscribed),
                    "symbols": sorted(self._subscribed),
                    "skipped": list(self._skipped),
                },
                "market_data": {
                    "last_message_time": last.isoformat() if last else None,
                    "last_message_age_seconds": age,
                    "quote_count": self._quote_count,
                    "malformed_count": self._malformed_count,
                },
            }

    def as_dict(self) -> dict:
        """Serializable snapshot (secrets redacted) for API / Dashboard."""
        payload = self.health()
        payload["config"] = self._config.as_dict()
        return payload

    # ── internals ─────────────────────────────────────────────

    def _set_state(self, state: BrokerConnectionState) -> None:
        with self._lock:
            if state is not self._state:
                logger.debug(
                    "%s: %s → %s", self.name, self._state.value, state.value
                )
            self._state = state

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<BrokerMarketDataAdapter provider={self._provider.name} "
            f"state={self._state.value} "
            f"subscription={self._subscription_state.value} "
            f"symbols={len(self._subscribed)}>"
        )


__all__ = [
    "BrokerMarketDataAdapter",
    "BrokerMarketDataProvider",
    "BrokerConnectionState",
    "SubscriptionState",
    "SimulatedBrokerProvider",
    "register_provider",
    "unregister_provider",
    "provider_names",
    "build_provider",
]
