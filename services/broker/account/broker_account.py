"""Commit 015 §5 — provider-backed account adapter + provider registry.

Same shape as Commit 014's ``BrokerMarketDataAdapter`` so the two halves
of a broker integration feel identical, but this one is account-only::

    AccountProvider (vendor SDK, raw mappings)
            │
            ▼
    ProviderBrokerAccountAdapter   (lifecycle + state + errors)
            │  raw dict
            ▼
    AccountNormalizer              (→ AccountBalance / Position)

A new broker registers an :class:`AccountProvider` factory; the core
never imports a vendor library (§5).
"""
from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from services.account.sync.config import (
    DEFAULT_ACCOUNT_PROVIDER,
    AccountSyncConfig,
)
from services.account.sync.exceptions import (
    AccountProviderUnknownError,
    BrokerAccountConnectionError,
    BrokerAccountError,
    BrokerAccountNotConnectedError,
)
from services.market_data.adapters.broker import BrokerConnectionState

from .base import BrokerAccountAdapter

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Provider contract (§5)
# ══════════════════════════════════════════════════════════════════


class AccountProvider(ABC):
    """Vendor SDK wrapper: raw account / position channel (§5).

    A provider is thin by design — it dials and hands back *raw*
    payloads.  All mapping happens in the normalizer.
    """

    name: str = "unknown"

    def __init__(self, config: Optional[AccountSyncConfig] = None) -> None:
        self._config = config or AccountSyncConfig.from_env()

    @property
    def config(self) -> AccountSyncConfig:
        return self._config

    @abstractmethod
    def connect(self) -> None:
        """Open the vendor channel."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the vendor channel."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the vendor channel is open."""

    @abstractmethod
    def get_account(self, account_id: str) -> Mapping[str, Any]:
        """Raw balance payload (§2)."""

    @abstractmethod
    def get_positions(self, account_id: str) -> list[Mapping[str, Any]]:
        """Raw position payloads (§3)."""


ProviderFactory = Callable[[AccountSyncConfig], AccountProvider]

_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def register_provider(
    name: str, factory: ProviderFactory, *, replace: bool = False
) -> None:
    """Register a provider factory under ``name`` (§5)."""
    key = (name or "").strip().lower()
    if not key:
        raise AccountProviderUnknownError("provider name must not be empty")
    if key in _PROVIDER_FACTORIES and not replace:
        raise AccountProviderUnknownError(
            f"account provider {name!r} is already registered", provider=name
        )
    _PROVIDER_FACTORIES[key] = factory


def unregister_provider(name: str) -> None:
    """Remove a provider factory (test / teardown helper)."""
    _PROVIDER_FACTORIES.pop((name or "").strip().lower(), None)


def provider_names() -> list[str]:
    """Registered provider names, sorted."""
    return sorted(_PROVIDER_FACTORIES)


def build_account_provider(config: AccountSyncConfig) -> AccountProvider:
    """Instantiate the provider named by ``config.provider`` (§5)."""
    key = (config.provider or "").strip().lower()
    factory = _PROVIDER_FACTORIES.get(key)
    if factory is None:
        raise AccountProviderUnknownError(
            f"no account provider registered for {config.provider!r} "
            f"(registered: {provider_names()})",
            provider=config.provider,
        )
    return factory(config)


# ══════════════════════════════════════════════════════════════════
# Adapter over a provider (§5)
# ══════════════════════════════════════════════════════════════════


class ProviderBrokerAccountAdapter(BrokerAccountAdapter):
    """``BrokerAccountAdapter`` driven by a pluggable provider (§5).

    Owns the connection lifecycle and translates provider exceptions
    into the account error hierarchy; it never inspects the payload.
    """

    def __init__(
        self,
        provider: AccountProvider,
        config: Optional[AccountSyncConfig] = None,
    ) -> None:
        super().__init__(config or provider.config)
        self._provider = provider
        self.provider_name = getattr(provider, "name", "unknown")

    @property
    def provider(self) -> AccountProvider:
        return self._provider

    def connect(self) -> None:
        self._set_state(BrokerConnectionState.CONNECTING)
        try:
            self._provider.connect()
        except BrokerAccountError as exc:
            self._record_error(exc)
            self._set_state(BrokerConnectionState.CONNECTION_LOST)
            raise
        except Exception as exc:  # pragma: no cover - vendor-specific
            self._record_error(exc)
            self._set_state(BrokerConnectionState.CONNECTION_LOST)
            raise BrokerAccountConnectionError(
                f"failed to open account channel: {exc}",
                provider=self.provider_name,
            ) from exc
        self._set_state(BrokerConnectionState.CONNECTED)

    def disconnect(self) -> None:
        try:
            self._provider.disconnect()
        except Exception as exc:  # pragma: no cover - vendor-specific
            logger.warning("account provider disconnect failed: %s", exc)
        finally:
            self._set_state(BrokerConnectionState.DISCONNECTED)

    def is_connected(self) -> bool:
        return bool(self._provider.is_connected()) and super().is_connected()

    def _guard(self, call: str, fn: Callable[[], Any]) -> Any:
        self._ensure_connected()
        if not self._provider.is_connected():
            self._set_state(BrokerConnectionState.CONNECTION_LOST)
            raise BrokerAccountNotConnectedError(
                f"account provider {self.provider_name!r} link is down",
                provider=self.provider_name,
            )
        try:
            return fn()
        except BrokerAccountError:
            raise
        except Exception as exc:
            self._record_error(exc)
            raise BrokerAccountError(
                f"{call} failed: {exc}", provider=self.provider_name
            ) from exc

    def get_account(self, account_id: str) -> Mapping[str, Any]:
        return self._guard(
            "get_account", lambda: self._provider.get_account(account_id)
        )

    def get_positions(self, account_id: str) -> list[Mapping[str, Any]]:
        return self._guard(
            "get_positions", lambda: self._provider.get_positions(account_id)
        )

    def health(self) -> dict:
        payload = super().health()
        payload["provider_connected"] = bool(self._provider.is_connected())
        return payload


# ══════════════════════════════════════════════════════════════════
# Built-in simulated provider (dev / test only)
# ══════════════════════════════════════════════════════════════════


def _demo_account_payload(stamp: str) -> dict[str, Any]:
    """A default demo balance in the *broker wire dialect* (§14 style)."""
    return {
        "币种": "CNY",
        "资金余额": "83500.00",
        "可用资金": "82000.00",
        "冻结资金": "1500.00",
        "证券市值": "128000.00",
        "总资产": "211500.00",
        "可买金额": "82000.00",
        "更新时间": stamp,
    }


def _demo_position_payloads(stamp: str) -> list[dict[str, Any]]:
    """Default demo positions in the *broker wire dialect*."""
    return [
        {
            "证券代码": "159852",
            "市场": "SZ",
            "持仓数量": "10000",
            "可用数量": "10000",
            "冻结数量": "0",
            "成本价": "1.250",
            "现价": "1.280",
            "市值": "12800.00",
            "更新时间": stamp,
        },
        {
            "证券代码": "159559",
            "市场": "SZ",
            "持仓数量": "20000",
            "可用数量": "0",
            "冻结数量": "20000",
            "成本价": "0.800",
            "现价": "0.820",
            "市值": "16400.00",
            "更新时间": stamp,
        },
        {
            "证券代码": "513050",
            "市场": "SH",
            "持仓数量": "5000",
            "可用数量": "5000",
            "冻结数量": "0",
            "成本价": "1.600",
            "现价": "1.620",
            "市值": "8100.00",
            "更新时间": stamp,
        },
    ]


class SimulatedAccountProvider(AccountProvider):
    """Dev / test provider speaking the *broker wire dialect* (§14).

    Emits raw vendor-shaped payloads — Chinese field names, string
    numbers, a vendor ``更新时间`` — so the normalizer, valuation and
    reconciliation run end-to-end without a real broker.

    It is **simulated account data, never a real account**: only used
    when ``ACCOUNT_PROVIDER=simulated`` (the default outside
    production).  Failure injection keeps the reconnect path testable:

    * ``fail_connect_times`` — raise on the first N ``connect()`` calls
    * ``drop_after``         — the link goes down after N ``get_*`` calls
    """

    name = DEFAULT_ACCOUNT_PROVIDER

    def __init__(
        self,
        config: Optional[AccountSyncConfig] = None,
        *,
        accounts: Optional[Mapping[str, Mapping[str, Any]]] = None,
        positions: Optional[Mapping[str, list[Mapping[str, Any]]]] = None,
        clock: Optional[Callable[[], datetime]] = None,
        fail_connect_times: int = 0,
        drop_after: Optional[int] = None,
    ) -> None:
        super().__init__(config)
        self._clock = clock
        self._accounts = {k: copy.deepcopy(v) for k, v in (accounts or {}).items()}
        self._positions = {
            k: [copy.deepcopy(p) for p in v] for k, v in (positions or {}).items()
        }
        self._connected = False
        self._fail_connect_times = fail_connect_times
        self._drop_after = drop_after
        self._call_count = 0
        self._serving = True

    # ── helpers ───────────────────────────────────────────────────────

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock()
        from services.account.domain.enums import now_cst

        return now_cst()

    def _stamp(self) -> str:
        return self._now().strftime("%Y-%m-%d %H:%M:%S")

    def _maybe_drop(self) -> None:
        self._call_count += 1
        if self._drop_after is not None and self._call_count > self._drop_after:
            self._serving = False

    def _payload(self, account_id: str) -> Mapping[str, Any]:
        stamp = self._stamp()
        if account_id in self._accounts:
            payload = copy.deepcopy(self._accounts[account_id])
            payload.setdefault("更新时间", stamp)
            return payload
        return _demo_account_payload(stamp)

    def _position_payloads(self, account_id: str) -> list[Mapping[str, Any]]:
        stamp = self._stamp()
        if account_id in self._positions:
            rows = copy.deepcopy(self._positions[account_id])
        else:
            rows = _demo_position_payloads(stamp)
        for row in rows:
            row.setdefault("更新时间", stamp)
        return rows

    # ── injected data ─────────────────────────────────────────────────

    def set_account(self, account_id: str, payload: Mapping[str, Any]) -> None:
        self._accounts[account_id] = copy.deepcopy(dict(payload))

    def set_positions(
        self, account_id: str, payloads: list[Mapping[str, Any]]
    ) -> None:
        self._positions[account_id] = [copy.deepcopy(p) for p in payloads]

    # ── AccountProvider ───────────────────────────────────────────────

    def connect(self) -> None:
        if self._fail_connect_times > 0:
            self._fail_connect_times -= 1
            raise BrokerAccountConnectionError(
                "simulated account provider refused the connection",
                provider=self.name,
            )
        self._connected = True
        self._serving = True
        self._call_count = 0
        logger.warning(
            "SimulatedAccountProvider connected — SIMULATED account data, "
            "not a real broker"
        )

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._serving

    def get_account(self, account_id: str) -> Mapping[str, Any]:
        if not self.is_connected():
            raise BrokerAccountNotConnectedError(
                "simulated account provider is not connected", provider=self.name
            )
        self._maybe_drop()
        return self._payload(account_id)

    def get_positions(self, account_id: str) -> list[Mapping[str, Any]]:
        if not self.is_connected():
            raise BrokerAccountNotConnectedError(
                "simulated account provider is not connected", provider=self.name
            )
        self._maybe_drop()
        return self._position_payloads(account_id)


def _simulated_factory(config: AccountSyncConfig) -> AccountProvider:
    return SimulatedAccountProvider(config)


#: Register the built-in simulated provider so ``ACCOUNT_PROVIDER=simulated``
#: (the default) works out of the box.
register_provider(DEFAULT_ACCOUNT_PROVIDER, _simulated_factory, replace=True)


__all__ = [
    "AccountProvider",
    "ProviderFactory",
    "ProviderBrokerAccountAdapter",
    "SimulatedAccountProvider",
    "register_provider",
    "unregister_provider",
    "provider_names",
    "build_account_provider",
]
