"""OMS/EMS REST API.

FastAPI router providing endpoints for:
- Order creation and lifecycle management
- Order status queries
- Execution tracking
- Trade confirmation queries
- Order reconciliation

Endpoints:
    POST   /api/v1/orders              Create a new order
    GET    /api/v1/orders/active        Get active orders
    GET    /api/v1/orders/summary       Get order summary
    GET    /api/v1/orders/{order_id}    Get order status/details
    POST   /api/v1/orders/{order_id}/cancel    Cancel an order
    POST   /api/v1/orders/{order_id}/replace   Replace an order
    GET    /api/v1/orders/{order_id}/snapshot  Get execution snapshot
    GET    /api/v1/orders/{order_id}/fills     Get fill events
    GET    /api/v1/orders/{order_id}/report    Get execution report
    GET    /api/v1/confirmations/{order_id}    Get trade confirmations
    POST   /api/v1/confirmations/{cid}/reconcile  Reconcile confirmation
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..order.manager import (
    OrderManager,
    OrderModificationError,
    OrderNotFoundError,
    OrderValidationError,
)
from ..order.models import OrderSide, OrderStatus, OrderType, TimeInForce, OrderSource
from ..order.state_machine import InvalidTransitionError
from ..execution.tracker import ExecutionTracker, FillEvent
from ..execution.confirmation import TradeConfirmationEngine
from ..gateway.broker_gateway import PaperTradingGateway, BrokerOrderRequest
from ..gateway.adapter import BrokerAdapter


# =============================================================================
# Singleton instances (shared across requests)
# =============================================================================

order_manager = OrderManager()
execution_tracker = ExecutionTracker()
confirmation_engine = TradeConfirmationEngine()
paper_gateway = PaperTradingGateway()
broker_adapter = BrokerAdapter(gateway=paper_gateway)


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/api/v1", tags=["OMS"])


# =============================================================================
# Order Creation
# =============================================================================


@router.post("/orders", summary="Create a new order")
async def create_order(
    symbol: str = Query(..., description="Trading symbol (e.g., NVDA, AAPL)"),
    side: str = Query("BUY", description="BUY or SELL"),
    quantity: float = Query(..., description="Order quantity"),
    price: float = Query(0.0, ge=0, description="Limit price (0 for market)"),
    order_type: str = Query("MARKET", description="MARKET, LIMIT, STOP, STOP_LIMIT"),
    strategy_id: str = Query("", description="Originating strategy ID"),
    time_in_force: str = Query("DAY", description="DAY, GTC, IOC, FOK"),
    source: str = Query("STRATEGY", description="Order source"),
    broker: str = Query("", description="Target broker"),
    market: str = Query("", description="Target market/exchange"),
):
    """Create a new order.

    Example request:
        POST /api/v1/orders?symbol=NVDA&side=BUY&quantity=10000&strategy_id=AI_Momentum

    Example response:
        {
            "order_id": "ORD_20260728_000001",
            "symbol": "NVDA",
            "side": "BUY",
            "quantity": 10000,
            "status": "CREATED"
        }
    """
    # Validate quantity at app level
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    try:
        order = order_manager.create_order(
            symbol=symbol,
            side=OrderSide(side.upper()),
            quantity=quantity,
            price=price,
            order_type=OrderType(order_type.upper()),
            strategy_id=strategy_id,
            time_in_force=TimeInForce(time_in_force.upper()),
            source=OrderSource(source.upper()),
            broker=broker,
            market=market,
        )
        return order.to_dict()
    except (ValueError, OrderValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Static-path endpoints (MUST come before /orders/{order_id})
# =============================================================================


@router.get("/orders/active", summary="List active orders")
async def list_active_orders():
    """Get all currently active orders.

    Example:
        GET /api/v1/orders/active
    """
    active_orders = order_manager.get_active_orders()
    return {
        "count": len(active_orders),
        "orders": [o.to_dict() for o in active_orders],
    }


@router.get("/orders/summary", summary="Get order summary")
async def get_orders_summary():
    """Get a summary of all orders grouped by status.

    Example:
        GET /api/v1/orders/summary
    """
    return order_manager.get_order_summary()


# =============================================================================
# Dynamic-path endpoints (/orders/{order_id})
# =============================================================================


@router.get("/orders/{order_id}", summary="Get order details")
async def get_order(order_id: str):
    """Get full order details including execution progress.

    Example:
        GET /api/v1/orders/ORD_20260728_000001

    Response:
        {
            "order_id": "ORD_20260728_000001",
            "status": "PARTIALLY_FILLED",
            "filled_quantity": 5000,
            "remaining_quantity": 5000,
            "fill_pct": "50.0%"
        }
    """
    order = order_manager.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return order.to_dict()


@router.post("/orders/{order_id}/cancel", summary="Cancel an order")
async def cancel_order(
    order_id: str,
    reason: str = Query("", description="Cancellation reason"),
):
    """Cancel an active order.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/cancel?reason=Strategy stopped
    """
    try:
        order = order_manager.cancel_order(order_id, reason=reason)
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/replace", summary="Replace (modify) an order")
async def replace_order(
    order_id: str,
    new_quantity: Optional[float] = Query(None, gt=0, description="New quantity"),
    new_price: Optional[float] = Query(None, gt=0, description="New limit price"),
):
    """Modify an active order's quantity or price.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/replace?new_quantity=15000
    """
    try:
        order = order_manager.replace_order(
            order_id,
            new_quantity=new_quantity,
            new_price=new_price,
        )
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OrderModificationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/validate", summary="Validate an order")
async def validate_order(order_id: str):
    """Move an order from CREATED to VALIDATED state.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/validate
    """
    try:
        order = order_manager.validate_order(order_id)
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/route", summary="Route an order to a broker")
async def route_order(
    order_id: str,
    broker: str = Query("", description="Target broker"),
    market: str = Query("", description="Target market"),
):
    """Move an order from VALIDATED to ROUTED state.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/route?broker=IBKR&market=NASDAQ
    """
    try:
        order = order_manager.route_order(order_id, broker=broker, market=market)
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/submit", summary="Submit an order to exchange")
async def submit_order(order_id: str):
    """Move an order from ROUTED to SUBMITTED state.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/submit
    """
    try:
        order = order_manager.submit_order(order_id)
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/acknowledge", summary="Acknowledge order receipt")
async def acknowledge_order(order_id: str):
    """Move an order from SUBMITTED to ACKNOWLEDGED state.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/acknowledge
    """
    try:
        order = order_manager.acknowledge_order(order_id)
        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/orders/{order_id}/fill", summary="Record an order fill")
async def fill_order(
    order_id: str,
    fill_quantity: float = Query(..., gt=0, description="Quantity filled"),
    fill_price: float = Query(..., gt=0, description="Fill price"),
    commission: float = Query(0.0, ge=0, description="Commission charged"),
):
    """Record a fill event on an order.

    Example:
        POST /api/v1/orders/ORD_20260728_000001/fill?fill_quantity=5000&fill_price=150.0&commission=1.50
    """
    try:
        order = order_manager.fill_order(order_id, fill_quantity, fill_price, commission)

        # Track the fill
        fill_event = FillEvent(
            order_id=order_id,
            fill_id=f"FILL_{order.status_history[-1]['timestamp']}",
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
        )

        # Start tracking if not already
        snapshot = execution_tracker.get_snapshot(order_id)
        if snapshot is None:
            execution_tracker.start_tracking(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
            )

        execution_tracker.on_fill(fill_event)

        # Confirm the trade
        confirmation_engine.confirm(
            order_id=order_id,
            broker_order_id=f"BRK_{order_id}",
            symbol=order.symbol,
            side=order.side.value,
            quantity=fill_quantity,
            price=fill_price,
            commission=commission,
        )

        return order.to_dict()
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidTransitionError, OrderValidationError) as e:
        raise HTTPException(status_code=409, detail=str(e))


# =============================================================================
# Execution Tracking Endpoints
# =============================================================================


@router.get("/orders/{order_id}/snapshot", summary="Get execution snapshot")
async def get_execution_snapshot(order_id: str):
    """Get real-time execution progress for an order.

    Example:
        GET /api/v1/orders/ORD_20260728_000001/snapshot

    Response:
        {
            "order_id": "ORD_20260728_000001",
            "filled_quantity": 5000,
            "remaining_quantity": 5000,
            "fill_pct": "50.0%",
            "status": "EXECUTING"
        }
    """
    snapshot = execution_tracker.get_snapshot(order_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No execution data for {order_id}")
    return snapshot.to_dict()


@router.get("/orders/{order_id}/fills", summary="Get fill events")
async def get_order_fills(order_id: str):
    """Get all fill events for an order.

    Example:
        GET /api/v1/orders/ORD_20260728_000001/fills
    """
    fills = execution_tracker.get_fills(order_id)
    return {
        "order_id": order_id,
        "fill_count": len(fills),
        "fills": [
            {
                "fill_id": f.fill_id,
                "quantity": f.quantity,
                "price": f.price,
                "timestamp": f.timestamp.isoformat(),
                "venue": f.venue,
                "commission": f.commission,
            }
            for f in fills
        ],
    }


@router.get("/orders/{order_id}/report", summary="Get execution report")
async def get_execution_report(order_id: str):
    """Get a final execution report for a completed order.

    Example:
        GET /api/v1/orders/ORD_20260728_000001/report
    """
    report = execution_tracker.get_report(order_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"No execution data for {order_id}")
    return report.to_dict()


# =============================================================================
# Confirmation Endpoints
# =============================================================================


@router.get("/confirmations/{order_id}", summary="Get trade confirmations for order")
async def get_confirmations(order_id: str):
    """Get all trade confirmations for a given order.

    Example:
        GET /api/v1/confirmations/ORD_20260728_000001
    """
    confirmations = confirmation_engine.get_confirmations_by_order(order_id)
    return {
        "order_id": order_id,
        "count": len(confirmations),
        "confirmations": [c.to_dict() for c in confirmations],
    }


@router.post("/confirmations/{confirmation_id}/reconcile", summary="Reconcile a trade")
async def reconcile_confirmation(
    confirmation_id: str,
    broker_quantity: float = Query(..., gt=0, description="Broker-reported quantity"),
    broker_price: float = Query(..., gt=0, description="Broker-reported price"),
):
    """Reconcile a trade confirmation against broker records.

    Example:
        POST /api/v1/confirmations/TC_20260728_000001/reconcile?broker_quantity=10000&broker_price=150.0
    """
    confirmation = confirmation_engine.get_confirmation(confirmation_id)
    if confirmation is None:
        raise HTTPException(status_code=404, detail=f"Confirmation not found: {confirmation_id}")

    matched = confirmation_engine.reconcile(
        confirmation_id,
        {"quantity": broker_quantity, "price": broker_price},
    )

    return {
        "confirmation_id": confirmation_id,
        "matched": matched,
        "status": confirmation.status.value,
        "oms_quantity": confirmation.quantity,
        "oms_price": confirmation.price,
        "broker_quantity": broker_quantity,
        "broker_price": broker_price,
    }
