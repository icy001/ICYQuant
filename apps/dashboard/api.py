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
import uuid
from datetime import datetime, timezone
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


# In-memory run history (Integration 008): every completed/failed POST is
# recorded so the UI can list past runs and re-open a cached result via
# GET /dashboard/backtest/runs.  Bounded — keeps the newest MAX_RUNS.
_backtest_runs: list[dict] = []
_backtest_runs_lock = threading.Lock()
_BACKTEST_MAX_RUNS = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _record_backtest_run(status: str, config: dict,
                         payload: Optional[dict] = None,
                         error: Optional[str] = None) -> dict:
    """Append a run record to the history (caller holds no lock needed)."""
    meta = (payload or {}).get("meta") or {}
    record = {
        "run_id": "bt-" + _utc_now().strftime("%Y%m%d-%H%M%S") \
            + "-" + uuid.uuid4().hex[:6],
        "status": status,                     # completed | failed
        "created_at": _utc_now().isoformat(timespec="seconds"),
        "config": {
            "strategy": meta.get("alpha_id") or "Alpha021",
            "symbols": config.get("symbols") or [],
            "start": config.get("start"),
            "end": config.get("end"),
            "initial_capital": config.get("initial_capital"),
        },
        "metrics": {k: meta.get(k) for k in (
            "return_pct", "sharpe", "maxdd_pct", "win_rate",
            "profit_factor", "cagr")} if meta else {},
        "period": meta.get("period") if meta else None,
        "trades": len((payload or {}).get("trades") or []),
        "error": error,
        "result": payload,
    }
    with _backtest_runs_lock:
        _backtest_runs.append(record)
        del _backtest_runs[:-_BACKTEST_MAX_RUNS]
    return record


@router.get("/dashboard/backtest/universe")
def backtest_universe(
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Available backtest instruments + frozen strategy metadata (read-only).

    Surfaces what the sealed FACTOR_SPEC_REAL_D1 replay supports so the
    UI config form lists only runnable options.  No engine state is
    mutated.
    """
    from apps.runtime.factor_gate import (BACKTEST_UNIVERSE, SYMBOLS,
                                          data_dir as real_data_dir)

    root = real_data_dir()
    symbols = [
        {"symbol": s, "gate_passed": s in SYMBOLS,
         "data_available": (root / f"{s}_1d.csv").exists()}
        for s in BACKTEST_UNIVERSE
    ]
    return {
        "strategy": {
            "alpha_id": "Alpha021",
            "source_run": "factor-real-d1",
            "timeframe": "1D",
            "slippage_bps": 3,
            "frozen": True,       # formula/windows/orientation are sealed
        },
        "symbols": symbols,
    }


@router.get("/dashboard/backtest/runs")
def backtest_runs(
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Backtest run history (newest first) — the UI's Run list source."""
    with _backtest_runs_lock:
        runs = [
            {k: r[k] for k in (
                "run_id", "status", "created_at", "config", "metrics",
                "period", "trades", "error")}
            for r in reversed(_backtest_runs)
        ]
    return {"runs": runs, "total": len(runs)}


@router.get("/dashboard/backtest/runs/{run_id}")
def backtest_run_result(
    run_id: str,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Cached result payload for a recorded backtest run."""
    with _backtest_runs_lock:
        record = next(
            (r for r in _backtest_runs if r["run_id"] == run_id), None)
    if record is None:
        raise HTTPException(status_code=404,
                            detail=f"backtest run not found: {run_id}")
    if record["status"] != "completed" or record["result"] is None:
        raise HTTPException(
            status_code=409,
            detail=f"backtest run {run_id} did not complete: "
                   f"{record.get('error') or record['status']}")
    return record["result"]


@router.post("/dashboard/backtest/run")
def backtest_run(
    body: BacktestRequest,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Run a parameterised Alpha021 backtest on the real daily data.

    Product-layer wrapper only: the factor formula, windows and the
    train-IC orientation stay exactly as sealed in FACTOR_SPEC_REAL_D1
    (Factor Discovery v2 — CLOSED).  Each submission is recorded in the
    run history with its status (completed/failed) for the Runs list.
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
        _record_backtest_run("failed", body.model_dump(), error=str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # strip per-trade latency (wall-clock noise, meaningless for a replay)
    for r in payload["trades"]:
        r.pop("latency_total_us", None)
    record = _record_backtest_run(
        "completed", body.model_dump(), payload=payload)
    payload = {**payload, "run_id": record["run_id"]}
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


# ---------------------------------------------------------------------------
# Research API (Integration 007) — read-only views of Factor Discovery v2
# reports.  Reads from research/discovery/output/{run_id}/report.json.
# Does NOT modify Factor Engine, Gate, De-correlation, Alpha021, or Paper
# Trading — these endpoints only "read out" existing research results.
# ---------------------------------------------------------------------------

_RESEARCH_OUTPUT_DIR = (Path(__file__).resolve().parents[2]
                        / "research" / "discovery" / "output")

# Alpha101 formula strings — extracted read-only from
# research/discovery/factor/formulas.py (the sealed WorldQuant 101
# transcription).  Each alpha_* function carries the paper expression as
# leading comments; alphas that delegate (e.g. alpha_009/010) resolve their
# helper's comments.  Display-only: never re-implements the engine.
_ALPHA_FORMULA_CACHE: dict[str, str] | None = None


def _extract_formula(source: str) -> str:
    """Leading contiguous comment lines of a function, joined to one line."""
    lines: list[str] = []
    for line in source.splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(stripped.lstrip("# ").rstrip())
        elif stripped:
            break
    return " ".join(l for l in lines if l)


def _alpha_formulas() -> dict[str, str]:
    """Return {alpha_id: formula string} for all 101 alphas (read-only)."""
    global _ALPHA_FORMULA_CACHE
    if _ALPHA_FORMULA_CACHE is not None:
        return _ALPHA_FORMULA_CACHE
    formulas: dict[str, str] = {}
    try:
        import inspect
        import re

        from research.discovery.factor import formulas as formulas_mod

        for alpha_id, func in formulas_mod.ALPHA_FUNCS.items():
            formula = _extract_formula(inspect.getsource(func))
            if not formula:
                # delegated alpha (e.g. alpha_009/010) -> find helpers
                # *defined in formulas.py* in the return line and take the
                # first one carrying comments (operators like rank() are
                # skipped via the __module__ check)
                return_line = next(
                    (l for l in inspect.getsource(func).splitlines()
                     if "return" in l), "")
                for name in re.findall(r"\b(\w+)\s*\(", return_line):
                    helper = getattr(formulas_mod, name, None)
                    if (callable(helper)
                            and getattr(helper, "__module__", None)
                            == formulas_mod.__name__):
                        formula = _extract_formula(
                            inspect.getsource(helper))
                        if formula:
                            break
            formulas[alpha_id] = formula
    except Exception as exc:  # noqa: BLE001 — display-only, degrade softly
        logger.warning("alpha formula extraction failed: %s", exc)
    _ALPHA_FORMULA_CACHE = formulas
    return formulas


def _load_research_report(run_id: str) -> dict:
    """Load a Factor Discovery report.json (read-only)."""
    import json
    path = _RESEARCH_OUTPUT_DIR / run_id / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404,
                            detail=f"report not found: {run_id}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"report unreadable: {exc}") from exc


def _normalize_funnel(raw: dict) -> dict:
    """Normalize the funnel schema across experiment tracks.

    The Factor Discovery v2 reports use ``alphas_total`` / ``pairs_backtested``
    / ``final_alphas`` / ``decorrelated_alphas``; older tracks use
    ``candidates_total`` / ``candidates_backtested`` / ``final_candidates``
    without a de-correlation stage. The UI expects a single shape — this
    helper merges both into a canonical schema (missing fields → 0).
    """
    if not isinstance(raw, dict):
        return {}
    return {
        "alphas_total":         raw.get("alphas_total")
                                or raw.get("candidates_total") or 0,
        "pairs_backtested":     raw.get("pairs_backtested")
                                or raw.get("candidates_backtested") or 0,
        "validation_passed":   raw.get("validation_passed") or 0,
        "oos_passed":          raw.get("oos_passed") or 0,
        "robustness_passed":   raw.get("robustness_passed") or 0,
        "final_alphas":         raw.get("final_alphas")
                                or raw.get("final_candidates") or 0,
        "decorrelated_alphas": raw.get("decorrelated_alphas") or 0,
    }


@router.get("/dashboard/research/overview")
def research_overview(
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Research overview: all experiment runs with their funnels."""
    runs = []
    if _RESEARCH_OUTPUT_DIR.exists():
        for d in sorted(_RESEARCH_OUTPUT_DIR.iterdir()):
            if not (d.is_dir() and (d / "report.json").exists()):
                continue
            try:
                report = _load_research_report(d.name)
            except HTTPException:
                continue
            spec = report.get("spec", {})
            funnel = _normalize_funnel(report.get("funnel", {}))
            runs.append({
                "run_id": d.name,
                "experiment_id": report.get("experiment_id", d.name),
                "dataset": "Real" if "real" in d.name else "Synthetic",
                "timeframe": spec.get("timeframe", ""),
                "universe": spec.get("universe", []),
                "funnel": funnel,
                "report_generated_at": report.get("report_generated_at", ""),
            })
    return {"runs": runs}


@router.get("/dashboard/research/runs")
def research_runs(
    principal: Principal = Depends(require_roles()),
) -> dict:
    """List of experiment runs (summary)."""
    runs = []
    if _RESEARCH_OUTPUT_DIR.exists():
        for d in sorted(_RESEARCH_OUTPUT_DIR.iterdir()):
            if not (d.is_dir() and (d / "report.json").exists()):
                continue
            try:
                report = _load_research_report(d.name)
            except HTTPException:
                continue
            spec = report.get("spec", {})
            funnel = _normalize_funnel(report.get("funnel", {}))
            runs.append({
                "run_id": d.name,
                "experiment_id": report.get("experiment_id", d.name),
                "dataset": "Real" if "real" in d.name else "Synthetic",
                "timeframe": spec.get("timeframe", ""),
                "alphas": spec.get("alphas_total", 0),
                "candidates": funnel.get("final_alphas", 0),
                "decorrelated": funnel.get("decorrelated_alphas", 0),
                "status": "Completed",
                "report_generated_at": report.get("report_generated_at", ""),
            })
    return {"runs": runs}


@router.get("/dashboard/research/runs/{run_id}")
def research_run_detail(
    run_id: str,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Single run detail (spec + split + funnel)."""
    report = _load_research_report(run_id)
    return {
        "run_id": run_id,
        "experiment_id": report.get("experiment_id", run_id),
        "spec": report.get("spec", {}),
        "split": report.get("split", {}),
        "funnel": _normalize_funnel(report.get("funnel", {})),
        "report_generated_at": report.get("report_generated_at", ""),
        "runtime_seconds": report.get("runtime_seconds", 0),
    }


def _research_stage_flags(report: dict) -> dict[str, dict]:
    """Replay the engine's funnel stage logic per alpha (read-only).

    Mirrors FactorEngine.run() exactly: an alpha passes a stage when the
    number of assets whose checks pass *through* that stage reaches
    spec.thresholds.min_assets_passed.
    """
    thresholds = (report.get("spec") or {}).get("thresholds") or {}
    min_assets = thresholds.get("min_assets_passed", 3)
    flags: dict[str, dict] = {}
    outcomes = report.get("outcomes") or {}
    for alpha_id, per_asset in outcomes.items():
        def _count_through(check_name: str) -> int:
            n = 0
            for od in per_asset.values():
                ok = True
                for chk in od.get("checks", []):
                    if not chk.get("passed"):
                        ok = False
                        break
                    if chk.get("name") == check_name:
                        break
                if ok:
                    n += 1
            return n
        flags[alpha_id] = {
            "validation_passed":
                _count_through("validation_performance") >= min_assets,
            "oos_passed":
                _count_through("oos_performance") >= min_assets,
            "robustness_passed":
                sum(1 for od in per_asset.values() if od.get("passed"))
                >= min_assets,
        }
    return flags


def _research_pair_aggregates(report: dict) -> dict[str, dict]:
    """Mean OOS return / max drawdown per alpha over gate-passing pairs."""
    agg: dict[str, dict] = {}
    for p in report.get("ranked_pairs", []):
        aid = p.get("alpha_id", "")
        st = agg.setdefault(
            aid, {"n": 0, "oos_return": 0.0, "max_drawdown": 0.0})
        st["n"] += 1
        st["oos_return"] += p.get("oos_return") or 0.0
        st["max_drawdown"] += p.get("max_drawdown") or 0.0
    for st in agg.values():
        if st["n"]:
            st["oos_return"] = round(st["oos_return"] / st["n"], 6)
            st["max_drawdown"] = round(st["max_drawdown"] / st["n"], 6)
    return agg


def _research_family_index(report: dict) -> dict[str, dict]:
    """Map alpha_id -> decorrelation family (read-only)."""
    index: dict[str, dict] = {}
    for fam in ((report.get("decorrelation") or {}).get("families") or []):
        for member in fam.get("members", []) or []:
            index[member] = fam
    return index


@router.get("/dashboard/research/alphas")
def research_alphas(
    run_id: str = "factor-real-d1",
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Alpha list from a run (alpha_ranking)."""
    report = _load_research_report(run_id)
    dec = report.get("decorrelation", {})
    reps = set(dec.get("representatives", []))
    stages = _research_stage_flags(report)
    pairs = _research_pair_aggregates(report)
    families = _research_family_index(report)
    formulas = _alpha_formulas()
    alphas = []
    for row in report.get("alpha_ranking", []):
        aid = row.get("alpha_id", "")
        stage = stages.get(aid, {})
        agg = pairs.get(aid, {})
        fam = families.get(aid, {})
        alphas.append({
            "alpha_id": aid,
            "status": row.get("status", ""),
            "score": row.get("score", 0),
            "rank": row.get("rank", 0),
            "mean_oos_ic": row.get("mean_oos_ic"),
            "mean_oos_rank_ic": row.get("mean_oos_rank_ic"),
            "mean_oos_icir": row.get("mean_oos_icir"),
            "mean_oos_sharpe": row.get("mean_oos_sharpe"),
            "mean_oos_return": agg.get("oos_return"),
            "mean_max_drawdown": agg.get("max_drawdown"),
            "mean_turnover": row.get("mean_turnover"),
            "breadth": row.get("breadth"),
            "assets_passed": row.get("assets_passed", []),
            "assets_passed_count": row.get("assets_passed_count", 0),
            "validation_passed": stage.get("validation_passed"),
            "oos_passed": stage.get("oos_passed"),
            "robustness_passed": stage.get("robustness_passed"),
            "is_representative": aid in reps,
            "family": fam.get("family"),
            "formula": formulas.get(aid, ""),
        })
    return {"run_id": run_id, "alphas": alphas, "total": len(alphas)}


@router.get("/dashboard/research/alphas/{alpha_id}")
def research_alpha_detail(
    alpha_id: str,
    run_id: str = "factor-real-d1",
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Alpha detail: summary + ranked pairs + decorrelation family."""
    report = _load_research_report(run_id)
    summary = None
    for row in report.get("alpha_summary", []):
        if row.get("alpha_id") == alpha_id:
            summary = row
            break
    pairs = [p for p in report.get("ranked_pairs", [])
             if p.get("alpha_id") == alpha_id]
    dec = report.get("decorrelation", {})
    family = None
    for fam in dec.get("families", []):
        if alpha_id in fam.get("members", []) or \
                alpha_id == fam.get("representative"):
            family = fam
            break
    stage = _research_stage_flags(report).get(alpha_id, {})
    agg = _research_pair_aggregates(report).get(alpha_id, {})
    return {
        "alpha_id": alpha_id,
        "run_id": run_id,
        "formula": _alpha_formulas().get(alpha_id, ""),
        "summary": summary,
        "pairs": pairs,
        "family": family,
        "decorrelation_threshold": dec.get("threshold"),
        "validation_passed": stage.get("validation_passed"),
        "oos_passed": stage.get("oos_passed"),
        "robustness_passed": stage.get("robustness_passed"),
        "mean_oos_return": agg.get("oos_return"),
        "mean_max_drawdown": agg.get("max_drawdown"),
    }


@router.get("/dashboard/research/runs/{run_id}/report")
def research_run_report(
    run_id: str,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Raw research report for a run — the UI's View Report source."""
    base = _RESEARCH_OUTPUT_DIR / run_id
    for name, fmt in (("report.md", "markdown"), ("report.html", "html")):
        path = base / name
        if path.exists():
            try:
                return {
                    "run_id": run_id,
                    "format": fmt,
                    "content": path.read_text(encoding="utf-8"),
                }
            except OSError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"report unreadable: {exc}") from exc
    raise HTTPException(status_code=404,
                        detail=f"report not found: {run_id}")


@router.get("/dashboard/research/funnel/{run_id}")
def research_funnel(
    run_id: str,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """Funnel for a specific run."""
    report = _load_research_report(run_id)
    return {"run_id": run_id, "funnel": _normalize_funnel(report.get("funnel", {}))}


@router.get("/dashboard/research/decorrelation/{run_id}")
def research_decorrelation(
    run_id: str,
    principal: Principal = Depends(require_roles()),
) -> dict:
    """De-correlation families for a run."""
    report = _load_research_report(run_id)
    dec = report.get("decorrelation", {})
    return {
        "run_id": run_id,
        "threshold": dec.get("threshold"),
        "n_families": dec.get("n_families", 0),
        "families": dec.get("families", []),
        "representatives": dec.get("representatives", []),
    }


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
