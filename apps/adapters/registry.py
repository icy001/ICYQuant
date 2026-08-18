"""Adapter registry - brokers and accounts known to the system.

One broker owns one or more accounts; every account is served by exactly
one adapter. The registry also tracks connection status so the Dashboard
can show broker health.
"""

from __future__ import annotations

from typing import Dict, List

from apps.adapters.domain import Account, Broker
from apps.adapters.interface import AccountAdapter, AdapterError


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: Dict[str, AccountAdapter] = {}
        self._brokers: Dict[str, Broker] = {}
        self._accounts: Dict[str, Account] = {}

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------

    def register_adapter(self, adapter: AccountAdapter) -> Broker:
        """Register an adapter together with its broker and accounts."""
        broker = Broker(
            broker_id=adapter.broker_id,
            broker_name=adapter.broker_name,
            market=adapter.market,
            adapter_type=adapter.adapter_type,
            capabilities=set(adapter.capabilities),
            account_ids=list(adapter.account_ids),
        )
        self._adapters[adapter.broker_id] = adapter
        self._brokers[adapter.broker_id] = broker
        for account_id in adapter.account_ids:
            account = adapter.get_account(account_id)
            account.broker_name = adapter.broker_name
            self._accounts[account_id] = account
        return broker

    # ------------------------------------------------------------------
    # connection
    # ------------------------------------------------------------------

    def connect(self, broker_id: str) -> str:
        adapter = self.adapter_for(broker_id)
        status = adapter.connect()
        self._brokers[broker_id].connection_status = status
        return status

    def connect_all(self) -> None:
        for broker_id in list(self._brokers):
            self.connect(broker_id)

    def disconnect(self, broker_id: str) -> None:
        self.adapter_for(broker_id).disconnect()
        self._brokers[broker_id].connection_status = "DISCONNECTED"

    # ------------------------------------------------------------------
    # lookups
    # ------------------------------------------------------------------

    def adapter_for(self, broker_id: str) -> AccountAdapter:
        try:
            return self._adapters[broker_id]
        except KeyError:
            raise AdapterError(f"Unknown broker: {broker_id}") from None

    def get_account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError:
            raise AdapterError(f"Unknown account: {account_id}") from None

    def get_broker(self, broker_id: str) -> Broker:
        try:
            return self._brokers[broker_id]
        except KeyError:
            raise AdapterError(f"Unknown broker: {broker_id}") from None

    def accounts(self) -> List[Account]:
        return list(self._accounts.values())

    def brokers(self) -> List[Broker]:
        return list(self._brokers.values())
