"""ICYQuant Multi-Account Adapter Layer.

One unified contract (AccountAdapter), four market adapters (A-Share /
Futures / US Equity / FX), a routing layer and a sync / reconciliation
engine. Brokers never leak into Strategy, Risk or the Order Domain.
"""

from apps.adapters.adapters import AshareAdapter, FxAdapter, FuturesAdapter, UsEquityAdapter
from apps.adapters.domain import (
    Account,
    AccountBalance,
    Broker,
    Capability,
    ExecutionRecord,
    Market,
    OrderIntent,
    OrderRecord,
    Position,
)
from apps.adapters.interface import AccountAdapter, AdapterError
from apps.adapters.registry import AdapterRegistry
from apps.adapters.routing import OrderRouter, RoutingError
from apps.adapters.service import MultiAccountService, service
from apps.adapters.sync import SyncEngine

__all__ = [
    "Account",
    "AccountAdapter",
    "AccountBalance",
    "AdapterError",
    "AdapterRegistry",
    "AshareAdapter",
    "Broker",
    "Capability",
    "ExecutionRecord",
    "FxAdapter",
    "FuturesAdapter",
    "Market",
    "MultiAccountService",
    "OrderIntent",
    "OrderRecord",
    "OrderRouter",
    "Position",
    "RoutingError",
    "SyncEngine",
    "UsEquityAdapter",
    "service",
]
