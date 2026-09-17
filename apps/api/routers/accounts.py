"""Account / Position API — the single standard entry point (Commit 015 §15).

Mounted at ``/api/accounts``::

    GET  /                                 Account registry + connection
    GET  /health                           §14 sync health roll-up
    GET  /{account_id}                     Account + status + balance + positions
    GET  /{account_id}/balance             Balance (§2)
    GET  /{account_id}/positions           Positions + reconciliation (§3 / §10)
    GET  /{account_id}/sync-status         §12 status, §13 latency, §7 snapshots
    GET  /{account_id}/snapshots           Snapshot history (§7)
    POST /connect | /disconnect            Channel lifecycle (OPERATOR/ADMIN)
    POST /{account_id}/sync                Pull one snapshot (OPERATOR/ADMIN)

Design rules honoured here:

* **The API never talks to the broker** (§15).  Routes do no data work:
  they validate HTTP input, call
  :data:`~services.account.sync.service.account_service` and serialise a
  Pydantic model.  §17 holds by construction — Dashboard → API →
  AccountService → Snapshot, so the front end is never coupled to a
  vendor.
* **Reads are side-effect free.**  A ``GET`` serves the last retained
  snapshot; it never opens a broker connection.  Pulling fresh state is
  an explicit operator action (``POST /{account_id}/sync``), which is why
  ``/health`` is safe to poll.
* **Quality is never hidden.**  Every position payload carries ``status``
  (VALID/INVALID) and every account payload carries the §10
  reconciliation verdict, so a MISMATCH account is served *as* MISMATCH
  (§11) rather than as a plausible-looking number.
* **No snapshot yet is honest.**  404 ``ACCOUNT_SNAPSHOT_NOT_FOUND``
  rather than a fabricated empty account.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from apps.api.schemas.accounts import (
    AccountDetailResponse,
    AccountHealthResponse,
    AccountListResponse,
    AccountSchema,
    AccountsErrorResponse,
    BalanceSchema,
    ConnectionActionResponse,
    PositionListResponse,
    PositionSchema,
    ReconciliationItemSchema,
    ReconciliationSchema,
    SnapshotListResponse,
    SnapshotSchema,
    SyncActionResponse,
    SyncStatusResponse,
)
from apps.dashboard.auth import Principal, require_roles
from services.account.domain.account import Account
from services.account.domain.balance import AccountBalance
from services.account.domain.exceptions import AccountError
from services.account.domain.position import Position
from services.account.domain.snapshot import AccountSnapshot
from services.account.sync.exceptions import AccountSyncError
from services.account.sync.service import (
    AccountSyncService,
    account_service,
)
from services.market_data.universe import universe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_MAX_SNAPSHOT_LIMIT = 500

_ERROR_RESPONSES: dict = {
    400: {
        "model": AccountsErrorResponse,
        "description": "Bad request / unknown provider",
    },
    404: {
        "model": AccountsErrorResponse,
        "description": "Unknown account or no snapshot",
    },
    409: {
        "model": AccountsErrorResponse,
        "description": "Account / broker state conflict",
    },
    422: {
        "model": AccountsErrorResponse,
        "description": "Broker payload invalid",
    },
    502: {
        "model": AccountsErrorResponse,
        "description": "Broker account request failed",
    },
    503: {
        "model": AccountsErrorResponse,
        "description": "Broker channel unavailable",
    },
}


def accounts_error_handler(request, exc: AccountError):
    """Render any account error as one envelope (§15).

    :class:`~services.account.sync.exceptions.AccountSyncError` carries its
    own ``status_code``; a pure domain error falls back to 400 — the
    request was well-formed but the account data does not add up.
    """
    status_code = getattr(exc, "status_code", 400)
    return JSONResponse(status_code=status_code, content=exc.as_dict())


def _service() -> AccountSyncService:
    """Single shared service instance (§15 / §17)."""
    return account_service


# ══════════════════════════════════════════════════════════════════
# Serialisation helpers — domain object → Pydantic model
# ══════════════════════════════════════════════════════════════════


def _account_schema(account: Account) -> AccountSchema:
    return AccountSchema(
        account_id=account.account_id,
        name=account.name,
        broker=account.broker,
        currency=account.currency,
        status=account.status,
    )


def _balance_schema(balance: Optional[AccountBalance]) -> Optional[BalanceSchema]:
    if balance is None:
        return None
    return BalanceSchema(
        account_id=balance.account_id,
        currency=balance.currency,
        cash=float(balance.cash),
        available_cash=float(balance.available_cash),
        frozen_cash=float(balance.frozen_cash),
        market_value=float(balance.market_value),
        total_asset=float(balance.total_asset),
        buying_power=float(balance.buying_power),
        broker_timestamp=balance.broker_timestamp,
        received_timestamp=balance.received_timestamp,
        consistent=balance.consistent,
    )


def _position_schema(position: Position) -> PositionSchema:
    """One position (§3) — plus the Instrument Master name for §16's table.

    ``name`` is a display join on the §2 registry; the account model itself
    stays symbol-only, and §20's rule holds: the universe is not the
    position list, so a name may legitimately be ``None``.
    """
    instrument = universe.get(position.symbol)
    return PositionSchema(
        symbol=position.symbol,
        exchange=position.exchange,
        name=instrument.name if instrument else None,
        quantity=float(position.quantity),
        available_quantity=float(position.available_quantity),
        frozen_quantity=float(position.frozen_quantity),
        average_cost=float(position.average_cost),
        market_price=(
            None if position.market_price is None else float(position.market_price)
        ),
        market_value=(
            None if position.market_value is None else float(position.market_value)
        ),
        unrealized_pnl=(
            None if position.unrealized_pnl is None else float(position.unrealized_pnl)
        ),
        unrealized_pnl_pct=(
            None
            if position.unrealized_pnl_pct is None
            else float(position.unrealized_pnl_pct)
        ),
        status=position.status,
        consistent=position.consistent,
        broker_timestamp=position.broker_timestamp,
        received_timestamp=position.received_timestamp,
    )


def _reconciliation_schema(payload: Optional[dict]) -> Optional[ReconciliationSchema]:
    if not payload:
        return None
    return ReconciliationSchema(
        account_id=payload["account_id"],
        snapshot_id=payload["snapshot_id"],
        timestamp=payload["timestamp"],
        status=payload["status"],
        outcome=payload["outcome"],
        checked=payload["checked"],
        matched=payload["matched"],
        mismatch=payload["mismatch"],
        missing_broker=payload["missing_broker"],
        missing_ledger=payload["missing_ledger"],
        invalid=payload["invalid"],
        mismatch_count=payload["mismatch_count"],
        items=[
            ReconciliationItemSchema(**item) for item in payload.get("items", [])
        ],
    )


def _sync_status_schema(
    service: AccountSyncService, status: dict
) -> SyncStatusResponse:
    config = service.config
    account_id = status.get("account_id") or ""
    health = (
        service.health(account_id).get("health") if account_id else "OFFLINE"
    )
    return SyncStatusResponse(
        account_id=account_id,
        status=status.get("status", "OFFLINE"),
        health=health or "OFFLINE",
        connection_state=status.get("connection_state", "DISCONNECTED"),
        broker_connected=bool(status.get("broker_connected")),
        provider=status.get("provider", service.adapter.provider_name),
        source=status.get("source", service.source),
        last_successful_sync=status.get("last_successful_sync"),
        last_sync_age_seconds=status.get("last_sync_age_seconds"),
        sync_latency_ms=status.get("sync_latency_ms"),
        stale_after_seconds=config.max_sync_age_seconds,
        sync_interval_seconds=config.sync_interval_seconds,
        position_count=int(status.get("position_count") or 0),
        invalid_count=int(status.get("invalid_count") or 0),
        mismatch_count=int(status.get("mismatch_count") or 0),
        snapshot_count=int(status.get("snapshot_count") or 0),
        reconciliation_status=status.get("reconciliation_status"),
        reconciliation_outcome=status.get("reconciliation_outcome"),
        new_orders_blocked=bool(status.get("new_orders_blocked")),
    )


def _snapshot_schema(snapshot: AccountSnapshot) -> SnapshotSchema:
    reconciliation = snapshot.reconciliation or {}
    return SnapshotSchema(
        snapshot_id=snapshot.snapshot_id,
        account_id=snapshot.account_id,
        sequence=snapshot.sequence,
        status=snapshot.status,
        source=snapshot.source,
        timestamp=snapshot.timestamp,
        received_timestamp=snapshot.received_timestamp,
        sync_latency_ms=snapshot.sync_latency_ms,
        position_count=snapshot.position_count,
        reconciliation_status=reconciliation.get("status"),
        reconciliation_outcome=reconciliation.get("outcome"),
        balance=_balance_schema(snapshot.balance),
    )


def _sync_action_schema(snapshot: AccountSnapshot) -> SyncActionResponse:
    return SyncActionResponse(
        account_id=snapshot.account_id,
        status=snapshot.status,
        snapshot_id=snapshot.snapshot_id,
        sequence=snapshot.sequence,
        position_count=snapshot.position_count,
        sync_latency_ms=snapshot.sync_latency_ms,
        reconciliation=_reconciliation_schema(snapshot.reconciliation),
    )


# ══════════════════════════════════════════════════════════════════
# ① Account registry
# ══════════════════════════════════════════════════════════════════


@router.get(
    "",
    response_model=AccountListResponse,
    responses=_ERROR_RESPONSES,
    summary="Registered broker accounts",
)
def list_accounts(
    principal: Principal = Depends(require_roles()),
):
    """Every registered account with the §5 connection state (§15)."""
    service = _service()
    accounts = service.accounts()
    return AccountListResponse(
        accounts=[_account_schema(a) for a in accounts],
        count=len(accounts),
        provider=service.adapter.provider_name,
        connection_state=service.connection_state(),
        broker_connected=service.is_connected(),
        source=service.source,
        new_orders_blocked=service.new_orders_blocked(),
    )


@router.get(
    "/health",
    response_model=AccountHealthResponse,
    summary="Account / position sync health",
)
def get_account_health(
    principal: Principal = Depends(require_roles()),
):
    """§14 roll-up for Commit 013 — non-mutating, safe to poll.

    Declared before ``/{account_id}`` so ``health`` is never read as an
    account id.
    """
    return _service().health_report()


# ══════════════════════════════════════════════════════════════════
# ② Lifecycle (operator actions)
# ══════════════════════════════════════════════════════════════════


@router.post(
    "/connect",
    response_model=ConnectionActionResponse,
    responses=_ERROR_RESPONSES,
    summary="Open the broker account channel",
)
def connect_accounts(
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
):
    """Open the account channel (§5).  Idempotent at the adapter level."""
    service = _service()
    service.connect()
    return ConnectionActionResponse(
        provider=service.adapter.provider_name,
        connection_state=service.connection_state(),
        broker_connected=service.is_connected(),
        accounts=[a.account_id for a in service.accounts()],
    )


@router.post(
    "/disconnect",
    response_model=ConnectionActionResponse,
    responses=_ERROR_RESPONSES,
    summary="Close the broker account channel",
)
def disconnect_accounts(
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
):
    """Close the account channel — snapshots already stored stay readable."""
    service = _service()
    service.disconnect()
    return ConnectionActionResponse(
        provider=service.adapter.provider_name,
        connection_state=service.connection_state(),
        broker_connected=service.is_connected(),
        accounts=[a.account_id for a in service.accounts()],
    )


# ══════════════════════════════════════════════════════════════════
# ③ Account detail
# ══════════════════════════════════════════════════════════════════


@router.get(
    "/{account_id}",
    response_model=AccountDetailResponse,
    responses=_ERROR_RESPONSES,
    summary="One account with its latest state",
)
def get_account(
    account_id: str,
    principal: Principal = Depends(require_roles()),
):
    """Account + sync status + latest balance / positions (§15).

    A registered account that has never synced answers with ``OFFLINE``
    status and empty positions — honest, not fabricated.
    """
    service = _service()
    account = service.account(account_id)
    latest = service.latest(account_id)
    return AccountDetailResponse(
        account=_account_schema(account),
        sync_status=_sync_status_schema(service, service.status(account_id)),
        balance=_balance_schema(latest.balance if latest else None),
        positions=[_position_schema(p) for p in latest.positions] if latest else [],
        reconciliation=_reconciliation_schema(service.reconciliation(account_id)),
    )


@router.get(
    "/{account_id}/balance",
    response_model=BalanceSchema,
    responses=_ERROR_RESPONSES,
    summary="Latest account balance",
)
def get_balance(
    account_id: str,
    principal: Principal = Depends(require_roles()),
):
    """Cash / available / frozen / market value / total asset (§2)."""
    service = _service()
    service.account(account_id)
    return _balance_schema(service.balance(account_id))


@router.get(
    "/{account_id}/positions",
    response_model=PositionListResponse,
    responses=_ERROR_RESPONSES,
    summary="Latest positions",
)
def get_positions(
    account_id: str,
    principal: Principal = Depends(require_roles()),
):
    """Positions with the §10 reconciliation verdict attached (§15).

    The response carries ``status`` and ``reconciliation`` next to the
    numbers, so a caller physically cannot read a MISMATCH account as if
    it were reconciled.
    """
    service = _service()
    service.account(account_id)
    snapshot = service.require_snapshot(account_id)
    positions = list(snapshot.positions)
    return PositionListResponse(
        account_id=account_id,
        status=snapshot.status,
        snapshot_id=snapshot.snapshot_id,
        snapshot_timestamp=snapshot.timestamp,
        count=len(positions),
        positions=[_position_schema(p) for p in positions],
        positions_market_value=snapshot.total_market_value,
        total_cost=float(sum(p.average_cost * p.quantity for p in positions)),
        total_unrealized_pnl=float(
            sum(
                p.unrealized_pnl
                for p in positions
                if p.unrealized_pnl is not None
            )
        ),
        reconciliation=_reconciliation_schema(service.reconciliation(account_id)),
    )


@router.get(
    "/{account_id}/sync-status",
    response_model=SyncStatusResponse,
    responses=_ERROR_RESPONSES,
    summary="Sync status, latency and staleness",
)
def get_sync_status(
    account_id: str,
    principal: Principal = Depends(require_roles()),
):
    """§12 status, §13 latency, §7 snapshot count and §11 blocking flag."""
    service = _service()
    service.account(account_id)
    return _sync_status_schema(service, service.status(account_id))


@router.get(
    "/{account_id}/snapshots",
    response_model=SnapshotListResponse,
    responses=_ERROR_RESPONSES,
    summary="Retained snapshot history",
)
def get_snapshots(
    account_id: str,
    limit: int = Query(
        50,
        ge=1,
        le=_MAX_SNAPSHOT_LIMIT,
        description="How many snapshots to return, newest first (§7)",
    ),
    principal: Principal = Depends(require_roles()),
):
    """Newest-first snapshot chain — snapshots are never overwritten (§7).

    Answering "why did the system think I held 10,000 shares?" means
    re-reading the snapshot from that moment, so history is never
    compacted here.
    """
    service = _service()
    service.account(account_id)
    snapshots = service.snapshots(account_id, limit=limit)
    return SnapshotListResponse(
        account_id=account_id,
        count=len(snapshots),
        limit=limit,
        snapshots=[_snapshot_schema(s) for s in snapshots],
    )


# ══════════════════════════════════════════════════════════════════
# ④ Manual snapshot pull (operator action, §6)
# ══════════════════════════════════════════════════════════════════


@router.post(
    "/{account_id}/sync",
    response_model=SyncActionResponse,
    responses=_ERROR_RESPONSES,
    summary="Pull one account + position snapshot",
)
def sync_account(
    account_id: str,
    response: Response,
    connect: bool = Query(
        True,
        description="Open the channel first when it is not already connected",
    ),
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
):
    """Take a snapshot now (§6).

    Snapshot sync is a scheduled job in production; this endpoint is the
    operator's manual equivalent, so the Dashboard and Commit 017's E2E
    validation can drive the real pipeline instead of a fixture.  It goes
    through the service — the route still never calls a vendor SDK
    (§15 / §17).
    """
    service = _service()
    service.account(account_id)
    if connect and not service.is_connected():
        service.connect()
    snapshot = service.sync(account_id)
    response.status_code = 202
    return _sync_action_schema(snapshot)


__all__ = ["router", "accounts_error_handler"]
