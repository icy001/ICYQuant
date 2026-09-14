"""Broker market data error types (Commit 014 §9 / §10).

The broker adapter sits between an untrusted vendor SDK and the rest of
ICYQuant.  Everything that can go wrong at that boundary gets a typed
exception, so a caller can decide whether to skip a single message,
retry the whole subscription, or reconnect the socket — instead of
guessing from a generic ``Exception``.

Design rule (§9): a *bad value* is **not** an adapter error.  If the
broker sends ``last = -1`` the adapter parses it faithfully into
``MarketQuote(last=-1)`` and lets the Commit 006 Quality Gate reject it
(``INVALID_PRICE`` → ``INVALID`` → ``QUARANTINED``).  An adapter error is
a *structural* problem — the payload could not be mapped to the standard
model at all — and is surfaced as :class:`BrokerMessageError`.

Hierarchy::

    MarketDataError                    (Commit 001)
      └── BrokerMarketDataError        (Commit 014 base)
            ├── BrokerConfigError      provider misconfigured / unknown
            ├── BrokerConnectionError  the link to the provider
            │     ├── BrokerConnectionLostError   mid-stream drop
            │     └── BrokerReconnectError        reconnect exhausted
            ├── BrokerSubscriptionError subscribe rejected / unknown symbol
            ├── BrokerMessageError      payload could not be mapped
            └── BrokerProtocolError     provider violated its contract
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from .market_data_error import MarketDataError


class BrokerErrorCode(str, Enum):
    """Machine-readable broker error reasons."""

    CONFIG_INVALID = "BROKER_CONFIG_INVALID"
    PROVIDER_UNKNOWN = "BROKER_PROVIDER_UNKNOWN"
    CONNECT_FAILED = "BROKER_CONNECT_FAILED"
    CONNECTION_LOST = "BROKER_CONNECTION_LOST"
    RECONNECT_EXHAUSTED = "BROKER_RECONNECT_EXHAUSTED"
    SUBSCRIBE_FAILED = "BROKER_SUBSCRIBE_FAILED"
    UNKNOWN_SYMBOL = "BROKER_UNKNOWN_SYMBOL"
    DISABLED_SYMBOL = "BROKER_DISABLED_SYMBOL"
    MALFORMED_MESSAGE = "BROKER_MALFORMED_MESSAGE"
    MISSING_SYMBOL = "BROKER_MISSING_SYMBOL"
    MISSING_PRICE = "BROKER_MISSING_PRICE"
    INVALID_TIMESTAMP = "BROKER_INVALID_TIMESTAMP"
    INVALID_FIELD = "BROKER_INVALID_FIELD"
    NOT_CONNECTED = "BROKER_NOT_CONNECTED"


class BrokerMarketDataError(MarketDataError):
    """Base class for every broker adapter failure (§14).

    Carries the :class:`BrokerErrorCode` plus whatever context helps an
    operator diagnose the incident, without leaking secrets.
    """

    code: str = "BROKER_MARKET_DATA_ERROR"

    def __init__(
        self,
        detail: str = "",
        *,
        code: Any = None,
        symbol: Optional[str] = None,
        provider: Optional[str] = None,
        **context: Any,
    ) -> None:
        resolved = code.value if isinstance(code, BrokerErrorCode) else code
        self.code = resolved or type(self).code
        self.detail = detail or self.code
        self.symbol = symbol
        self.provider = provider
        self.context = {k: v for k, v in context.items() if v is not None}
        super().__init__(f"{self.code}: {self.detail}")

    def as_dict(self) -> dict:
        """Serializable view (error code + context, never a secret)."""
        payload: dict = {"error": self.code, "detail": self.detail}
        if self.symbol is not None:
            payload["symbol"] = self.symbol
        if self.provider is not None:
            payload["provider"] = self.provider
        payload.update(self.context)
        return payload


class BrokerConfigError(BrokerMarketDataError):
    """The broker configuration is missing, invalid, or names an
    unregistered provider (§4)."""

    code = BrokerErrorCode.CONFIG_INVALID.value


class BrokerProviderUnknownError(BrokerConfigError):
    """No provider factory is registered for ``config.provider`` (§5)."""

    code = BrokerErrorCode.PROVIDER_UNKNOWN.value


class BrokerConnectionError(BrokerMarketDataError):
    """The connection to the provider could not be established or broke."""

    code = BrokerErrorCode.CONNECT_FAILED.value


class BrokerConnectionLostError(BrokerConnectionError):
    """The stream died mid-flight (socket closed, heartbeat missing).

    Raised by a provider's ``poll``/``receive`` so the adapter can run
    the §7 reconnect + resubscribe flow.
    """

    code = BrokerErrorCode.CONNECTION_LOST.value


class BrokerReconnectError(BrokerConnectionError):
    """Reconnect attempts were exhausted — the feed stays offline until
    an operator intervenes (§10 Monitoring raises MARKET_DATA_OFFLINE)."""

    code = BrokerErrorCode.RECONNECT_EXHAUSTED.value


class BrokerSubscriptionError(BrokerMarketDataError):
    """A subscription was rejected (unknown / disabled symbol, provider
    refusal)."""

    code = BrokerErrorCode.SUBSCRIBE_FAILED.value


class BrokerMessageError(BrokerMarketDataError):
    """A raw provider payload could not be mapped to ``MarketQuote`` (§9).

    This is a *structural* failure — missing symbol, missing price,
    unparseable timestamp, malformed envelope — not a bad value.  A
    syntactically valid but semantically wrong quote (``last = -1``)
    is mapped faithfully and handed to the Quality Gate instead.
    """

    code = BrokerErrorCode.MALFORMED_MESSAGE.value


class BrokerProtocolError(BrokerMarketDataError):
    """The provider violated the ``BrokerMarketDataProvider`` contract
    (e.g. yielded a non-mapping frame)."""

    code = BrokerErrorCode.MALFORMED_MESSAGE.value


__all__ = [
    "BrokerErrorCode",
    "BrokerMarketDataError",
    "BrokerConfigError",
    "BrokerProviderUnknownError",
    "BrokerConnectionError",
    "BrokerConnectionLostError",
    "BrokerReconnectError",
    "BrokerSubscriptionError",
    "BrokerMessageError",
    "BrokerProtocolError",
]
