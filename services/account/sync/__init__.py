"""Commit 015 — Account / Position Sync pipeline.

    config          AccountSyncConfig (env-driven, secrets redacted)
    repository      AccountSnapshotRepository (+ in-memory)
    sql_repository  PostgreSQL implementation (Commit 011 DB stack)
    orm             §8 tables
    ledger          Position Ledger read port (§9)
    valuation       §18 — the single quantity × price meeting point
    reconciliation  §10 / §11 broker vs ledger
    state           §12 account status machine
    monitoring      §14 account / position sync health
    service         AccountSyncService — the orchestrator + default singleton
"""
from __future__ import annotations

from .config import DEFAULT_ACCOUNT_PROVIDER, AccountSyncConfig
from .exceptions import (
    AccountNormalizationError,
    AccountNotFoundError,
    AccountProviderUnknownError,
    AccountSnapshotNotFoundError,
    AccountStateError,
    AccountSyncError,
    BrokerAccountConnectionError,
    BrokerAccountError,
    BrokerAccountNotConnectedError,
    InvalidAccountTransition,
    UnknownAccountSymbolError,
)
from .ledger import (
    InMemoryPositionLedgerReader,
    LedgerBalance,
    LedgerPosition,
    PositionLedgerReader,
    ProjectionPositionLedgerReader,
)
from .monitoring import (
    AccountSyncHealthSnapshot,
    AccountSyncMonitor,
    health_for_status,
    is_blocking,
)
from .reconciliation import (
    AccountReconciler,
    ReconciliationItem,
    ReconciliationReport,
)
from .repository import (
    AccountSnapshotRepository,
    InMemoryAccountSnapshotRepository,
)
from .service import (
    AccountSyncService,
    account_service,
    build_default_account_service,
    demo_ledger,
)
from .state import AccountStateMachine
from .valuation import (
    MappingPriceProvider,
    MarketDataPriceProvider,
    PositionValuator,
    PriceProvider,
    StaticPriceProvider,
)

__all__ = [
    "AccountSyncConfig",
    "DEFAULT_ACCOUNT_PROVIDER",
    "AccountSyncError",
    "AccountNotFoundError",
    "AccountSnapshotNotFoundError",
    "AccountNormalizationError",
    "AccountProviderUnknownError",
    "AccountStateError",
    "BrokerAccountError",
    "BrokerAccountConnectionError",
    "BrokerAccountNotConnectedError",
    "InvalidAccountTransition",
    "UnknownAccountSymbolError",
    "AccountSnapshotRepository",
    "InMemoryAccountSnapshotRepository",
    "LedgerPosition",
    "LedgerBalance",
    "PositionLedgerReader",
    "InMemoryPositionLedgerReader",
    "ProjectionPositionLedgerReader",
    "AccountReconciler",
    "ReconciliationItem",
    "ReconciliationReport",
    "AccountStateMachine",
    "AccountSyncMonitor",
    "AccountSyncHealthSnapshot",
    "health_for_status",
    "is_blocking",
    "PriceProvider",
    "MappingPriceProvider",
    "StaticPriceProvider",
    "MarketDataPriceProvider",
    "PositionValuator",
    "AccountSyncService",
    "account_service",
    "build_default_account_service",
    "demo_ledger",
]
