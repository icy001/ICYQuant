"""
Dashboard API - served by the ICYQuant API gateway.

The Dashboard is API-only: every endpoint below reads the live state
of the attached pipeline through the Dashboard runtime (read-only
observation) or performs a control operation that is authorized and
audited by the Backend. The Dashboard never touches the database,
Redis, the event bus or any internal engine directly.
"""

from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from apps.dashboard import runtime
from apps.dashboard.auth import Principal, auth, require_roles
from apps.runtime.paper_trading import (
    PaperAccount,
    PaperTradingSession,
    SignalSpec,
    SimulatedMarketFeed,
)
from services.security.audit_center import AuditAction, AuditSeverity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Session management (one active paper session at a time)
# ---------------------------------------------------------------------------
_session: Optional[PaperTradingSession] = None
_session_thread: Optional[threading.Thread] = None
_session_stop = threading.Event()
_session_lock = threading.Lock()

_SESSION_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA"]
_SESSION_SIDES = ["BUY", "SELL"]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _stop_session() -> None:
    global _session, _session_thread, _session_stop
    _session_stop.set()
    if _session_thread is not None:
        _session_thread.join(timeout=2.0)
    _session = None
    _session_thread = None
    _session_stop = threading.Event()


def _start_feeder(session: PaperTradingSession, period_s: float) -> None:
    global _session_thread, _session_stop
    _session_stop = threading.Event()

    def feed() -> None:
        while not _session_stop.is_set():
            spec = SignalSpec(
                symbol=random.choice(_SESSION_SYMBOLS),
                side=random.choice(_SESSION_SIDES),
                quantity=random.randint(10, 250),
            )
            try:
                session.process(spec)
            except Exception as exc:  # noqa: BLE001 - keep the feed alive
                logger.warning("dashboard session feed error: %s", exc)
            # also push one routed intent through the Multi-Account Adapter
            # Layer so Accounts / Executions pages stay live during the run
            try:
                from apps.adapters.service import service as multi_service

                multi_service.submit_intent(multi_service.random_intent())
            except Exception as exc:  # noqa: BLE001 - keep the feed alive
                logger.warning("dashboard multi-account feed error: %s", exc)
            _session_stop.wait(period_s)

    thread = threading.Thread(
        target=feed, name="dashboard-session-feed", daemon=True
    )
    thread.start()
    _session_thread = thread


class LoginRequest(BaseModel):
    username: str
    password: str


# ===========================================================================
# Authentication
# ===========================================================================


@router.post("/auth/login")
def login(request: Request, body: LoginRequest) -> dict:
    try:
        return auth.login(
            body.username.strip(),
            body.password,
            ip_address=_client_ip(request),
        )
    except Exception:  # noqa: BLE001 - official auth failure surfaces as 401
        raise HTTPException(
            status_code=401, detail="Invalid username or password"
        )


@router.post("/auth/logout")
def logout(
    request: Request,
    principal: Principal = Depends(require_roles()),
) -> dict:
    auth.logout(principal, ip_address=_client_ip(request))
    return {"ok": True}


@router.get("/auth/me")
def me(principal: Principal = Depends(require_roles())) -> dict:
    return {"username": principal.username, "role": principal.role}


# ===========================================================================
# Read-only views
# ===========================================================================


@router.get("/dashboard")
def dashboard(principal: Principal = Depends(require_roles())) -> dict:
    """Single-call aggregated payload for the Dashboard UI page.

    Returns ``{account, positions, orders, risk, execution, strategies,
    alerts, meta}`` so the frontend can render every KPI card, position
    table, and status panel from one request instead of fanning out to
    six separate endpoints.
    """
    return runtime.dashboard_summary()


@router.get("/dashboard/overview")
def overview(principal: Principal = Depends(require_roles())) -> dict:
    return runtime.overview()


@router.get("/dashboard/strategies")
def strategies(principal: Principal = Depends(require_roles())) -> dict:
    return {"strategies": runtime.strategies()}


@router.get("/dashboard/strategies/{strategy_id}")
def strategy_detail(
    strategy_id: str, principal: Principal = Depends(require_roles())
) -> dict:
    signals = [
        s
        for s in runtime.signals()
        if (s.get("strategy_id") or "SCENARIO") == strategy_id
    ]
    decisions = [
        d
        for d in runtime.risk_decisions()
        if (d.get("strategy_id") or "SCENARIO") == strategy_id
    ]
    orders = [
        o
        for o in runtime.orders()
        if (o.get("strategy_id") or "SCENARIO") == strategy_id
    ]
    executions = [e for e in runtime.executions() if e["strategy_id"] == strategy_id]
    if not signals and not orders:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {
        "strategy_id": strategy_id,
        "status": "RUNNING" if signals else "IDLE",
        "signals": signals,
        "risk_decisions": decisions,
        "orders": orders,
        "executions": executions,
    }


@router.get("/dashboard/risk")
def risk(principal: Principal = Depends(require_roles())) -> dict:
    return runtime.risk()


@router.get("/dashboard/orders")
def orders(principal: Principal = Depends(require_roles())) -> dict:
    return {"orders": runtime.orders()}


@router.get("/dashboard/orders/{order_id}")
def order_detail(
    order_id: str, principal: Principal = Depends(require_roles())
) -> dict:
    trace = runtime.order_detail(order_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return trace


# ===========================================================================
# Integration 003 — Trading API (quote / preview / submit)
#
# Three thin endpoints that wrap existing internal capabilities:
#   - SimulatedMarketFeed.quote()  ->  GET  /dashboard/quote/{symbol}
#   - read-only pre-check          ->  POST /dashboard/orders/preview
#   - PaperTradingSession.process  ->  POST /dashboard/orders
#
# No new engines, no new market data service, no Order/Risk/Execution
# Engine core changes. These are pure adaptation-layer endpoints.
# ===========================================================================


class OrderTicketRequest(BaseModel):
    """Order ticket payload shared by preview + submit."""

    symbol: str
    side: str  # BUY / SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET / LIMIT
    price: Optional[float] = None  # required for LIMIT, ignored for MARKET


@router.get("/dashboard/quote/{symbol}")
def quote(
    symbol: str, principal: Principal = Depends(require_roles())
) -> dict:
    """Real-time quote for a symbol (observational, from the attached feed).

    Uses the active paper session's ``SimulatedMarketFeed.quote()`` when a
    session is running, falling back to the runtime's last-known trade
    prices. Bid/ask are derived from the mid price with an observational
    spread — this does NOT create a new market data service, it only
    surfaces what the feed already produces.
    """
    from datetime import datetime, timezone

    symbol = symbol.upper()
    last_price = 0.0
    base_price = 0.0
    source = "none"

    # 1) Active session's market feed (preferred)
    if _session is not None and getattr(_session, "feed", None) is not None:
        try:
            last_price = float(_session.feed.quote(symbol))
            base_prices = getattr(_session.feed, "_prices", {}) or {}
            base_price = float(base_prices.get(symbol, last_price))
            source = "paper_feed"
        except Exception:  # noqa: BLE001
            pass

    # 2) Fallback to runtime's last-known prices (from order fills)
    if not last_price:
        last_price = float(runtime._prices.get(symbol, 0.0))
        base_price = last_price
        source = "last_trade"

    # 3) Final fallback (nominal)
    if not last_price:
        last_price = 100.0
        base_price = 100.0
        source = "nominal"

    # Derive bid/ask from mid (observational half-spread, not a new service)
    half_spread = max(0.01, last_price * 0.0005)  # 5 bps
    bid = round(last_price - half_spread, 4)
    ask = round(last_price + half_spread, 4)

    change = round(last_price - base_price, 4)
    change_pct = round((change / base_price) * 100.0, 4) if base_price else 0.0

    return {
        "symbol": symbol,
        "last_price": round(last_price, 4),
        "bid": bid,
        "ask": ask,
        "spread": round(ask - bid, 4),
        "change": change,
        "change_pct": change_pct,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "session_running": _session is not None,
    }


@router.post("/dashboard/orders/preview")
def order_preview(
    body: OrderTicketRequest,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Read-only order preview: estimated value + risk/session readiness.

    Does NOT submit the order and does NOT call the Risk Engine. It only
    reports what the UI needs to render the "Review Order" panel: the
    current price, estimated notional, and observational readiness flags.
    """
    from datetime import datetime, timezone

    symbol = body.symbol.strip().upper()
    side = body.side.strip().upper()
    quantity = abs(int(body.quantity))
    order_type = body.order_type.strip().upper()

    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    # Reuse the quote logic to get the current price
    last_price = 0.0
    if _session is not None and getattr(_session, "feed", None) is not None:
        try:
            last_price = float(_session.feed.quote(symbol))
        except Exception:  # noqa: BLE001
            pass
    if not last_price:
        last_price = float(runtime._prices.get(symbol, 0.0))
    if not last_price:
        last_price = 100.0

    # Use the user's limit price if provided, else market price
    ref_price = (
        body.price
        if order_type == "LIMIT" and body.price
        else last_price
    )
    estimated_value = round(quantity * ref_price, 2)

    # Observational readiness flags (NOT a real Risk Engine check)
    session_running = _session is not None
    pipeline_attached = runtime.attached()
    warnings = []
    if not session_running:
        warnings.append("No paper trading session running — start a session first")
    if order_type == "LIMIT" and not body.price:
        warnings.append("Limit orders require a price")

    return {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
        "price": round(ref_price, 4),
        "last_price": round(last_price, 4),
        "estimated_value": estimated_value,
        "risk_check": {
            "status": "READY" if not warnings else "BLOCKED",
            "warnings": warnings,
            "session_running": session_running,
            "pipeline_attached": pipeline_attached,
        },
        "preview_only": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/dashboard/positions")
def positions(principal: Principal = Depends(require_roles())) -> dict:
    return runtime.portfolio()


@router.get("/dashboard/positions/{symbol}")
def position_detail(
    symbol: str, principal: Principal = Depends(require_roles())
) -> dict:
    """Single position + its ORDER_FILLED ledger history (Positions detail)."""
    detail = runtime.position_detail(symbol)
    if detail is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return detail


@router.get("/dashboard/accounts")
def accounts(principal: Principal = Depends(require_roles())) -> dict:
    return runtime.multi_accounts()


@router.get("/dashboard/accounts/{account_id}")
def account_detail(
    account_id: str, principal: Principal = Depends(require_roles())
) -> dict:
    detail = runtime.multi_account_detail(account_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return detail


@router.get("/dashboard/portfolio")
def global_portfolio(principal: Principal = Depends(require_roles())) -> dict:
    return runtime.global_portfolio()


@router.get("/dashboard/executions")
def executions(principal: Principal = Depends(require_roles())) -> dict:
    """Executions across the multi-account layer plus the paper pipeline."""
    multi = runtime.multi_executions()
    paper = []
    for e in runtime.executions():
        paper.append(
            {
                "execution_id": e.get("execution_id")
                or f"EXEC-PAPER-{e.get('order_id', '')}",
                "order_id": e.get("order_id") or "",
                "account_id": "paper",
                "broker_id": "paper",
                "symbol": e.get("symbol"),
                "market": "PAPER",
                "side": e.get("side"),
                "fill_quantity": e.get("quantity") or e.get("filled_quantity") or 0,
                "fill_price": e.get("price") or e.get("average_fill_price") or 0,
                "slippage": e.get("slippage", 0.0),
                "timestamp": e.get("timestamp"),
            }
        )
    combined = multi + paper
    combined.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return {"executions": combined}


@router.get("/dashboard/reconciliation")
def reconciliation(principal: Principal = Depends(require_roles())) -> dict:
    return {
        "reconciliation": runtime.reconciliation(),
        "accounts": runtime.multi_reconciliation(),
        "ledger_events": runtime.ledger_events()[-20:],
    }


@router.get("/health", include_in_schema=False)
def api_health(principal: Optional[Principal] = Depends(auth.optional)) -> dict:
    """Thin wrapper around the root ``GET /health`` endpoint.

    The Integration API client uses a single base URL pointing at ``/api``.
    Rather than making the client juggle two roots just for one health call,
    we mirror the public aggregated health under ``/api/health``.  Authentication
    is intentionally optional so the client can probe backend connectivity
    before (or without) a dashboard session.

    The returned shape mirrors ``GET /health`` exactly:
    ``{status, version, timestamp, services, bootstrap}``.
    """
    from apps.runtime.health_server import build_registry
    from core.bootstrap import get_bootstrap

    registry = build_registry()
    snapshot = registry.snapshot()
    snapshot["bootstrap"] = get_bootstrap().report()
    return snapshot


@router.get("/dashboard/system")
def system(principal: Principal = Depends(require_roles())) -> dict:
    health = runtime.system_health()
    return {
        "health": health,
        "services": health["services"],
        "dashboard": {
            "version": health.get("version"),
            "environment": health.get("app"),
            "attached": runtime.attached(),
            "attached_at": runtime.overview()["pipeline"]["attached_at"],
        },
    }


@router.get("/dashboard/alerts")
def alerts(principal: Principal = Depends(require_roles())) -> dict:
    return {"alerts": runtime.alerts()}


# ---------------------------------------------------------------------------
# Factor paper trading (Alpha021) - deterministic research-layer replay
# ---------------------------------------------------------------------------
_factor_paper_cache: Optional[dict] = None


@router.get("/dashboard/factor")
def factor_paper(principal: Principal = Depends(require_roles())) -> dict:
    """Alpha021 factor -> paper trading replay (static historical data).

    The replay is deterministic and independent of the live pipeline, so
    the result is cached after the first request.  Returns
    ``{"error": ...}`` with a friendly hint when the real daily data files
    have not been synced into the container yet.
    """
    global _factor_paper_cache
    if _factor_paper_cache is not None:
        return _factor_paper_cache
    try:
        from apps.runtime.factor_gate import build_paper_data, data_dir

        missing = [s for s in ("NVDA", "QQQ", "SPY")
                   if not (data_dir() / f"{s}_1d.csv").exists()]
        if missing:
            payload = {
                "error": "real daily data files not found under "
                         f"{data_dir()} (missing: {', '.join(missing)}); "
                         "sync with: docker cp data/real/d1 "
                         "icyquant-api:/app/data/real/",
            }
        else:
            payload = build_paper_data()
    except Exception as exc:  # noqa: BLE001 - surfaced on the page
        logger.warning("factor paper replay failed: %s", exc)
        payload = {"error": f"{type(exc).__name__}: {exc}"}
    if "error" not in payload:
        _factor_paper_cache = payload
    return payload


# ---------------------------------------------------------------------------
# Backtest page (product UI) - parameterised replay over frozen components
# ---------------------------------------------------------------------------
class BacktestRequest(BaseModel):
    symbols: list[str] = ["NVDA", "QQQ", "SPY"]
    start: Optional[str] = None       # "YYYY-MM-DD"; None = full history
    end: Optional[str] = None
    initial_capital: float = 1_000_000.0


@router.post("/dashboard/backtest/run")
def backtest_run(
    body: BacktestRequest,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Run a parameterised Alpha021 backtest on the real daily data.

    Product-layer wrapper only: the factor formula, windows and the
    train-IC orientation stay exactly as sealed in FACTOR_SPEC_REAL_D1
    (Factor Discovery v2 — CLOSED).
    """
    from apps.runtime.factor_gate import run_backtest

    if not body.symbols:
        raise HTTPException(status_code=400, detail="symbols must not be empty")
    if body.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    try:
        payload = run_backtest(
            symbols=body.symbols, start=body.start, end=body.end,
            initial_capital=body.initial_capital)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # strip per-trade latency (wall-clock noise, meaningless for a replay)
    for r in payload["trades"]:
        r.pop("latency_total_us", None)
    return payload


# ---------------------------------------------------------------------------
# Trading-UI config (paper account + risk rules), persisted as JSON
# ---------------------------------------------------------------------------
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "config" / "trading_ui.json"

_DEFAULT_CONFIG: dict = {
    "account": {
        "account_name": "Main Paper Account",
        "broker": "Simulated",
        "account_type": "Paper",          # Paper | Shadow | Live (display only)
        "initial_capital": 1_000_000.0,
        "currency": "USD",
    },
    "risk": {
        "max_daily_loss_pct": 3.0,
        "max_drawdown_pct": 6.0,
        "risk_per_trade_pct": 0.5,
    },
    "live_trading_enabled": False,
}


def _load_ui_config() -> dict:
    import json

    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            # merge over defaults so newly added keys never break the page
            merged = {
                **_DEFAULT_CONFIG,
                **data,
                "account": {**_DEFAULT_CONFIG["account"],
                            **data.get("account", {})},
                "risk": {**_DEFAULT_CONFIG["risk"],
                         **data.get("risk", {})},
            }
            return merged
        except (OSError, json.JSONDecodeError):
            logger.warning("trading-ui config unreadable, using defaults")
    return {**_DEFAULT_CONFIG}


class ConfigRequest(BaseModel):
    account_name: str = "Main Paper Account"
    broker: str = "Simulated"
    account_type: str = "Paper"
    initial_capital: float = 1_000_000.0
    currency: str = "USD"
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 6.0
    risk_per_trade_pct: float = 0.5


@router.get("/dashboard/config")
def get_config(principal: Principal = Depends(require_roles())) -> dict:
    cfg = _load_ui_config()
    cfg["connections"] = {
        "simulated": True,
        "brokers": [
            {"name": b, "connected": False}
            for b in ("Interactive Brokers", "盈透证券", "CTP", "Alpaca")
        ],
        "note": "No broker is connected. Live trading is NOT enabled.",
    }
    return cfg


@router.post("/dashboard/config")
def save_config(
    body: ConfigRequest,
    request: Request,
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
) -> dict:
    import json

    if body.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    for key, lo, hi in (("max_daily_loss_pct", 0.1, 50.0),
                        ("max_drawdown_pct", 0.1, 90.0),
                        ("risk_per_trade_pct", 0.01, 10.0)):
        v = getattr(body, key)
        if not (lo <= v <= hi):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be within [{lo}, {hi}]")
    cfg = {
        "account": {
            "account_name": body.account_name.strip() or "Main Paper Account",
            "broker": body.broker,
            "account_type": body.account_type,
            "initial_capital": body.initial_capital,
            "currency": body.currency,
        },
        "risk": {
            "max_daily_loss_pct": body.max_daily_loss_pct,
            "max_drawdown_pct": body.max_drawdown_pct,
            "risk_per_trade_pct": body.risk_per_trade_pct,
        },
        "live_trading_enabled": False,   # hard-off: frozen by design
    }
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    auth.record(
        AuditAction.ADMIN_ACTION,
        principal,
        target="trading_ui_config",
        severity=AuditSeverity.MEDIUM,
        details={"action": "save",
                 "account_type": body.account_type,
                 "broker": body.broker},
        ip_address=_client_ip(request),
    )
    return {"ok": True, "config": cfg}


# ---------------------------------------------------------------------------
# Factor candidates (Strategy page) - read-only view of the discovery report
# ---------------------------------------------------------------------------
@router.get("/dashboard/factor-candidates")
def factor_candidates(principal: Principal = Depends(require_roles())) -> dict:
    """Gate outcomes for the Strategy page (read-only).

    The Gate decides a candidate's stage — the UI only displays it.  Reads
    the sealed factor-real-d1 report; returns an empty list when absent.
    """
    import json

    report_path = (Path(__file__).resolve().parents[2]
                   / "research" / "discovery" / "output"
                   / "factor-real-d1" / "report.json")
    if not report_path.exists():
        return {"candidates": [], "source": "report not found"}
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"candidates": [], "source": "report unreadable"}
    dec = data.get("decorrelation", {})
    reps = set(dec.get("representatives", []))
    candidates = []
    for row in data.get("alpha_summary", []):
        aid = row["alpha_id"]
        if row.get("status") != "CANDIDATE":
            continue
        candidates.append({
            "alpha_id": aid,
            "stage": "PAPER" if aid == "Alpha021" else "CANDIDATE",
            "assets": row.get("assets_passed", []),
            "is_family_representative": aid in reps,
            "mean_oos_ic": row.get("mean_oos_ic"),
            "mean_oos_icir": row.get("mean_oos_icir"),
            "mean_oos_sharpe": row.get("mean_oos_sharpe"),
        })
    watch = [
        {
            "alpha_id": r["alpha_id"],
            "stage": "WATCH",
            "assets": [],
            "is_family_representative": r["alpha_id"] in reps,
            "mean_oos_ic": r.get("mean_oos_ic"),
            "mean_oos_icir": r.get("mean_oos_icir"),
            "mean_oos_sharpe": r.get("mean_oos_sharpe"),
        }
        for r in data.get("alpha_ranking", [])
        if r.get("status") != "CANDIDATE"
    ][:8]
    return {"candidates": candidates, "watch_list": watch,
            "families": dec.get("n_families"),
            "decorrelation_threshold": dec.get("threshold")}


@router.get("/dashboard/session")
def session_status(principal: Principal = Depends(require_roles())) -> dict:
    return {
        "running": _session is not None,
        "attached": runtime.attached(),
    }


# ===========================================================================
# Controls (authorized + audited)
# ===========================================================================


@router.post("/dashboard/orders/{order_id}/cancel")
def cancel_order(
    order_id: str,
    request: Request,
    principal: Principal = Depends(require_roles("TRADER", "ADMIN")),
) -> dict:
    pipeline = runtime.get_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=409, detail="No pipeline attached")
    try:
        order = pipeline.order_manager.cancel_order(
            order_id, reason="cancelled from dashboard"
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    auth.record(
        AuditAction.TRADE_CANCEL,
        principal,
        target=order_id,
        severity=AuditSeverity.MEDIUM,
        details={
            "symbol": order.symbol,
            "side": str(order.side),
            "quantity": order.quantity,
        },
        ip_address=_client_ip(request),
    )
    return {"order": runtime.serialize_order(order)}


@router.post("/dashboard/orders")
def submit_order(
    request: Request,
    body: OrderTicketRequest,
    principal: Principal = Depends(require_roles("TRADER", "ADMIN")),
) -> dict:
    """Submit a manual order through the paper trading session.

    Pushes a ``SignalSpec`` through the official engine chain
    (Risk → Order → Execution) by reusing ``PaperTradingSession.process()``
    which internally calls ``pipeline.submit_signal()``. This does NOT
    bypass or duplicate any engine logic — the same Risk Engine, Order
    Engine and Execution Engine that govern automated signals govern
    this manual ticket.

    Returns the created order (when one is produced), the session's
    metric record, and the linked risk decision so the UI can render
    Accepted / Rejected / Risk-Rejected / Filled states.
    """
    from datetime import datetime, timezone

    symbol = body.symbol.strip().upper()
    side = body.side.strip().upper()
    quantity = abs(int(body.quantity))
    order_type = body.order_type.strip().upper()

    if side not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    with _session_lock:
        if _session is None:
            raise HTTPException(
                status_code=409,
                detail="No paper trading session running. Start a session first.",
            )
        session = _session

    # Build the signal spec (reuses the official SignalSpec).
    # ref_price=None lets the session use the live feed quote for MARKET;
    # for LIMIT the user's price is honoured as the reference.
    ref_price = body.price if order_type == "LIMIT" and body.price else None
    spec = SignalSpec(symbol=symbol, side=side, quantity=quantity, ref_price=ref_price)

    # Push through the official chain (Risk → Order → Execution)
    result = session.process(spec)

    # Locate the most recently created order matching this ticket
    orders_list = runtime.orders()
    submitted_order = None
    for order in reversed(orders_list):
        if (
            order.get("symbol") == symbol
            and order.get("side") == side
            and int(order.get("quantity", 0) or 0) == quantity
        ):
            submitted_order = order
            break

    if result.get("rejected"):
        status_label = "REJECTED"
    elif result.get("error"):
        status_label = "ERROR"
    elif submitted_order and submitted_order.get("filled_quantity"):
        status_label = "FILLED"
    else:
        status_label = "SUBMITTED"

    auth.record(
        AuditAction.TRADE_EXECUTE,
        principal,
        target=submitted_order.get("order_id") if submitted_order else symbol,
        severity=AuditSeverity.MEDIUM,
        details={
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "price": body.price,
            "status": status_label,
            "result": result,
        },
        ip_address=_client_ip(request),
    )

    return {
        "order": submitted_order,
        "result": result,
        "risk_decision": submitted_order.get("risk_decision") if submitted_order else None,
        "status": status_label,
        "rejection_reason": result.get("reason") if result.get("rejected") else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/dashboard/session/start")
def session_start(
    request: Request,
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
) -> dict:
    global _session
    with _session_lock:
        _stop_session()
        session = PaperTradingSession(
            feed=SimulatedMarketFeed(), account=PaperAccount()
        )
        runtime.attach(session.pipeline)
        # immediate burst so the Dashboard shows live data right away
        for spec in [
            SignalSpec(symbol="AAPL", side="BUY", quantity=100),
            SignalSpec(symbol="MSFT", side="BUY", quantity=150),
            SignalSpec(symbol="NVDA", side="SELL", quantity=80),
        ]:
            session.process(spec)
        _start_feeder(session, period_s=5.0)
        _session = session
    auth.record(
        AuditAction.ADMIN_ACTION,
        principal,
        target="session",
        severity=AuditSeverity.INFO,
        details={"action": "start"},
        ip_address=_client_ip(request),
    )
    return {"ok": True, "session": session.report()}


@router.post("/dashboard/session/stop")
def session_stop(
    request: Request,
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
) -> dict:
    with _session_lock:
        report = _session.report() if _session is not None else None
        _stop_session()
        runtime.detach()
    auth.record(
        AuditAction.ADMIN_ACTION,
        principal,
        target="session",
        severity=AuditSeverity.INFO,
        details={"action": "stop"},
        ip_address=_client_ip(request),
    )
    return {"ok": True, "session": report}


@router.post("/dashboard/accounts/sync")
def accounts_sync(
    request: Request,
    principal: Principal = Depends(require_roles("OPERATOR", "ADMIN")),
) -> dict:
    """Trigger a full multi-account sync (authorized + audited)."""
    report = runtime.multi_sync()
    auth.record(
        AuditAction.ADMIN_ACTION,
        principal,
        target="accounts",
        severity=AuditSeverity.INFO,
        details={
            "action": "sync",
            "accounts": report.get("accounts"),
            "positions": report.get("positions"),
            "orders": report.get("orders"),
            "executions": report.get("executions"),
        },
        ip_address=_client_ip(request),
    )
    return report


# ---------------------------------------------------------------------------
# Audit log (read-only viewer for the Audit Center)
# ---------------------------------------------------------------------------

@router.get("/dashboard/audit-log")
def audit_log(
    principal: Principal = Depends(require_roles()),
    limit: int = 200,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    severity: Optional[str] = None,
) -> dict:
    """Audit log viewer with optional filters.

    Returns recent audit entries from the Dashboard AuditCenter.
    Supports filtering by action, actor, or severity.
    """
    from services.security.audit_center import AuditAction as AA, AuditSeverity as AS

    kwargs: dict = {"limit": min(limit, 1000)}
    if action:
        try:
            kwargs["action"] = AA(action)
        except ValueError:
            pass
    if actor:
        kwargs["actor"] = actor
    if severity:
        try:
            kwargs["severity"] = AS(severity.lower())
        except ValueError:
            pass

    entries = auth.audit.query(**kwargs)
    return {
        "entries": [e.to_dict() for e in reversed(entries)],
        "total": len(entries),
        "statistics": auth.audit.get_statistics(),
        "integrity": auth.audit.verify_integrity(),
    }


# ---------------------------------------------------------------------------
# Enhanced risk (VaR / Beta / breach / exposure breakdown)
# ---------------------------------------------------------------------------

@router.get("/dashboard/risk-enhanced")
def risk_enhanced(principal: Principal = Depends(require_roles())) -> dict:
    """Enhanced risk view: VaR, Beta, concentration, breach status."""
    from apps.dashboard import runtime as rt

    positions_list = rt.positions()
    total_eq = 100000.0 + sum(float(p.get("unrealized_pnl", 0)) for p in positions_list)
    total_exposure = sum(float(p.get("exposure", 0)) for p in positions_list)
    gross = total_exposure
    net = total_exposure  # long-only

    # Concentration by symbol
    conc = {}
    for p in positions_list:
        sym = p.get("symbol", "unknown")
        val = float(p.get("exposure", 0))
        conc[sym] = conc.get(sym, 0) + val
    conc_pct = {k: round(v / total_exposure * 100, 2) if total_exposure > 0 else 0.0
                for k, v in conc.items()}

    # Simple 1-day 95% VaR using historical vol (assume 2% daily vol proxy)
    daily_vol = 0.02
    var_95 = round(total_exposure * daily_vol * 1.65, 2)

    # Beta proxy (simple: 1.0 for paper account)
    beta = 1.0

    # Breach detection
    breaches = []
    max_dd = 0.0
    daily_loss = sum(float(p.get("unrealized_pnl", 0)) for p in positions_list)

    # Check against configured risk limits if available
    try:
        cfg = _load_ui_config()
        risk_limits = cfg.get("risk", {})
        max_daily_loss_pct = risk_limits.get("max_daily_loss_pct", 3.0)
        max_drawdown_pct = risk_limits.get("max_drawdown_pct", 6.0)
        if total_eq > 0:
            dd_pct = abs(daily_loss) / total_eq * 100
            if dd_pct >= max_daily_loss_pct:
                breaches.append({
                    "rule": "Max Daily Loss",
                    "limit_pct": max_daily_loss_pct,
                    "actual_pct": round(dd_pct, 2),
                    "severity": "CRITICAL",
                    "action": "Trading Halted",
                })
    except Exception:
        pass

    return {
        "summary": {
            "total_equity": round(total_eq, 2),
            "gross_exposure": round(gross, 2),
            "net_exposure": round(net, 2),
            "beta": beta,
            "var_95": var_95,
            "concentration": conc_pct,
            "position_count": len(positions_list),
        },
        "breaches": breaches,
        "trading_halted": len(breaches) > 0,
        "positions": positions_list,
    }
