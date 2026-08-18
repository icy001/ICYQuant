"""Account Adapter interface - the unified contract every broker adapter
(A-Share, CTP / Futures, US Equity, FX) must satisfy.

Strategies / Risk / Order Domain never see broker specifics; all broker
differences are encapsulated behind this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from apps.adapters.domain import (
    Account,
    AccountBalance,
    ExecutionRecord,
    OrderIntent,
    OrderRecord,
    Position,
)


class AccountAdapter(ABC):
    """Contract every market adapter must implement.

    A market may implement a subset of capabilities (e.g. A-Share does not
    expose margin), but the methods themselves are part of the unified
    contract so the Dashboard and routing layer can treat all accounts
    uniformly.
    """

    # --- static broker identity (set by subclasses) -----------------------
    broker_id: str = ""
    broker_name: str = ""
    adapter_type: str = ""
    market: str = ""
    account_ids: list = []
    capabilities: set = set()

    # --- connection lifecycle ---------------------------------------------
    @abstractmethod
    def connect(self) -> str:
        """Establish the connection and return the ConnectionStatus."""

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down the connection."""

    @abstractmethod
    def health(self) -> dict:
        """Return a health snapshot {status, broker_id, market, latency_ms}."""

    # --- read side ----------------------------------------------------------
    @abstractmethod
    def get_account(self, account_id: str) -> Account:
        """Return the unified account model."""

    @abstractmethod
    def get_balance(self, account_id: str) -> AccountBalance:
        """Return the current balance snapshot."""

    @abstractmethod
    def get_positions(self, account_id: str) -> list:
        """Return live positions."""

    @abstractmethod
    def get_orders(self, account_id: str) -> list:
        """Return orders on the account."""

    @abstractmethod
    def get_executions(self, account_id: str) -> list:
        """Return executions (fills) on the account."""

    # --- trade side ----------------------------------------------------------
    @abstractmethod
    def submit_order(self, intent: OrderIntent) -> OrderRecord:
        """Submit an order to the broker and return the broker order."""

    @abstractmethod
    def cancel_order(self, account_id: str, order_id: str) -> OrderRecord:
        """Cancel a cancellable order."""

    @abstractmethod
    def query_order(self, account_id: str, order_id: str) -> OrderRecord:
        """Query the current state of an order."""

    # --- sync side -----------------------------------------------------------
    @abstractmethod
    def sync_account(self, account_id: str) -> Account:
        """Pull the latest account snapshot and refresh the cached Account."""

    @abstractmethod
    def sync_positions(self, account_id: str) -> list:
        """Pull positions and refresh the cache."""

    @abstractmethod
    def sync_orders(self, account_id: str) -> list:
        """Pull orders and refresh the cache."""

    @abstractmethod
    def sync_executions(self, account_id: str) -> list:
        """Pull executions and refresh the cache."""


class AdapterError(RuntimeError):
    """Raised when an adapter operation fails (not connected, unknown
    account, capability missing, order not cancellable, ...)."""
