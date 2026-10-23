"""Broker-facing adapters, one per concern (§5, Commit 015).

Broker concerns are kept strictly apart so that neither leaks into the
other — the rule §5 spells out explicitly:

    ==========================  ==========================================
    ``services.market_data``    market data pipeline (Commit 014)
    ``services.broker.account`` account + position adapter (Commit 015)
    ==========================  ==========================================

A broker therefore exposes up to two adapters — ``MarketDataAdapter`` and
``BrokerAccountAdapter`` — but an Account API is never stuffed into
``BrokerMarketDataAdapter`` and market data never enters the account
adapter (§18).
"""
from __future__ import annotations

from .account import (
    AccountProvider,
    BrokerAccountAdapter,
    ProviderBrokerAccountAdapter,
    SimulatedAccountProvider,
    build_account_provider,
    provider_names,
    register_provider,
    unregister_provider,
)

__all__ = [
    "AccountProvider",
    "BrokerAccountAdapter",
    "ProviderBrokerAccountAdapter",
    "SimulatedAccountProvider",
    "build_account_provider",
    "provider_names",
    "register_provider",
    "unregister_provider",
]
