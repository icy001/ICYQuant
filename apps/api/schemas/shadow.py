"""Shadow Trading API schemas (Commit 016 §22).

Every response states the two §22 facts explicitly::

    {"mode": "SHADOW", "real_orders_enabled": false}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ShadowStatusResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    running: bool
    started_at: Optional[str] = None
    feed: Dict[str, Any]
    account_reference: Dict[str, Any]
    counts: Dict[str, Any]
    config: Dict[str, Any]


class ShadowOrderSchema(BaseModel):
    order_id: str
    intent_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    strategy_id: str
    status: str
    reason: Optional[str] = None
    created_at: Optional[str] = None
    signal_timestamp: Optional[str] = None
    filled_quantity: int = 0
    avg_fill_price: Optional[str] = None


class ShadowFillSchema(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: str
    price_source: str
    notional: str
    market_timestamp: Optional[str] = None
    execution_timestamp: Optional[str] = None
    signal_timestamp: Optional[str] = None
    slippage_bps: float = 0.0
    commission: str = "0"
    status: str = "FILLED"


class ShadowOrdersResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    items: List[ShadowOrderSchema]
    count: int


class ShadowFillsResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    items: List[ShadowFillSchema]
    count: int


class ShadowPositionSchema(BaseModel):
    symbol: str
    quantity: int
    avg_cost: str
    realized_pnl: str
    market_price: Optional[str] = None
    market_value: Optional[str] = None
    unrealized_pnl: Optional[str] = None


class ShadowPositionsResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    items: List[ShadowPositionSchema]
    count: int
    broker_comparison: Dict[str, Any]


class ShadowPnLResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    initial_capital: str
    cash: str
    market_value: str
    equity: str
    realized_pnl: str
    unrealized_pnl: str
    daily_pnl: str
    total_pnl: str
    peak_equity: str
    drawdown: str
    day: Optional[str] = None
    timestamp: Optional[str] = None


class ShadowEventsResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    items: List[Dict[str, Any]]
    count: int


class ShadowActionResponse(BaseModel):
    mode: str = "SHADOW"
    real_orders_enabled: bool = False
    action: str
    running: bool
