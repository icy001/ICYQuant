"""Account / Position API schemas (Commit 015 §15).

The API's job (§15) is to expose what the **snapshot store** holds — never
to ask the broker.  Two consequences are visible in these models:

* every payload carries the §12 ``status`` and the §10 ``reconciliation``
  verdict alongside the numbers, so a reader can never mistake a
  ``MISMATCH`` account for a trustworthy one;
* an unpriceable field stays ``null`` (§18) — the API does not invent a
  price to fill a column.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

AccountStatusName = Literal[
    "CONNECTED", "SYNCING", "SYNCED", "STALE", "ERROR", "MISMATCH", "OFFLINE"
]
PositionStatusName = Literal["VALID", "INVALID"]
ReconciliationStatusName = Literal[
    "RECONCILED", "MISMATCH", "MISSING_BROKER", "MISSING_LEDGER", "INVALID"
]
ReconciliationOutcomeName = Literal["PASS", "FAIL"]
SyncHealthName = Literal["HEALTHY", "DEGRADED", "BLOCKED", "OFFLINE"]


# ── errors ────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Error envelope shared by every ``/api/accounts`` route (§15)."""

    error: str = Field(description="Machine-readable error code")
    detail: str = Field(description="Human-readable explanation")
    account_id: Optional[str] = Field(default=None, description="Account in play")
    symbol: Optional[str] = Field(default=None, description="Symbol in play")
    provider: Optional[str] = Field(default=None, description="Broker provider")
    state: Optional[str] = Field(default=None, description="Account state at failure")


# ── account ───────────────────────────────────────────────────────


class AccountSchema(BaseModel):
    """One registered broker account (§2)."""

    account_id: str
    name: str = ""
    broker: str = ""
    currency: str = "CNY"
    status: AccountStatusName


class AccountListResponse(BaseModel):
    """``GET /api/accounts``."""

    accounts: list[AccountSchema]
    count: int
    provider: str = Field(description="Broker account provider name")
    connection_state: str = Field(description="§5 adapter connection state")
    broker_connected: bool
    source: str = Field(description="BROKER | SIMULATED | REPLAY")
    new_orders_blocked: bool = Field(
        description="§11 — whether new Shadow/Live orders are blocked"
    )


class BalanceSchema(BaseModel):
    """Account balance (§2).  Amounts are in ``currency``."""

    account_id: str
    currency: str
    cash: float
    available_cash: float
    frozen_cash: float
    market_value: float
    total_asset: float
    buying_power: float
    broker_timestamp: Optional[datetime] = Field(
        default=None, description="Broker's own snapshot time (§13)"
    )
    received_timestamp: Optional[datetime] = Field(
        default=None, description="When ICYQuant pulled it (§13)"
    )
    consistent: bool = Field(description="cash/total identities hold (§3)")


# ── position ──────────────────────────────────────────────────────


class PositionSchema(BaseModel):
    """One broker position (§3) with its §18 valuation."""

    symbol: str
    exchange: str = ""
    name: Optional[str] = Field(
        default=None, description="Instrument Master name (§2 / §20)"
    )
    quantity: float
    available_quantity: float = Field(
        description="As the broker reported it — T+1 may differ (§19)"
    )
    frozen_quantity: float
    average_cost: float
    market_price: Optional[float] = Field(
        default=None, description="Market Data price (§18); null when unpriced"
    )
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    status: PositionStatusName = Field(description="VALID | INVALID (§3)")
    consistent: bool = Field(
        description="quantity == available_quantity + frozen_quantity (§3)"
    )
    broker_timestamp: Optional[datetime] = None
    received_timestamp: Optional[datetime] = None


class ReconciliationItemSchema(BaseModel):
    """One check on one symbol (or the balance) (§10)."""

    symbol: str
    check: str
    broker_value: Optional[float] = None
    ledger_value: Optional[float] = None
    difference: Optional[float] = None
    status: ReconciliationStatusName


class ReconciliationSchema(BaseModel):
    """Broker vs Position Ledger verdict (§10 / §11)."""

    account_id: str
    snapshot_id: str
    timestamp: datetime
    status: ReconciliationStatusName
    outcome: ReconciliationOutcomeName
    checked: int
    matched: int
    mismatch: int
    missing_broker: int
    missing_ledger: int
    invalid: int
    mismatch_count: int
    items: list[ReconciliationItemSchema] = Field(default_factory=list)


class PositionListResponse(BaseModel):
    """``GET /api/accounts/{account_id}/positions`` (§15)."""

    account_id: str
    status: AccountStatusName
    snapshot_id: str
    snapshot_timestamp: datetime
    count: int
    positions: list[PositionSchema]
    positions_market_value: float
    total_cost: float
    total_unrealized_pnl: float
    reconciliation: Optional[ReconciliationSchema] = None


# ── sync status (§12 / §13 / §14) ─────────────────────────────────


class SyncStatusResponse(BaseModel):
    """``GET /api/accounts/{account_id}/sync-status`` (§15)."""

    account_id: str
    status: AccountStatusName
    health: SyncHealthName
    connection_state: str
    broker_connected: bool
    provider: str
    source: str
    last_successful_sync: Optional[datetime] = None
    last_sync_age_seconds: Optional[float] = None
    sync_latency_ms: Optional[float] = None
    stale_after_seconds: float = Field(
        description="§12 SYNCED → STALE threshold"
    )
    sync_interval_seconds: float = Field(description="§6 snapshot cadence")
    position_count: int
    invalid_count: int
    mismatch_count: int
    snapshot_count: int
    reconciliation_status: Optional[ReconciliationStatusName] = None
    reconciliation_outcome: Optional[ReconciliationOutcomeName] = None
    new_orders_blocked: bool


# ── snapshots (§7) ────────────────────────────────────────────────


class SnapshotSchema(BaseModel):
    """One retained snapshot — the chain that makes history answerable (§7)."""

    snapshot_id: str
    account_id: str
    sequence: int
    status: AccountStatusName
    source: str
    timestamp: datetime
    received_timestamp: datetime
    sync_latency_ms: Optional[float] = None
    position_count: int
    reconciliation_status: Optional[str] = None
    reconciliation_outcome: Optional[str] = None
    balance: Optional[BalanceSchema] = None


class SnapshotListResponse(BaseModel):
    """``GET /api/accounts/{account_id}/snapshots`` (§15)."""

    account_id: str
    count: int
    limit: int
    snapshots: list[SnapshotSchema]


# ── detail / actions / health ─────────────────────────────────────


class AccountDetailResponse(BaseModel):
    """``GET /api/accounts/{account_id}``."""

    account: AccountSchema
    sync_status: SyncStatusResponse
    balance: Optional[BalanceSchema] = None
    positions: list[PositionSchema] = Field(default_factory=list)
    reconciliation: Optional[ReconciliationSchema] = None


class SyncActionResponse(BaseModel):
    """Result of a manual snapshot pull (§6)."""

    account_id: str
    status: AccountStatusName
    snapshot_id: str
    sequence: int
    position_count: int
    sync_latency_ms: Optional[float] = None
    reconciliation: Optional[ReconciliationSchema] = None


class ConnectionActionResponse(BaseModel):
    """Result of ``POST /connect`` / ``POST /disconnect`` (§5)."""

    provider: str
    connection_state: str
    broker_connected: bool
    accounts: list[str] = Field(default_factory=list)


class AccountHealthSchema(BaseModel):
    """One account's §14 sync health."""

    account_id: str
    status: AccountStatusName
    health: SyncHealthName
    connection_state: Optional[str] = None
    last_successful_sync: Optional[datetime] = None
    last_sync_age_seconds: Optional[float] = None
    sync_latency_ms: Optional[float] = None
    position_count: int
    mismatch_count: int
    invalid_count: int
    reconciliation_status: Optional[str] = None
    reconciliation_outcome: Optional[str] = None
    new_orders_blocked: bool


class AccountHealthResponse(BaseModel):
    """``GET /api/accounts/health`` — the §14 roll-up for Commit 013."""

    overall_health: SyncHealthName
    new_orders_blocked: bool = Field(
        description="§11 — Paper Trading is deliberately never in this flag"
    )
    account_count: int
    position_mismatch_count: int
    accounts: list[AccountHealthSchema] = Field(default_factory=list)


__all__ = [
    "AccountStatusName",
    "PositionStatusName",
    "ReconciliationStatusName",
    "ReconciliationOutcomeName",
    "SyncHealthName",
    "ErrorResponse",
    "AccountSchema",
    "AccountListResponse",
    "BalanceSchema",
    "PositionSchema",
    "ReconciliationItemSchema",
    "ReconciliationSchema",
    "PositionListResponse",
    "SyncStatusResponse",
    "SnapshotSchema",
    "SnapshotListResponse",
    "AccountDetailResponse",
    "SyncActionResponse",
    "ConnectionActionResponse",
    "AccountHealthSchema",
    "AccountHealthResponse",
]
