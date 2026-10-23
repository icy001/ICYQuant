"""Commit 015 §5 — the ``BrokerAccountAdapter`` contract.

The account sibling of Commit 014's ``MarketDataAdapter``::

    BrokerAccountAdapter
        ├── connect() / disconnect()      lifecycle
        ├── get_account(account_id)       → raw balance payload
        └── get_positions(account_id)     → [raw position payload]

It reuses Commit 014's connection vocabulary
(:class:`~services.market_data.adapters.broker.BrokerConnectionState`) so
Monitoring sees one state language across market data and accounts, and
it returns **raw mappings** — reading them into ``AccountBalance`` /
``Position`` is the Normalizer's job (§1).  The adapter never does
business judgement and never touches Market Data (§18) or Redis.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from services.market_data.adapters.broker import BrokerConnectionState

from services.account.sync.config import AccountSyncConfig
from services.account.sync.exceptions import (
    BrokerAccountNotConnectedError,
)


class BrokerAccountAdapter(ABC):
    """Read-only broker account / position adapter (§5)."""

    #: Vendor key this adapter is registered under.
    provider_name: str = "unknown"

    def __init__(self, config: Optional[AccountSyncConfig] = None) -> None:
        self._config = config or AccountSyncConfig.from_env()
        self._state: BrokerConnectionState = BrokerConnectionState.DISCONNECTED
        self._last_error: Optional[str] = None

    # ── lifecycle ─────────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Open the account channel."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the account channel."""

    @abstractmethod
    def get_account(self, account_id: str) -> Mapping[str, Any]:
        """Return the raw balance payload for ``account_id`` (§2)."""

    @abstractmethod
    def get_positions(self, account_id: str) -> list[Mapping[str, Any]]:
        """Return the raw position payloads for ``account_id`` (§3)."""

    # ── state ─────────────────────────────────────────────────────────

    @property
    def config(self) -> AccountSyncConfig:
        return self._config

    def connection_state(self) -> str:
        """Commit 014 state vocabulary, as a plain string."""
        return self._state.value

    def is_connected(self) -> bool:
        return self._state == BrokerConnectionState.CONNECTED

    def last_error(self) -> Optional[str]:
        return self._last_error

    def _set_state(self, state: BrokerConnectionState) -> None:
        self._state = state

    def _record_error(self, error: Any) -> None:
        self._last_error = str(error)

    def _ensure_connected(self) -> None:
        if not self.is_connected():
            raise BrokerAccountNotConnectedError(
                f"account adapter for provider {self.provider_name!r} "
                f"is not connected (state={self.connection_state()})",
                provider=self.provider_name,
                state=self.connection_state(),
            )

    # ── reporting (Commit 013 Monitoring) ─────────────────────────────

    def health(self) -> dict:
        """Connection-health slice for Monitoring (§14)."""
        return {
            "provider": self.provider_name,
            "connection_state": self.connection_state(),
            "connected": self.is_connected(),
            "last_error": self._last_error,
        }

    def as_dict(self) -> dict:
        payload = self.health()
        payload["config"] = self._config.as_dict()
        return payload


__all__ = ["BrokerAccountAdapter"]
