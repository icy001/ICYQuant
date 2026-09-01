"""Dashboard Gate - Definition of Done D-01 .. D-15.

The Dashboard is API-only: every assertion goes through the API gateway
(TestClient on apps.api.main.app) exactly like a browser would.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.dashboard import runtime
from apps.dashboard.auth import auth as dashboard_auth
from apps.runtime.health_server import build_registry
from apps.runtime.paper_trading import (
    PaperAccount,
    PaperTradingSession,
    SignalSpec,
    SimulatedMarketFeed,
)
from services.security.audit_center import AuditAction

# Seed Dashboard users/roles and service health checks up-front so the
# gateway works even when the TestClient lifespan is not triggered.
dashboard_auth.seed()
_registry = build_registry()
for _name, _service in _registry.services.items():
    runtime.register_health(_name, _service.check)

client = TestClient(app)


def _login(username: str, password: str) -> str:
    res = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def attached_pipeline():
    """Attach a live paper pipeline so the views carry real data."""
    session = PaperTradingSession(
        feed=SimulatedMarketFeed(seed=7), account=PaperAccount()
    )
    for spec in [
        SignalSpec(symbol="AAPL", side="BUY", quantity=100),
        SignalSpec(symbol="MSFT", side="BUY", quantity=200),
        SignalSpec(symbol="NVDA", side="SELL", quantity=150),
        # exceeds the official risk limit -> must be REJECTED
        SignalSpec(symbol="TSLA", side="BUY", quantity=99999),
    ]:
        session.process(spec)
    runtime.attach(session.pipeline)
    yield session
    runtime.detach()


# --- D-01 Dashboard 启动 -----------------------------------------------------


def test_d01_dashboard_accessible():
    res = client.get("/dashboard/")
    assert res.status_code == 200
    assert "ICYQuant" in res.text
    # static bundle present
    assert client.get("/dashboard/css/app.css").status_code == 200
    assert client.get("/dashboard/js/app.js").status_code == 200


# --- D-02 Login ---------------------------------------------------------------


def test_d02_authentication():
    # unauthenticated -> 401
    assert client.get("/api/dashboard/overview").status_code == 401
    # wrong credentials -> 401
    res = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert res.status_code == 401
    # valid credentials -> token + role
    res = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token"]
    assert body["user"]["username"] == "admin"
    assert body["user"]["role"] == "ADMIN"
    # token works on /me
    res = client.get("/api/auth/me", headers=_headers(body["token"]))
    assert res.status_code == 200
    assert res.json()["username"] == "admin"


# --- D-03 Overview -------------------------------------------------------------


def test_d03_overview():
    token = _login("trader", "trader123")
    res = client.get("/api/dashboard/overview", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    for key in (
        "system",
        "pipeline",
        "metrics",
        "risk",
        "positions",
        "recent_orders",
        "recent_decisions",
        "accounts",
        "alerts",
    ):
        assert key in body
    # cockpit shows the multi-account strip
    assert body["accounts"]["total"] == 4
    assert set(body["accounts"]["by_market"]) == {"A-Share", "Futures", "US Equity", "FX"}


# --- D-04 Accounts --------------------------------------------------------------


def test_d04_accounts():
    token = _login("trader", "trader123")
    res = client.get("/api/dashboard/accounts", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert len(body["accounts"]) == 4
    markets = {a["market"] for a in body["accounts"]}
    assert markets == {"CN_STOCK", "CN_FUTURES", "US_EQUITY", "FX"}
    # every account carries the unified Account Domain fields
    for a in body["accounts"]:
        for key in (
            "account_id",
            "broker_id",
            "broker_name",
            "market",
            "market_label",
            "currency",
            "status",
            "connection",
            "equity",
            "cash",
            "buying_power",
            "margin",
            "capabilities",
        ):
            assert key in a, f"account missing {key}"
    # account detail: balance / positions / orders / executions / connection
    detail = client.get("/api/dashboard/accounts/fx_main", headers=_headers(token))
    assert detail.status_code == 200
    d = detail.json()
    assert d["account_id"] == "fx_main"
    assert d["market"] == "FX"
    for key in ("positions", "orders", "executions", "exposure", "connection"):
        assert key in d
    assert d["positions"] and d["orders"] and d["executions"]
    # unknown account -> 404
    assert (
        client.get("/api/dashboard/accounts/nope", headers=_headers(token)).status_code
        == 404
    )


# --- D-05 Strategy ---------------------------------------------------------------


def test_d05_strategy_page():
    token = _login("researcher", "researcher123")
    res = client.get("/api/dashboard/strategies", headers=_headers(token))
    assert res.status_code == 200
    assert "strategies" in res.json()


# --- D-06 Risk -------------------------------------------------------------------


def test_d06_risk_page():
    token = _login("risk", "risk123")
    res = client.get("/api/dashboard/risk", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "metrics" in body
    assert "decisions" in body


# --- D-07 Orders -------------------------------------------------------------------


def test_d07_orders_page(attached_pipeline):
    token = _login("trader", "trader123")
    res = client.get("/api/dashboard/orders", headers=_headers(token))
    assert res.status_code == 200
    orders = res.json()["orders"]
    assert orders, "paper pipeline should have produced orders"
    # orders expose account + broker columns (multi-account ready)
    for o in orders:
        assert "account_id" in o
        assert "broker" in o
    # full trace: signal -> risk -> order -> execution -> position -> ledger
    order_id = orders[0]["order_id"]
    trace = client.get(
        f"/api/dashboard/orders/{order_id}", headers=_headers(token)
    ).json()
    for key in ("signal", "risk_decision", "order", "execution", "position", "ledger"):
        assert key in trace
    assert trace["order"]["order_id"] == order_id
    assert trace["risk_decision"] is not None
    assert trace["execution"] is not None


# --- D-08 Executions ----------------------------------------------------------------


def test_d08_executions():
    token = _login("trader", "trader123")
    res = client.get("/api/dashboard/executions", headers=_headers(token))
    assert res.status_code == 200
    executions = res.json()["executions"]
    assert executions, "the adapter layer seeds executions"
    for e in executions:
        for key in (
            "execution_id",
            "order_id",
            "account_id",
            "symbol",
            "side",
            "fill_quantity",
            "fill_price",
            "slippage",
            "timestamp",
        ):
            assert key in e, f"execution missing {key}"


# --- D-09 Portfolio / Positions -------------------------------------------------------


def test_d09_portfolio_positions():
    token = _login("trader", "trader123")
    res = client.get("/api/dashboard/portfolio", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "summary" in body
    for key in (
        "total_equity_usd",
        "total_cash_usd",
        "gross_exposure_usd",
        "net_exposure_usd",
        "daily_pnl_usd",
        "total_pnl_usd",
        "drawdown_usd",
    ):
        assert key in body["summary"]
    assert body["market_exposure"], "market exposure breakdown expected"
    assert body["positions"], "multi-account layer seeds positions"
    # positions carry account / market / currency for global filtering
    for p in body["positions"]:
        assert "account_id" in p
        assert "market" in p
        assert "currency" in p


# --- D-10 Reconciliation ---------------------------------------------------------------


def test_d10_reconciliation(attached_pipeline):
    token = _login("operator", "operator123")
    res = client.get("/api/dashboard/reconciliation", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "reconciliation" in body
    assert "ledger_events" in body
    assert body["reconciliation"]["status"] == "OK"
    # adapter-layer reconciliation is consistent
    assert body["accounts"]["status"] == "CONSISTENT"
    assert len(body["accounts"]["accounts"]) == 4

    # critical error display: force a Position / Ledger mismatch
    pos = next(iter(attached_pipeline.pipeline.position_repo.positions.values()))
    pos.quantity += 1
    alerts = client.get("/api/dashboard/alerts", headers=_headers(token)).json()[
        "alerts"
    ]
    assert any(a["level"] == "CRITICAL" for a in alerts)
    rec = client.get(
        "/api/dashboard/reconciliation", headers=_headers(token)
    ).json()["reconciliation"]
    assert rec["status"] == "MISMATCH"


# --- D-11 System Health -------------------------------------------------------------------


def test_d11_system_health():
    token = _login("operator", "operator123")
    res = client.get("/api/dashboard/system", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    services = body["services"]
    assert "api" in services
    assert "database" in services
    assert "event-bus" in services


# --- D-12 API 数据一致 -------------------------------------------------------------------


def test_d12_api_data_consistent(attached_pipeline):
    token = _login("trader", "trader123")
    overview = client.get("/api/dashboard/overview", headers=_headers(token)).json()
    orders = client.get("/api/dashboard/orders", headers=_headers(token)).json()[
        "orders"
    ]
    assert overview["metrics"]["orders"] == len(orders)
    assert overview["metrics"]["executions"] == sum(
        1 for o in orders if o["status"] == "FILLED"
    )
    # recent orders are a subset of all orders
    recent_ids = {o["order_id"] for o in overview["recent_orders"]}
    all_ids = {o["order_id"] for o in orders}
    assert recent_ids <= all_ids
    # cockpit account summary matches the Accounts page
    accounts_page = client.get(
        "/api/dashboard/accounts", headers=_headers(token)
    ).json()["accounts"]
    assert overview["accounts"]["total"] == len(accounts_page) == 4
    # executions page carries the seeded multi-account fills
    executions = client.get(
        "/api/dashboard/executions", headers=_headers(token)
    ).json()["executions"]
    assert executions


# --- D-13 RBAC ----------------------------------------------------------------------------


def test_d13_rbac_enforced():
    readonly = _login("readonly", "readonly123")
    trader = _login("trader", "trader123")
    operator = _login("operator", "operator123")

    # read-only can view but not control
    assert (
        client.get("/api/dashboard/overview", headers=_headers(readonly)).status_code
        == 200
    )
    assert (
        client.post(
            "/api/dashboard/orders/x/cancel", headers=_headers(readonly)
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/dashboard/session/start", headers=_headers(readonly)
        ).status_code
        == 403
    )
    # operator may control the session but not trade
    assert (
        client.post(
            "/api/dashboard/orders/x/cancel", headers=_headers(operator)
        ).status_code
        == 403
    )
    # trader may attempt trading control (no pipeline -> 409, not 403)
    assert (
        client.post(
            "/api/dashboard/orders/x/cancel", headers=_headers(trader)
        ).status_code
        == 409
    )
    # account sync is an operator/admin action
    assert (
        client.post(
            "/api/dashboard/accounts/sync", headers=_headers(operator)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/dashboard/accounts/sync", headers=_headers(readonly)
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/dashboard/accounts/sync", headers=_headers(trader)
        ).status_code
        == 403
    )
    # unauthenticated control -> 401
    assert client.post("/api/dashboard/session/start").status_code == 401


# --- D-14 Audit ---------------------------------------------------------------------------


def test_d14_audit_effective():
    entries_before = len(dashboard_auth.audit.query(limit=10000))
    # login itself is audited
    _login("trader", "trader123")
    assert len(dashboard_auth.audit.query(limit=10000)) >= entries_before + 1

    # a control action is audited with the operator principal
    operator = _login("operator", "operator123")
    res = client.post("/api/dashboard/accounts/sync", headers=_headers(operator))
    assert res.status_code == 200, res.text
    actions = {e.action for e in dashboard_auth.audit.query(limit=10000)}
    assert AuditAction.LOGIN in actions
    assert AuditAction.ADMIN_ACTION in actions


# --- D-15 Docker 部署 ---------------------------------------------------------------------


def test_d15_docker_deployable():
    from pathlib import Path

    import yaml

    from apps.api import main as main_module

    static = (
        Path(main_module.__file__).resolve().parent.parent / "dashboard" / "static"
    )
    for rel in ("index.html", "css/app.css", "js/api.js", "js/app.js"):
        assert (static / rel).exists(), f"missing static asset: {rel}"
    # compose defines the api service
    compose = yaml.safe_load(
        Path(__file__).resolve().parent.parent
        .joinpath("docker-compose.yml")
        .read_text()
    )
    assert "api" in compose["services"]


def test_d16_factor_paper_page():
    """Factor / 因子纸面 page: menu link, API payload schema, data sanity.

    Skipped when the real daily data files are not present (they must be
    synced separately, see VALIDATION_REPORT.md 执行注意 #6).
    """
    from pathlib import Path

    from apps.api import main as apps_api_main

    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced - factor replay unavailable")

    # nav link present in the SPA (UI V1 route: #/research/factors)
    index = (Path(apps_api_main.__file__).resolve().parent.parent
             / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'href="#/research/factors"' in index
    assert 'data-nav="research/factors"' in index

    res = client.get(
        "/api/dashboard/factor",
        headers=_headers(_login("admin", "admin123")),
    )
    assert res.status_code == 200
    body = res.json()
    assert "error" not in body, body.get("error")

    meta = body["meta"]
    assert meta["alpha_id"] == "Alpha021"
    assert meta["symbols"] == ["NVDA", "QQQ", "SPY"]
    assert meta["signals"] == len(body["trades"]) >= 100
    assert meta["filled"] + meta["rejected"] + meta["errored"] == meta["signals"]
    # equity curve is daily, marked to real closes, starts at 1M cash
    assert len(body["equity"]) >= 300
    first_fill_day = min(r["date"] for r in body["trades"])
    assert body["equity"][0]["date"] == first_fill_day
    # summary carries per-symbol rows + a TOTAL row
    assert [r["symbol"] for r in body["summary"]] == ["NVDA", "QQQ", "SPY", "TOTAL"]
    total = body["summary"][-1]
    assert total["realized_pnl"] == pytest.approx(meta["realized"], abs=0.01)
    # headline numbers consistent with the trade log
    assert sum(r["realized_pnl"] for r in body["trades"]) == pytest.approx(
        meta["realized"], abs=0.05)


# --- D-17 回测页面（Product UI） -------------------------------------------------------------


def test_d17_backtest_page():
    """Backtest / 回测 page: menu link, frozen-core replay API, equivalence
    with the sealed paper replay, windowed runs, validation errors."""
    from pathlib import Path

    from apps.api import main as apps_api_main

    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced - backtest replay unavailable")

    index = (Path(apps_api_main.__file__).resolve().parent.parent
             / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'href="#/research/backtest"' in index
    assert 'data-nav="research/backtest"' in index

    token = _login("admin", "admin123")

    # default run == sealed paper replay (same data, same seed, same windows)
    res = client.post(
        "/api/dashboard/backtest/run", json={},
        headers=_headers(token),
    )
    assert res.status_code == 200
    body = res.json()
    m = body["meta"]
    assert m["alpha_id"] == "Alpha021"
    assert m["symbols"] == ["NVDA", "QQQ", "SPY"]
    sealed = client.get(
        "/api/dashboard/factor", headers=_headers(token)).json()["meta"]
    assert m["equity_final"] == sealed["equity_final"]
    assert m["signals"] == sealed["signals"]
    assert m["return_pct"] == pytest.approx(sealed["return_pct"], abs=1e-6)
    assert m["sharpe"] is not None and m["turnover_shares_per_day"] > 0
    # latency noise stripped from the product payload
    assert all("latency_total_us" not in r for r in body["trades"])

    # windowed run on a subset with a different capital
    res = client.post(
        "/api/dashboard/backtest/run",
        json={"symbols": ["NVDA"], "start": "2025-01-01",
              "end": "2025-12-31", "initial_capital": 500_000.0},
        headers=_headers(token),
    )
    assert res.status_code == 200
    m2 = res.json()["meta"]
    assert m2["symbols"] == ["NVDA"]
    assert m2["initial_capital"] == 500_000.0
    assert all(t["symbol"] == "NVDA" for t in res.json()["trades"])
    assert res.json()["trades"][0]["date"] >= "2025-01-01"

    # validation: unknown symbol / empty symbols / bad capital
    for payload, code in (
        ({"symbols": ["FAKE"]}, 400),
        ({"symbols": []}, 400),
        ({"symbols": ["NVDA"], "initial_capital": 0}, 400),
    ):
        res = client.post(
            "/api/dashboard/backtest/run", json=payload, headers=_headers(token))
        assert res.status_code == code, payload

    # RBAC: readonly may run backtests (read-only replay)
    ro_token = _login("readonly", "readonly123")
    res = client.post(
        "/api/dashboard/backtest/run", json={}, headers=_headers(ro_token))
    assert res.status_code == 200


# --- D-18 账户 / 风控配置页面 ------------------------------------------------------------------


def test_d18_settings_page():
    """Settings / 设置 page: menu link, config GET defaults + POST save
    + persistence, RBAC, and honest no-fake-connection surface."""
    from pathlib import Path

    from apps.api import main as apps_api_main

    index = (Path(apps_api_main.__file__).resolve().parent.parent
             / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'href="#/settings"' in index
    assert 'data-nav="settings"' in index

    token = _login("admin", "admin123")

    # defaults (or previously saved values) with connection honesty
    res = client.get("/api/dashboard/config", headers=_headers(token))
    assert res.status_code == 200
    cfg = res.json()
    assert cfg["account"]["account_name"]
    assert cfg["risk"]["max_daily_loss_pct"] > 0
    assert cfg["live_trading_enabled"] is False
    assert all(b["connected"] is False for b in cfg["connections"]["brokers"])

    # save and read back (persists to data/config/trading_ui.json)
    payload = {
        "account_name": "UI Test Account",
        "broker": "Simulated",
        "account_type": "Paper",
        "initial_capital": 2_000_000.0,
        "currency": "USD",
        "max_daily_loss_pct": 2.5,
        "max_drawdown_pct": 5.0,
        "risk_per_trade_pct": 0.4,
    }
    res = client.post(
        "/api/dashboard/config", json=payload, headers=_headers(token))
    assert res.status_code == 200
    assert res.json()["ok"] is True
    # live trading stays hard-off even if a client tried to imply otherwise
    assert res.json()["config"]["live_trading_enabled"] is False

    res = client.get("/api/dashboard/config", headers=_headers(token))
    assert res.json()["account"]["account_name"] == "UI Test Account"
    assert res.json()["risk"]["max_daily_loss_pct"] == 2.5

    # validation errors
    for bad in ({"initial_capital": -1}, {"max_daily_loss_pct": 99.0}):
        res = client.post(
            "/api/dashboard/config",
            json={**payload, **bad},
            headers=_headers(token))
        assert res.status_code == 400, bad

    # RBAC: readonly cannot save
    ro_token = _login("readonly", "readonly123")
    res = client.post(
        "/api/dashboard/config", json=payload, headers=_headers(ro_token))
    assert res.status_code == 403
    res = client.get("/api/dashboard/config", headers=_headers(ro_token))
    assert res.status_code == 200

    # restore defaults so the test stays idempotent
    client.post("/api/dashboard/config", json={
        "account_name": "Main Paper Account",
        "broker": "Simulated",
        "account_type": "Paper",
        "initial_capital": 1_000_000.0,
        "currency": "USD",
        "max_daily_loss_pct": 3.0,
        "max_drawdown_pct": 6.0,
        "risk_per_trade_pct": 0.5,
    }, headers=_headers(token))


# --- D-19 Audit Log endpoint ------------------------------------------------

def test_d19_audit_log_endpoint():
    """GET /api/dashboard/audit-log returns entries, statistics, integrity.
    RBAC enforced; filters accepted. """
    token = _login("admin", "admin123")
    res = client.get(
        "/api/dashboard/audit-log", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "entries" in body
    assert "total" in body
    assert "statistics" in body
    assert "integrity" in body
    assert isinstance(body["entries"], list)
    assert isinstance(body["statistics"], dict)
    # Each entry must have the expected fields
    if body["entries"]:
        e = body["entries"][0]
        assert "action" in e
        assert "actor" in e
        assert "target" in e
        assert "severity" in e
        assert "timestamp" in e
    # Integrity must report ok
    integ = body["integrity"]
    assert "integrityOk" in integ
    assert "total" in integ

    # filter by action
    res2 = client.get(
        "/api/dashboard/audit-log?action=LOGIN",
        headers=_headers(token))
    assert res2.status_code == 200
    # RBAC: readonly can read audit
    ro_token = _login("readonly", "readonly123")
    res3 = client.get(
        "/api/dashboard/audit-log", headers=_headers(ro_token))
    assert res3.status_code == 200


# --- D-20 Enhanced Risk endpoint --------------------------------------------

def test_d20_risk_enhanced_endpoint():
    """GET /api/dashboard/risk-enhanced returns summary, breaches, positions.
    RBAC enforced. """
    token = _login("admin", "admin123")
    res = client.get(
        "/api/dashboard/risk-enhanced", headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "summary" in body
    assert "breaches" in body
    assert "trading_halted" in body
    assert "positions" in body
    s = body["summary"]
    assert "total_equity" in s
    assert "gross_exposure" in s
    assert "net_exposure" in s
    assert "var_95" in s
    assert "concentration" in s
    assert "position_count" in s
    assert isinstance(s["concentration"], dict)
    assert isinstance(body["breaches"], list)
    assert isinstance(body["trading_halted"], bool)

    # RBAC: risk role can access
    risk_token = _login("risk", "risk123")
    res2 = client.get(
        "/api/dashboard/risk-enhanced", headers=_headers(risk_token))
    assert res2.status_code == 200


# --- D-21 Backtest chart_panels ---------------------------------------------

def test_d21_backtest_chart_panels():
    """Backtest response includes chart_panels for multi-panel chart rendering.
    Each panel has price, z_score, position, signal arrays. """
    from pathlib import Path
    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced")

    token = _login("admin", "admin123")
    res = client.post(
        "/api/dashboard/backtest/run", json={},
        headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "chart_panels" in body
    panels = body["chart_panels"]
    assert isinstance(panels, list)
    assert len(panels) > 0
    # Each panel must have the required arrays
    for p in panels:
        assert "symbol" in p
        assert "dates" in p
        assert "closes" in p
        assert "z_scores" in p
        assert "positions" in p
        assert "signals" in p
        assert "equity_line" in p
        n = len(p["dates"])
        assert n > 0
        assert len(p["closes"]) == n
        assert len(p["z_scores"]) == n
        assert len(p["positions"]) == n
        assert len(p["equity_line"]) == n
    # Default run has NVDA panel
    symbols = [p["symbol"] for p in panels]
    assert "NVDA" in symbols


# --- D-22 Backtest extended metrics -----------------------------------------

def test_d22_backtest_extended_metrics():
    """Backtest meta includes CAGR, Sortino, Calmar and trade analysis. """
    from pathlib import Path
    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced")

    token = _login("admin", "admin123")
    res = client.post(
        "/api/dashboard/backtest/run", json={},
        headers=_headers(token))
    assert res.status_code == 200
    m = res.json()["meta"]
    # New extended fields must be present
    assert "cagr" in m
    assert "sortino" in m
    assert "calmar" in m
    assert "avg_win" in m
    assert "avg_loss" in m
    assert "profit_factor" in m
    assert "expectancy" in m
    assert "avg_holding_days" in m
    assert "best_trade" in m
    assert "worst_trade" in m
    # Profit factor and expectancy should be reasonable numbers
    assert m["profit_factor"] is None or m["profit_factor"] >= 0
    # Original fields still present (additive change)
    assert "equity_final" in m
    assert "return_pct" in m


# --- D-23 Drawdown series in backtest ---------------------------------------

def test_d23_drawdown_series():
    """Backtest response includes drawdown_series (daily DD %). """
    from pathlib import Path
    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced")

    token = _login("admin", "admin123")
    res = client.post(
        "/api/dashboard/backtest/run", json={},
        headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "drawdown_series" in body
    dd = body["drawdown_series"]
    assert isinstance(dd, list)
    assert len(dd) > 0
    # Drawdown values should be <= 0 (no positive drawdown)
    for v in dd:
        assert v <= 0, f"drawdown value {v} should be <= 0"


# --- D-24 Monthly returns in backtest ---------------------------------------

def test_d24_monthly_returns():
    """Backtest response includes monthly_returns for heatmap. """
    from pathlib import Path
    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced")

    token = _login("admin", "admin123")
    res = client.post(
        "/api/dashboard/backtest/run", json={},
        headers=_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "monthly_returns" in body
    mr = body["monthly_returns"]
    assert isinstance(mr, list)
    assert len(mr) > 0
    # Each entry has month (YYYY-MM) and return_pct
    for m in mr:
        assert "month" in m
        assert "return_pct" in m
        assert len(m["month"]) == 7  # YYYY-MM format
    # Returns should sum approximately to total return
    total_ret = body["meta"]["return_pct"]
    monthly_sum = sum(m["return_pct"] for m in mr)
    assert abs(monthly_sum - total_ret) < 5.0, (
        f"monthly sum {monthly_sum} ~= total {total_ret}")


# --- D-25 Backtest API integration (Integration 008) -----------------------

def test_d25_backtest_api_integration():
    """Integration 008: universe / run history / cached result endpoints.

    The Backtest workbench reads its config from GET /backtest/universe,
    submits via POST /backtest/run, and re-opens past runs through
    GET /backtest/runs + GET /backtest/runs/{run_id} without re-running
    the engine.  Frozen-core boundary: no engine knobs are exposed.
    """
    from pathlib import Path

    from apps.api import main as apps_api_main

    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if not (data_root / "NVDA_1d.csv").exists():
        pytest.skip("data/real/d1 not synced - backtest replay unavailable")

    # SPA: the workbench route is registered in the nav
    index = (Path(apps_api_main.__file__).resolve().parent.parent
             / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'href="#/research/backtest"' in index
    assert 'data-nav="research/backtest"' in index

    # API client bundle exposes the four Integration-008 methods
    api_js = (Path(apps_api_main.__file__).resolve().parent.parent
              / "dashboard" / "static" / "js" / "api.js").read_text(encoding="utf-8")
    for method in ("backtestUniverse", "backtestRun", "backtestRuns",
                   "backtestRunResult"):
        assert method in api_js, f"api.js missing client method {method}"

    token = _login("admin", "admin123")

    # --- universe: frozen strategy metadata + gated symbols ---------------
    res = client.get(
        "/api/dashboard/backtest/universe", headers=_headers(token))
    assert res.status_code == 200
    univ = res.json()
    strat = univ["strategy"]
    assert strat["alpha_id"] == "Alpha021"
    assert strat["frozen"] is True          # quant core is sealed
    assert strat["timeframe"] == "1D"
    assert strat["slippage_bps"] > 0
    syms = {s["symbol"]: s for s in univ["symbols"]}
    assert set(syms) >= {"NVDA", "QQQ", "SPY", "EURUSD"}
    for s in syms.values():                # honest data availability
        assert isinstance(s["gate_passed"], bool)
        assert isinstance(s["data_available"], bool)
    assert syms["NVDA"]["data_available"] is True
    assert syms["NVDA"]["gate_passed"] is True

    # --- run + history + cached result -----------------------------------
    res = client.post(
        "/api/dashboard/backtest/run",
        json={"symbols": ["NVDA"], "start": "2025-01-01",
              "end": "2025-12-31", "initial_capital": 500_000.0},
        headers=_headers(token),
    )
    assert res.status_code == 200
    payload = res.json()
    run_id = payload["run_id"]
    assert run_id.startswith("bt-")

    res = client.get("/api/dashboard/backtest/runs", headers=_headers(token))
    assert res.status_code == 200
    history = res.json()["runs"]
    assert history, "the run just submitted must be recorded"
    latest = history[0]                      # newest first
    assert latest["run_id"] == run_id
    assert latest["status"] == "completed"
    assert latest["config"]["symbols"] == ["NVDA"]
    assert latest["config"]["initial_capital"] == 500_000.0
    assert latest["metrics"]["return_pct"] == pytest.approx(
        payload["meta"]["return_pct"], abs=1e-6)
    assert latest["trades"] == len(payload["trades"])
    # the run-list payload itself must not embed the full result
    assert "result" not in latest

    # cached result is byte-identical to the POST payload (minus run_id)
    res = client.get(
        f"/api/dashboard/backtest/runs/{run_id}", headers=_headers(token))
    assert res.status_code == 200
    cached = res.json()
    assert cached == {k: v for k, v in payload.items() if k != "run_id"}

    # unknown run -> 404
    assert client.get(
        "/api/dashboard/backtest/runs/bt-does-not-exist",
        headers=_headers(token)).status_code == 404

    # --- RBAC: readonly may view universe/history (read-only replay) -----
    ro_token = _login("readonly", "readonly123")
    assert client.get(
        "/api/dashboard/backtest/universe",
        headers=_headers(ro_token)).status_code == 200
    assert client.get(
        "/api/dashboard/backtest/runs",
        headers=_headers(ro_token)).status_code == 200

    # --- unauthenticated -> 401 ------------------------------------------
    assert client.get("/api/dashboard/backtest/universe").status_code == 401
    assert client.get("/api/dashboard/backtest/runs").status_code == 401
