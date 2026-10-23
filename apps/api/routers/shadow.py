"""Shadow Trading API (Commit 016 §22).

::

    GET  /api/shadow/status
    GET  /api/shadow/orders
    GET  /api/shadow/fills
    GET  /api/shadow/positions
    GET  /api/shadow/pnl
    GET  /api/shadow/events
    POST /api/shadow/start      (operator)
    POST /api/shadow/stop       (operator)

Every response repeats the §22 banner — ``mode: SHADOW`` and
``real_orders_enabled: false`` — because an API that can only ever
say "simulated" should never leave room for doubt.

Read-only by construction: the endpoints delegate to
:class:`~services.shadow.service.ShadowTradingService`, which has no
symbol — literal or importable — pointing at a broker order API (§25).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from apps.dashboard.auth import Principal, require_roles
from apps.api.schemas.shadow import (
    ShadowActionResponse,
    ShadowEventsResponse,
    ShadowFillsResponse,
    ShadowOrdersResponse,
    ShadowPnLResponse,
    ShadowPositionsResponse,
    ShadowStatusResponse,
)
from services.shadow.service import get_shadow_service

router = APIRouter(prefix="/api/shadow", tags=["shadow"])


@router.get("/status", response_model=ShadowStatusResponse)
def shadow_status(principal: Principal = Depends(require_roles())):
    """Session status: mode, gate inputs and counters (§23 status card)."""
    return ShadowStatusResponse(**get_shadow_service().status())


@router.get("/orders", response_model=ShadowOrdersResponse)
def shadow_orders(
    limit: int = Query(100, ge=1, le=1000),
    principal: Principal = Depends(require_roles()),
):
    """Shadow orders (newest last)."""
    items = get_shadow_service().orders(limit=limit)
    return ShadowOrdersResponse(items=items, count=len(items))


@router.get("/fills", response_model=ShadowFillsResponse)
def shadow_fills(
    limit: int = Query(100, ge=1, le=1000),
    principal: Principal = Depends(require_roles()),
):
    """Simulated fills with the §7 field set."""
    items = get_shadow_service().fills(limit=limit)
    return ShadowFillsResponse(items=items, count=len(items))


@router.get("/positions", response_model=ShadowPositionsResponse)
def shadow_positions(
    principal: Principal = Depends(require_roles()),
):
    """Open shadow positions plus the §18 broker comparison view."""
    service = get_shadow_service()
    items = service.positions()
    return ShadowPositionsResponse(
        items=items,
        count=len(items),
        broker_comparison=service.broker_comparison(),
    )


@router.get("/pnl", response_model=ShadowPnLResponse)
def shadow_pnl(principal: Principal = Depends(require_roles())):
    """The §23 PnL card (initial capital, equity, daily/total, drawdown)."""
    return ShadowPnLResponse(**get_shadow_service().pnl())


@router.get("/events", response_model=ShadowEventsResponse)
def shadow_events(
    limit: int = Query(200, ge=1, le=2000),
    type: Optional[str] = Query(None, description="filter by §19 event type"),
    principal: Principal = Depends(require_roles()),
):
    """The §19 decision trail: signal → risk → order → fill → position → pnl."""
    items = get_shadow_service().events(type=type, limit=limit)
    return ShadowEventsResponse(items=items, count=len(items))


@router.post(
    "/start",
    response_model=ShadowActionResponse,
    dependencies=[Depends(require_roles("OPERATOR", "ADMIN"))],
)
def shadow_start(principal: Principal = Depends(require_roles())):
    """Start the session, resuming persisted shadow state (§14)."""
    status = get_shadow_service().start()
    return ShadowActionResponse(
        action="start",
        running=status["running"],
        mode="SHADOW",
        real_orders_enabled=False,
    )


@router.post(
    "/stop",
    response_model=ShadowActionResponse,
    dependencies=[Depends(require_roles("OPERATOR", "ADMIN"))],
)
def shadow_stop(principal: Principal = Depends(require_roles())):
    """Stop the session — shadow state persists in the event ledger."""
    status = get_shadow_service().stop()
    return ShadowActionResponse(
        action="stop",
        running=status["running"],
        mode="SHADOW",
        real_orders_enabled=False,
    )
