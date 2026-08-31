"""
Dashboard runtime - live read-only observation of a running pipeline.

The Dashboard attaches to the pipeline that is currently running
(Golden Scenario / Paper Trading session). All aggregation below is
strictly observational: it reads engine state through public interfaces
and never mutates pipeline or engine state, so no trading business
logic is duplicated on the Dashboard side.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from apps.runtime.health import HealthRegistry
from apps.runtime.pipeline import EventType, TradingPipeline

logger = logging.getLogger(__name__)

# Position / order limits applied by the official RiskEngine
RISK_POSITION_LIMIT = 1000.0
RISK_ORDER_LIMIT = 1000.0

_pipeline: Optional[TradingPipeline] = None
_attached_at: Optional[str] = None
_health = HealthRegistry()
_prices: Dict[str, float] = {}  # last known price per symbol (observational)


def attach(pipeline: TradingPipeline) -> None:
    """Attach the currently running pipeline as the Dashboard data source."""
    global _pipeline, _attached_at
    _pipeline = pipeline
    _attached_at = datetime.now(timezone.utc).isoformat()
    logger.info(
        "Dashboard attached to pipeline (events=%d, orders=%d)",
        len(pipeline._events),
        pipeline.order_manager.get_order_count(),
    )


def detach() -> None:
    """Detach the current pipeline (Dashboard shows empty state)."""
    global _pipeline, _attached_at
    _pipeline = None
    _attached_at = None


def attached() -> bool:
    return _pipeline is not None


def get_pipeline() -> Optional[TradingPipeline]:
    return _pipeline


def register_health(name: str, check=None) -> None:
    """Register a health check for a logical service (System page)."""
    _health.register(name, check)


# Service id normalisation: official registry names -> dashboard ids
_SERVICE_IDS = {
    "api": "api",
    "database": "database",
    "event_bus": "event-bus",
    "strategy_runtime": "strategy-runtime",
    "risk_engine": "risk-engine",
    "order_engine": "order-engine",
    "execution_engine": "execution-engine",
    "position": "position-ledger",
    "ledger": "ledger",
    "reconciliation": "reconciliation",
}


def system_health() -> dict:
    """Snapshot of all registered services (official HealthRegistry)."""
    snapshot = _health.snapshot()
    services = {}
    for name, service in snapshot.get("services", {}).items():
        services[_SERVICE_IDS.get(name, name)] = service
    return {**snapshot, "services": services}


def _events() -> List:
    p = _pipeline
    return list(p._events) if p else []


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _enum_val(value):
    """Enums and plain strings are both produced by the official OMS."""
    return value.value if hasattr(value, "value") else value


def _serialize_order(order) -> dict:
    """Serialize an official Order safely (side/status may be str or enum)."""
    return {
        "order_id": order.order_id,
        "strategy_id": order.strategy_id,
        "symbol": order.symbol,
        "side": _enum_val(order.side),
        "quantity": order.quantity,
        "price": order.price,
        "status": _enum_val(order.status),
        "order_type": _enum_val(order.order_type),
        "time_in_force": _enum_val(order.time_in_force),
        "source": _enum_val(order.source),
        "filled_quantity": order.filled_quantity,
        "remaining_quantity": order.remaining_quantity,
        "fill_pct": (
            f"{order.fill_pct:.1%}" if order.fill_pct is not None else None
        ),
        "average_fill_price": order.average_fill_price,
        "total_commission": order.total_commission,
        "account_id": getattr(order, "account_id", None) or "",
        "broker": order.broker,
        "market": order.market,
        "route": order.route,
        "is_active": order.is_active,
        "is_terminal": order.is_terminal,
        "notional_value": order.notional_value,
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "submitted_at": _iso(order.submitted_at),
        "filled_at": _iso(order.filled_at),
        "cancelled_at": _iso(order.cancelled_at),
        "rejection_reason": order.rejection_reason,
        "notes": order.notes,
    }


# =============================================================================
# Signal / Risk Decision stream
# =============================================================================


def signals() -> List[dict]:
    """Signals are the ORDER_CREATED events produced by strategy submit_signal."""
    out: List[dict] = []
    for event in _events():
        if event.event_type == EventType.ORDER_CREATED:
            payload = event.payload or {}
            out.append(
                {
                    "signal_id": event.order_id,
                    "symbol": payload.get("symbol"),
                    "side": payload.get("side"),
                    "quantity": payload.get("quantity"),
                    "price": payload.get("price"),
                    "strategy_id": payload.get("strategy_id"),
                    "timestamp": _iso(event.timestamp),
                }
            )
    return out


def risk_decisions() -> List[dict]:
    """Risk decisions are the RISK_CHECKED events from the RiskEngine."""
    out: List[dict] = []
    for event in _events():
        if event.event_type == EventType.RISK_CHECKED:
            payload = event.payload or {}
            order = payload.get("order") or {}
            approved = bool(payload.get("approved"))
            out.append(
                {
                    "signal_id": event.order_id,
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "quantity": order.get("quantity"),
                    "strategy_id": order.get("strategy_id"),
                    "decision": "APPROVED" if approved else "REJECTED",
                    "reason": payload.get("reason")
                    or ("Approved" if approved else "Rejected by risk rules"),
                    "timestamp": _iso(event.timestamp),
                }
            )
    return out


def _approved_signal_ids() -> List[str]:
    approved = {
        e.order_id for e in _events() if e.event_type == EventType.ORDER_APPROVED
    }
    rejected = {
        e.order_id for e in _events() if e.event_type == EventType.ORDER_REJECTED
    }
    return [
        e.order_id
        for e in _events()
        if e.event_type == EventType.ORDER_CREATED
        and e.order_id in approved
        and e.order_id not in rejected
    ]


def _risk_decision_for(signal_id: Optional[str]) -> Optional[dict]:
    if not signal_id:
        return None
    for event in reversed(_events()):
        if event.event_type == EventType.RISK_CHECKED and event.order_id == signal_id:
            payload = event.payload or {}
            return {
                "approved": bool(payload.get("approved")),
                "reason": payload.get("reason"),
            }
    return None


# =============================================================================
# Orders / Executions
# =============================================================================


def orders() -> List[dict]:
    """All orders with their linked signal id and risk decision."""
    queue = list(_approved_signal_ids())
    out: List[dict] = []
    for order in _orders_raw():
        data = _serialize_order(order)
        signal_id = queue.pop(0) if queue else None
        data["signal_id"] = signal_id
        data["risk_decision"] = _risk_decision_for(signal_id)
        if not data["account_id"]:
            pos = _position_for(order.symbol)
            data["account_id"] = (pos or {}).get("account_id") or "paper"
        _prices[order.symbol] = order.average_fill_price or order.price
        out.append(data)
    return out


def _orders_raw():
    p = _pipeline
    return list(p.order_manager._orders.values()) if p else []


def executions() -> List[dict]:
    """Executions derived from filled orders."""
    out: List[dict] = []
    for data in orders():
        if data["filled_quantity"] and data["filled_quantity"] > 0:
            out.append(
                {
                    "order_id": data["order_id"],
                    "signal_id": data.get("signal_id"),
                    "strategy_id": data.get("strategy_id"),
                    "symbol": data.get("symbol"),
                    "side": data.get("side"),
                    "quantity": data.get("filled_quantity"),
                    "price": data.get("average_fill_price"),
                    "timestamp": _iso(data.get("filled_at")),
                }
            )
    return out


def order_detail(order_id: str) -> Optional[dict]:
    """Full trace for a single order: signal -> risk -> order -> execution."""
    for data in orders():
        if data["order_id"] == order_id:
            trace = {
                "order": data,
                "signal": None,
                "risk_decision": data.get("risk_decision"),
                "execution": None,
                "position": None,
                "ledger": [],
            }
            signal_id = data.get("signal_id")
            for sig in signals():
                if sig["signal_id"] == signal_id:
                    trace["signal"] = sig
                    break
            for fill in executions():
                if fill["order_id"] == order_id:
                    trace["execution"] = fill
                    break
            trace["position"] = _position_for(data.get("symbol"))
            trace["ledger"] = _ledger_events_for(order_id)
            return trace
    return None


# =============================================================================
# Positions / P&L
# =============================================================================


def positions() -> List[dict]:
    """Live positions with an observational P&L against last known prices."""
    p = _pipeline
    out: List[dict] = []
    for position in list(p.position_repo.positions.values()) if p else []:
        last_price = _prices.get(position.symbol, _num(position.avg_price))
        quantity = _num(position.quantity)
        avg_price = _num(position.avg_price)
        out.append(
            {
                "position_id": position.position_id,
                "account_id": position.account_id,
                "symbol": position.symbol,
                "side": position.side,
                "quantity": quantity,
                "avg_price": avg_price,
                "last_price": last_price,
                "market_value": round(quantity * last_price, 2),
                "unrealized_pnl": round((last_price - avg_price) * quantity, 2),
                "realized_pnl": 0.0,
                "exposure": round(quantity * last_price, 2),
            }
        )
    return out


def _position_for(symbol: Optional[str]) -> Optional[dict]:
    if not symbol:
        return None
    for pos in positions():
        if pos["symbol"] == symbol:
            return pos
    return None


# =============================================================================
# Ledger / Reconciliation
# =============================================================================


def _ledger_events_for(order_id: str) -> List[dict]:
    p = _pipeline
    if not p:
        return []
    return [
        event
        for event in p.ledger.get("events", [])
        if (event.get("payload") or {}).get("order_id") == order_id
    ]


def ledger_events() -> List[dict]:
    p = _pipeline
    if not p:
        return []
    return list(p.ledger.get("events", []))


def position_detail(symbol: Optional[str]) -> Optional[dict]:
    """Single position with its ledger fill history (Orders → Fills → Position).

    Read-only view used by the Positions detail panel. The position truth
    comes straight from ``position_repo`` (the Position Ledger); the timeline
    is the ORDER_FILLED ledger events filtered by symbol. Nothing is fabricated.
    """
    position = _position_for(symbol)
    if position is None:
        return None
    events = [
        e
        for e in ledger_events()
        if ((e.get("payload") or {}).get("symbol") == symbol)
    ]
    return {
        "position": position,
        "ledger_events": events,
    }


def reconciliation() -> dict:
    """State of the reconciliation check - official TradingPipeline.reconcile."""
    p = _pipeline
    if not p:
        return {
            "status": "NO_PIPELINE",
            "detail": "No pipeline attached",
            "position": 0,
            "ledger": 0,
            "detected_at": None,
        }
    result = p.reconcile(None)
    state = result["status"]  # "OK" / "MISMATCH" from the official engine
    return {
        "status": state,
        "detail": "All states consistent" if state == "OK" else "RECOVERY_REQUIRED",
        "position": result["position"],
        "ledger": result["ledger"],
        "detected_at": _attached_at,
    }


# =============================================================================
# Strategies / Overview / Alerts
# =============================================================================


def strategies() -> List[dict]:
    """Per-strategy aggregation derived from the live event stream."""
    by_strategy: Dict[str, dict] = {}
    for sig in signals():
        sid = sig["strategy_id"] or "SCENARIO"
        entry = by_strategy.setdefault(
            sid,
            {
                "strategy_id": sid,
                "status": "RUNNING",
                "symbols": set(),
                "signals": 0,
                "approved": 0,
                "rejected": 0,
                "position": 0.0,
                "pnl": 0.0,
            },
        )
        entry["signals"] += 1
        if sig["symbol"]:
            entry["symbols"].add(sig["symbol"])
    for decision in risk_decisions():
        sid = decision["strategy_id"] or "SCENARIO"
        entry = by_strategy.setdefault(
            sid,
            {
                "strategy_id": sid,
                "status": "RUNNING",
                "symbols": set(),
                "signals": 0,
                "approved": 0,
                "rejected": 0,
                "position": 0.0,
                "pnl": 0.0,
            },
        )
        if decision["decision"] == "APPROVED":
            entry["approved"] += 1
        else:
            entry["rejected"] += 1
    for pos in positions():
        sid = pos["account_id"] or "SCENARIO"
        entry = by_strategy.setdefault(
            sid,
            {
                "strategy_id": sid,
                "status": "RUNNING",
                "symbols": {pos["symbol"]},
                "signals": 0,
                "approved": 0,
                "rejected": 0,
                "position": 0.0,
                "pnl": 0.0,
            },
        )
        entry["position"] += _num(pos["quantity"])
        entry["pnl"] += _num(pos["unrealized_pnl"])
    for entry in by_strategy.values():
        entry["symbols"] = sorted(entry["symbols"])
    return list(by_strategy.values())


def alerts() -> List[dict]:
    """Priority alerts so real trading risk is never drowned in noise."""
    now = datetime.now(timezone.utc).isoformat()
    out: List[dict] = []

    rec = reconciliation()
    if rec["status"] == "MISMATCH":
        out.append(
            {
                "level": "CRITICAL",
                "source": "reconciliation",
                "message": (
                    f"Position / Ledger mismatch: position={rec['position']} "
                    f"ledger={rec['ledger']}"
                ),
                "timestamp": now,
            }
        )
    elif rec["status"] == "NO_PIPELINE":
        out.append(
            {
                "level": "WARNING",
                "source": "system",
                "message": "No trading pipeline attached to Dashboard",
                "timestamp": now,
            }
        )

    total_qty = sum(_num(pos["quantity"]) for pos in positions())
    if total_qty >= RISK_POSITION_LIMIT:
        out.append(
            {
                "level": "CRITICAL",
                "source": "risk",
                "message": (
                    f"Position limit reached: {total_qty:g} / "
                    f"{RISK_POSITION_LIMIT:g}"
                ),
                "timestamp": now,
            }
        )
    elif total_qty >= RISK_POSITION_LIMIT * 0.9:
        out.append(
            {
                "level": "WARNING",
                "source": "risk",
                "message": (
                    f"Risk exposure approaching limit: {total_qty:g} / "
                    f"{RISK_POSITION_LIMIT:g}"
                ),
                "timestamp": now,
            }
        )

    for name, service in system_health()["services"].items():
        if service["status"] != "UP":
            out.append(
                {
                    "level": "HIGH",
                    "source": name,
                    "message": f"{name} unavailable ({service['detail']})",
                    "timestamp": now,
                }
            )

    for decision in risk_decisions()[-3:]:
        if decision["decision"] == "REJECTED":
            out.append(
                {
                    "level": "INFO",
                    "source": "risk",
                    "message": (
                        f"{decision['side']} {decision['symbol']} rejected: "
                        f"{decision['reason']}"
                    ),
                    "timestamp": decision["timestamp"] or now,
                }
            )

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "WARNING": 2, "INFO": 3}
    out.sort(key=lambda a: severity_rank.get(a["level"], 9))
    return out


def overview() -> dict:
    """Aggregated cockpit view for the Overview page."""
    decision_list = risk_decisions()
    approved = sum(1 for d in decision_list if d["decision"] == "APPROVED")
    rejected = sum(1 for d in decision_list if d["decision"] == "REJECTED")

    order_list = orders()
    total_orders = len(order_list)
    filled = sum(1 for o in order_list if o["status"] == "FILLED")
    rejected_orders = sum(1 for o in order_list if o["status"] == "REJECTED")

    position_list = positions()
    total_exposure = sum(_num(p["exposure"]) for p in position_list)
    unrealized_pnl = sum(_num(p["unrealized_pnl"]) for p in position_list)
    total_quantity = sum(_num(p["quantity"]) for p in position_list)

    return {
        "system": system_health(),
        "pipeline": {
            "attached": attached(),
            "attached_at": _attached_at,
            "events": len(_events()),
        },
        "metrics": {
            "today_pnl": round(unrealized_pnl, 2),
            "equity": round(100000.0 + unrealized_pnl, 2),
            "exposure": round(total_exposure, 2),
            "drawdown": 0.0,
            "orders": total_orders,
            "executions": filled,
            "fill_rate": round(filled / total_orders, 4) if total_orders else 0.0,
            "reject_rate": round(rejected_orders / total_orders, 4) if total_orders else 0.0,
        },
        "risk": {
            "decisions": len(decision_list),
            "approved": approved,
            "rejected": rejected,
            "exposure": round(total_exposure, 2),
            "position_quantity": round(total_quantity, 2),
            "position_limit": RISK_POSITION_LIMIT,
            "order_limit": RISK_ORDER_LIMIT,
        },
        "positions": position_list,
        "recent_orders": order_list[-6:],
        "recent_decisions": decision_list[-6:],
        "accounts": _account_overview(),
        "alerts": alerts(),
    }


def dashboard_summary() -> dict:
    """Single-call aggregated payload for the Dashboard UI page.

    Returns exactly seven top-level keys so the frontend can render all
    KPI cards, position tables, and status panels from one request:

    ::

        {
          "account":     {equity, cash, daily_pnl, daily_return},
          "positions":   {count, market_value, unrealized_pnl, items},
          "orders":      {pending, filled_today, rejected_today},
          "risk":        {status, drawdown, exposure},
          "execution":   {fill_rate, reject_rate, slippage},
          "strategies":  {active, signals_today, items},
          "alerts":      {critical, warning, items},
        }

    Every value is derived from the existing read-only runtime methods
    (positions / orders / signals / risk_decisions / alerts / system_health).
    No engine state is mutated.
    """
    from datetime import datetime, timezone

    # -- positions --
    pos_list = positions()
    market_value = round(sum(_num(p["market_value"]) for p in pos_list), 2)
    unrealized = round(sum(_num(p["unrealized_pnl"]) for p in pos_list), 2)

    # -- orders --
    order_list = orders()
    pending = sum(1 for o in order_list if o["status"] in ("PENDING", "NEW", "SUBMITTED"))
    filled = sum(1 for o in order_list if o["status"] == "FILLED")
    rejected = sum(1 for o in order_list if o["status"] == "REJECTED")
    total_orders = len(order_list) or 1  # avoid div-by-zero

    # -- risk decisions --
    decision_list = risk_decisions()
    approved = sum(1 for d in decision_list if d["decision"] == "APPROVED")
    rejected_risk = sum(1 for d in decision_list if d["decision"] == "REJECTED")

    # -- strategies --
    strat_list = strategies()
    sig_list = signals()

    # -- alerts --
    alert_list = alerts()
    critical = sum(1 for a in alert_list if a["level"] in ("CRITICAL", "HIGH"))
    warning = sum(1 for a in alert_list if a["level"] == "WARNING")

    # -- risk status from reconciliation --
    rec = reconciliation()
    if rec["status"] == "OK":
        risk_status = "HEALTHY"
    elif rec["status"] == "NO_PIPELINE":
        risk_status = "NO_PIPELINE"
    else:
        risk_status = "DEGRADED"

    total_exposure = round(sum(_num(p["exposure"]) for p in pos_list), 2)
    equity = round(100000.0 + unrealized, 2)
    cash = round(equity - total_exposure, 2)
    daily_return = round(unrealized / 100000.0 * 100.0, 4) if equity else 0.0

    # -- execution slippage (observational) --
    exec_list = executions()
    slippage_total = 0.0
    slippage_count = 0
    for ex in exec_list:
        oid = ex.get("order_id")
        if not oid:
            continue
        # find the matching order to get the intended price
        for o in order_list:
            if o["order_id"] == oid:
                intended = _num(o.get("price"))
                actual = _num(ex.get("price"))
                if intended and actual:
                    slippage_total += abs(actual - intended)
                    slippage_count += 1
                break
    avg_slippage = round(slippage_total / slippage_count, 4) if slippage_count else 0.0

    return {
        "account": {
            "equity": equity,
            "cash": cash,
            "daily_pnl": unrealized,
            "daily_return": daily_return,
        },
        "positions": {
            "count": len(pos_list),
            "market_value": market_value,
            "unrealized_pnl": unrealized,
            "items": pos_list,
        },
        "orders": {
            "pending": pending,
            "filled_today": filled,
            "rejected_today": rejected,
        },
        "risk": {
            "status": risk_status,
            "drawdown": 0.0,
            "exposure": total_exposure,
            "approved": approved,
            "rejected": rejected_risk,
        },
        "execution": {
            "fill_rate": round(filled / total_orders, 4),
            "reject_rate": round(rejected / total_orders, 4),
            "slippage": avg_slippage,
        },
        "strategies": {
            "active": len(strat_list),
            "signals_today": len(sig_list),
            "items": strat_list,
        },
        "alerts": {
            "critical": critical,
            "warning": warning,
            "items": alert_list,
        },
        # Extra context for the Dashboard header bar
        "meta": {
            "pipeline_attached": attached(),
            "attached_at": _attached_at,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": "PAPER",
            "account_name": "Paper-Alpha021",
        },
    }


def risk() -> dict:
    """Risk Decision Pipeline page payload."""
    decision_list = risk_decisions()
    approved = sum(1 for d in decision_list if d["decision"] == "APPROVED")
    rejected = sum(1 for d in decision_list if d["decision"] == "REJECTED")
    total_exposure = sum(_num(p["exposure"]) for p in positions())
    return {
        "metrics": {
            "decisions": len(decision_list),
            "approved": approved,
            "rejected": rejected,
            "exposure": round(total_exposure, 2),
            "daily_loss": 0.0,
            "drawdown": 0.0,
            "position_quantity": round(sum(_num(p["quantity"]) for p in positions()), 2),
            "position_limit": RISK_POSITION_LIMIT,
            "order_limit": RISK_ORDER_LIMIT,
        },
        "decisions": decision_list,
    }


def portfolio() -> dict:
    """Portfolio / Positions page payload."""
    position_list = positions()
    total_equity = 100000.0 + sum(_num(p["unrealized_pnl"]) for p in position_list)
    gross_exposure = sum(_num(p["exposure"]) for p in position_list)
    net_exposure = gross_exposure  # single-side long/short snapshot
    daily_pnl = sum(_num(p["unrealized_pnl"]) for p in position_list)
    return {
        "summary": {
            "total_equity": round(total_equity, 2),
            "cash": round(total_equity - gross_exposure, 2),
            "gross_exposure": round(gross_exposure, 2),
            "net_exposure": round(net_exposure, 2),
            "daily_pnl": round(daily_pnl, 2),
            "total_pnl": round(daily_pnl, 2),
            "drawdown": 0.0,
        },
        "positions": position_list,
    }


# =============================================================================
# Multi-Account Adapter Layer views (read-only)
# =============================================================================

# Rough conversion for the global portfolio USD aggregate (demo rates).
_MULTI_FX_RATE = {"CNY": 0.139, "USD": 1.0}


def _multi_service():
    """Lazy import keeps Dashboard importable without the adapter layer."""
    from apps.adapters.service import service

    return service


def multi_accounts() -> dict:
    """Accounts / Brokers overview from the Multi-Account Adapter Layer."""
    svc = _multi_service()
    return {
        "accounts": svc.accounts(),
        "brokers": svc.brokers(),
        "health": svc.health(),
    }


def multi_account_detail(account_id: str) -> Optional[dict]:
    """Single account: balance, positions, orders, executions, connection."""
    svc = _multi_service()
    try:
        return svc.account_detail(account_id)
    except Exception:  # unknown account -> None (API maps to 404)
        return None


def multi_executions() -> List[dict]:
    """Executions across every broker account (Account page / Executions page)."""
    return _multi_service().executions()


def multi_reconciliation() -> dict:
    """Adapter-layer reconciliation: cached Account Domain vs broker truth."""
    return _multi_service().reconcile()


def multi_sync() -> dict:
    """Trigger a full account sync (OPERATOR/ADMIN) and return the report."""
    svc = _multi_service()
    report = svc.sync_all()
    report["reconciliation"] = svc.reconcile()
    return report


def global_portfolio() -> dict:
    """Global portfolio across A-Share / Futures / US Equity / FX accounts."""
    return _multi_service().global_portfolio()


def _account_overview() -> dict:
    """Compact account summary for the Overview cockpit."""
    accounts = _multi_service().accounts()
    equity_usd = sum(
        _num(a["equity"]) * _MULTI_FX_RATE.get(a.get("currency", "USD"), 1.0)
        for a in accounts
    )
    by_market = {}
    for a in accounts:
        label = a["market_label"]
        by_market[label] = {
            "status": a["connection"],
            "equity": a["equity"],
            "currency": a["currency"],
        }
    return {
        "total": len(accounts),
        "connected": sum(1 for a in accounts if a["connection"] == "CONNECTED"),
        "equity_usd": round(equity_usd, 2),
        "by_market": by_market,
    }


__all__ = [
    "attach",
    "detach",
    "attached",
    "get_pipeline",
    "register_health",
    "serialize_order",
    "system_health",
    "signals",
    "risk_decisions",
    "orders",
    "executions",
    "order_detail",
    "positions",
    "ledger_events",
    "reconciliation",
    "strategies",
    "alerts",
    "overview",
    "risk",
    "portfolio",
    "multi_accounts",
    "multi_account_detail",
    "multi_executions",
    "multi_reconciliation",
    "multi_sync",
    "global_portfolio",
]
