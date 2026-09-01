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


# --- D-26 Strategy API (Integration 009) -------------------------------------

def test_d26_strategy_api_integration():
    """Integration 009: catalog + detail endpoints on real data sources.

    The Strategy page reads the research funnel (run factor-real-d1),
    the frozen Alpha021 paper replay and the recorded backtest history
    through GET /dashboard/strategy/catalog and /catalog/{id}.  Frozen-core
    boundary: read-only mapping — validation-passed -> CANDIDATE,
    OOS-passed -> VALIDATED, frozen replay -> PAPER, and alphas below
    the validation cut stay off the catalog entirely.
    """
    from pathlib import Path

    from apps.api import main as apps_api_main

    static = (Path(apps_api_main.__file__).resolve().parent.parent
               / "dashboard" / "static")

    # SPA: the strategies route is registered in the nav
    index = (static / "index.html").read_text(encoding="utf-8")
    assert 'href="#/research/strategies"' in index

    # the mock STRATEGIES array is gone; the page is API-driven
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    assert "var STRATEGIES = [" not in app_js
    assert "strategyCatalog" in app_js and "strategyDetail" in app_js
    api_js = (static / "js" / "api.js").read_text(encoding="utf-8")
    for method in ("strategyCatalog", "strategyDetail"):
        assert method in api_js, f"api.js missing client method {method}"

    token = _login("admin", "admin123")

    # --- catalog: the research funnel mapped onto the lifecycle ----------
    res = client.get("/api/dashboard/strategy/catalog",
                     headers=_headers(token))
    assert res.status_code == 200
    catalog = res.json()
    assert catalog["source"]["research_run"] == "factor-real-d1"
    assert isinstance(catalog["source"]["paper_replay_available"], bool)
    strats = {s["id"]: s for s in catalog["strategies"]}

    # funnel honesty: only the three validation-passing alphas are listed
    assert set(strats) == {"alpha021", "alpha035", "alpha053"}
    # Alpha021 is the frozen alpha carrying the paper replay -> PAPER
    assert strats["alpha021"]["status"] == "PAPER"
    assert strats["alpha021"]["metrics_source"] == "paper-replay"
    assert strats["alpha021"]["universe"] == ["NVDA", "QQQ", "SPY"]
    assert strats["alpha021"]["type"] == "Factor"
    assert strats["alpha021"]["timeframe"] == "1D"
    # research-run strategies never claim paper metrics
    assert strats["alpha035"]["status"] == "VALIDATED"
    assert strats["alpha035"]["metrics_source"] == "research-run"
    assert strats["alpha053"]["status"] == "CANDIDATE"
    assert strats["alpha053"]["metrics_source"] == "research-run"
    # counts are derived from the same list (no mock totals)
    counts = catalog["counts"]
    assert counts["total"] == len(catalog["strategies"]) == 3
    assert counts["paper"] == 1
    assert counts["active"] == 1          # PAPER only; no SHADOW/LIVE yet
    assert counts["shadow"] == 0 and counts["live"] == 0

    # --- detail (frozen alpha): research + paper replay + history ---------
    res = client.get("/api/dashboard/strategy/catalog/alpha021",
                     headers=_headers(token))
    assert res.status_code == 200
    d = res.json()
    assert d["id"] == "alpha021" and d["status"] == "PAPER"
    research = d["research"]
    assert research["run_id"] == "factor-real-d1"
    assert research["validation_passed"] is True
    assert research["oos_passed"] is True
    assert research["robustness_passed"] is True
    assert research["family"] == "D1"
    assert research["is_representative"] is True
    assert research["reject_reasons"]      # per-asset rejects survive
    paper = d["paper"]
    assert paper is not None
    assert paper["trades"]                 # deterministic replay has trades
    assert isinstance(paper["positions"], list)
    assert paper["execution"]["venue"].startswith("Paper")
    # headline metrics are fractions consistent with the paper replay
    from apps.runtime.factor_gate import build_paper_data
    meta = build_paper_data()["meta"]
    assert d["ret"] == pytest.approx(meta["return_pct"] / 100.0)
    assert d["sharpe"] == pytest.approx(meta["sharpe"])
    assert d["max_dd"] == pytest.approx(meta["maxdd_pct"] / 100.0)
    assert d["history"] and all(
        {"date", "event", "detail"} <= set(e) for e in d["history"])

    # --- detail (research-run alpha): honest empty paper state -----------
    res = client.get("/api/dashboard/strategy/catalog/alpha035",
                     headers=_headers(token))
    assert res.status_code == 200
    d35 = res.json()
    assert d35["paper"] is None
    assert d35["research"]["oos_passed"] is True
    assert d35["research"]["robustness_passed"] is False
    assert d35["research"]["family"] is None
    assert d35["status"] == "VALIDATED"

    # --- backtest history linkage (Integration 008 -> 009) ----------------
    data_root = (
        Path(__file__).resolve().parent.parent / "data" / "real" / "d1"
    )
    if (data_root / "NVDA_1d.csv").exists():
        res = client.post(
            "/api/dashboard/backtest/run",
            json={"symbols": ["NVDA"], "start": "2025-01-01",
                  "end": "2025-12-31", "initial_capital": 500_000.0},
            headers=_headers(token),
        )
        assert res.status_code == 200
        res = client.get("/api/dashboard/strategy/catalog/alpha021",
                         headers=_headers(token))
        detail = res.json()
        runs = detail["backtest_runs"]
        assert runs, "the submitted run must be linked to the strategy"
        assert runs[0]["status"] == "completed"
        assert runs[0]["config"]["strategy"] == "Alpha021"
        # the run also shows up in the lifecycle history
        assert any(e["event"] == "Backtest completed"
                   for e in detail["history"])

    # --- error paths ------------------------------------------------------
    # unknown strategy -> 404
    assert client.get(
        "/api/dashboard/strategy/catalog/nope-404",
        headers=_headers(token)).status_code == 404
    # a below-validation alpha is intentionally not part of the catalog
    assert client.get(
        "/api/dashboard/strategy/catalog/alpha047",
        headers=_headers(token)).status_code == 404

    # --- RBAC: readonly may view the catalog (read-only integration) -----
    ro_token = _login("readonly", "readonly123")
    assert client.get(
        "/api/dashboard/strategy/catalog",
        headers=_headers(ro_token)).status_code == 200
    assert client.get(
        "/api/dashboard/strategy/catalog/alpha021",
        headers=_headers(ro_token)).status_code == 200

    # --- unauthenticated -> 401 ------------------------------------------
    assert client.get(
        "/api/dashboard/strategy/catalog").status_code == 401
    assert client.get(
        "/api/dashboard/strategy/catalog/alpha021").status_code == 401
    assert client.get("/api/dashboard/backtest/runs").status_code == 401


# --- D-27 Risk API (Integration 010) ----------------------------------------

def test_d27_risk_api_integration(attached_pipeline):
    """Integration 010: Risk Control Center reads the live pipeline.

    GET /dashboard/risk/center aggregates positions / orders / risk
    decisions / alerts + engine limits + UI-configured loss limits for
    the Risk and Exposure pages.  Frozen-core boundary: read-only —
    every number is measured or configured upstream, nothing invented.
    """
    from pathlib import Path

    from apps.api import main as apps_api_main

    static = (Path(apps_api_main.__file__).resolve().parent.parent
               / "dashboard" / "static")

    # SPA: the risk routes are registered in the nav
    index = (static / "index.html").read_text(encoding="utf-8")
    assert 'href="#/risk"' in index
    assert 'href="#/risk/exposure"' in index

    # the mock RK_* arrays are gone; the page is API-driven
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    for gone in ("RK_KPI =", "RK_OVERVIEW =", "RK_ASSET_EXPOSURE =",
                 "RK_LIMITS =", "RK_EVENTS =", "RK_SECTOR_EXPOSURE ="):
        assert gone not in app_js, f"mock risk data still present: {gone}"
    assert "riskCenter" in app_js and "RK_STATE" in app_js
    api_js = (static / "js" / "api.js").read_text(encoding="utf-8")
    assert "riskCenter" in api_js, "api.js missing client method riskCenter"

    token = _login("admin", "admin123")

    # --- live snapshot: exposure derived from real positions -------------
    res = client.get("/api/dashboard/risk/center", headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # engine: pipeline attached + risk-engine service UP
    assert d["engine"]["status"] == "ONLINE"
    assert d["engine"]["attached"] is True
    assert d["engine"]["last_update"]

    # cross-check exposure against the positions endpoint itself
    pos = client.get("/api/dashboard/positions",
                     headers=_headers(token)).json()["positions"]
    long_exp = sum(p["exposure"] for p in pos if p["side"] == "BUY")
    short_exp = sum(p["exposure"] for p in pos if p["side"] == "SELL")
    e = d["exposure"]
    assert e["long"] == pytest.approx(long_exp)
    assert e["short"] == pytest.approx(short_exp)
    assert e["gross"] == pytest.approx(long_exp + short_exp)
    assert e["net"] == pytest.approx(long_exp - short_exp)
    assert e["position_count"] == len(pos) == 2   # TSLA was rejected
    assert {a["symbol"] for a in e["by_asset"]} == {"AAPL", "NVDA"}
    by_asset = {a["symbol"]: a for a in e["by_asset"]}
    assert by_asset["AAPL"]["side"] == "Long"
    assert by_asset["NVDA"]["side"] == "Short"
    # gross weights sum to 1 (two decimal tolerance for rounding)
    assert sum(a["weight"] for a in e["by_asset"]) == pytest.approx(1.0, abs=1e-3)
    # every strategy exposure row comes from position.account_id
    strat = {s["label"]: s for s in e["by_strategy"]}
    assert strat["SCENARIO"]["weight"] == pytest.approx(1.0)
    # by-side breakdown mirrors the headline numbers
    by_side = {s["label"]: s for s in e["by_side"]}
    assert by_side["Long"]["exposure"] == pytest.approx(long_exp)
    assert by_side["Short"]["exposure"] == pytest.approx(short_exp)

    # concentration: HHI of the same gross weights
    assert d["concentration"]["hhi"] > 0
    assert d["concentration"]["holdings"][0]["symbol"] in {"AAPL", "NVDA"}

    # --- KPI table: measured values, not mock constants -------------------
    kpi = {k["metric"]: k for k in d["kpi"]}
    assert kpi["Position Quantity"]["value"] == pytest.approx(250.0)  # 100+150
    assert kpi["Open Positions"]["value"] == 2
    assert kpi["Net Exposure"]["value"] == pytest.approx(
        (long_exp - short_exp) / e["equity"], abs=1e-5)
    assert "Risk Decisions" in kpi
    for row in d["kpi"]:
        assert row["status"] in {"NORMAL", "WATCH", "BREACH"}

    # --- limits: engine constants + UI-configured loss limits -------------
    from apps.dashboard import runtime as rt

    cfg = client.get("/api/dashboard/config",
                     headers=_headers(token)).json()
    limits = {l["name"]: l for l in d["limits"]}
    assert limits["Position Limit"]["limit"] == rt.RISK_POSITION_LIMIT
    assert limits["Position Limit"]["current"] == pytest.approx(250.0)
    assert limits["Order Rate Limit"]["current"] == 3   # AAPL/MSFT/NVDA
    assert limits["Order Rate Limit"]["limit"] == rt.RISK_ORDER_LIMIT
    assert limits["Daily Loss Limit"]["limit"] == pytest.approx(
        e["equity"] * cfg["risk"]["max_daily_loss_pct"] / 100.0)
    assert limits["Drawdown Limit"]["limit"] == pytest.approx(
        cfg["risk"]["max_drawdown_pct"])
    for row in d["limits"]:
        assert row["status"] in {"NORMAL", "WATCH", "BREACH"}

    # --- decisions + event log: the TSLA reject is visible ----------------
    assert d["decisions"] == {"total": 4, "approved": 3, "rejected": 1}
    titles = " | ".join(ev["title"] for ev in d["events"])
    assert "Order rejected: BUY TSLA 99999" in titles
    assert any(ev["severity"] in {"INFO", "WARNING", "BREACH"}
               for ev in d["events"])


def test_d27_risk_api_offline_and_access():
    """Integration 010: offline snapshot, RBAC and the auth gate."""
    # defensive: no pipeline may stay attached from earlier tests
    runtime.detach()

    token = _login("readonly", "readonly123")
    res = client.get("/api/dashboard/risk/center", headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # offline: engine OFFLINE, zeroed exposure, honest empty states
    assert d["engine"]["status"] == "OFFLINE"
    assert d["engine"]["attached"] is False
    assert d["exposure"]["gross"] == 0
    assert d["exposure"]["position_count"] == 0
    assert d["exposure"]["by_asset"] == []
    assert d["concentration"]["hhi"] == 0
    assert any("No trading pipeline attached" in ev["title"]
               for ev in d["events"])

    # unauthenticated -> 401
    assert client.get("/api/dashboard/risk/center").status_code == 401


# --- D-28 Execution API (Integration 011) ------------------------------------


def test_d28_execution_api_integration(attached_pipeline):
    """Integration 011: Execution Control Center reads the live pipeline."""
    from pathlib import Path
    from apps.api import main as apps_api_main

    static = (Path(apps_api_main.__file__).resolve().parent.parent
               / "dashboard" / "static")

    # SPA: mock EX_* arrays are gone; page is API-driven
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    for gone in ("EX_ENGINES =", "EX_KPI =", "EX_QUALITY =",
                 "EX_FLOW =", "EX_TIMELINE =", "EX_VENUES =",
                 "EX_LAST_UPDATE ="):
        assert gone not in app_js, f"mock execution data still present: {gone}"
    assert "EX_STATE" in app_js and "executionCenter" in app_js
    api_js = (static / "js" / "api.js").read_text(encoding="utf-8")
    assert "executionCenter" in api_js, "api.js missing executionCenter"

    token = _login("admin", "admin123")

    # --- live snapshot ----------------------------------------------------
    res = client.get("/api/dashboard/execution/center",
                     headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # engine: pipeline attached + services UP
    assert d["engine"]["status"] == "ONLINE"
    assert d["engine"]["attached"] is True
    assert d["engine"]["last_update"]
    assert len(d["engine"]["engines"]) == 3

    # cross-check KPI against the orders endpoint
    orders = client.get("/api/dashboard/orders",
                        headers=_headers(token)).json()["orders"]
    total = len(orders)
    filled = sum(1 for o in orders if o["status"] == "FILLED")
    rejected = sum(1 for o in orders if o["status"] == "REJECTED")
    k = d["kpi"]
    assert k["orders"] == total
    assert k["filled"] == filled
    assert k["rejected"] == rejected
    assert k["fill_rate"] == pytest.approx(
        filled / total if total else 0, abs=1e-4)
    assert k["reject_rate"] == pytest.approx(
        rejected / total if total else 0, abs=1e-4)

    # every flow cell count is non-negative and sums to total
    assert sum(f["count"] for f in d["flow"]) == total
    for f in d["flow"]:
        assert f["count"] >= 0
        assert f["cls"] in ("pending", "working", "partial", "filled",
                            "rejected", "cancelled")

    # quality bars: labels + bounded fills
    labels = {q["label"] for q in d["quality"]}
    assert {"Fill Rate", "Reject Rate", "Error Rate"}.issubset(labels)
    for q in d["quality"]:
        assert 0 <= q["fill"] <= 100
        assert q["cls"] in ("good", "neutral", "bad")

    # orders table: each row maps to a real order
    order_ids_api = {o["order_id"] for o in orders}
    order_rows = d["orders"]
    assert len(order_rows) == total
    for row in order_rows:
        assert row["order_id"] in order_ids_api
        assert row["symbol"]
        assert row["side"] in ("BUY", "SELL")
        assert row["status"]
        # slippage / latency only meaningful on filled orders
        if row["status"] == "FILLED":
            if row["slippage_bps"] is not None:
                assert isinstance(row["slippage_bps"], (int, float))
            if row["latency_ms"] is not None:
                assert row["latency_ms"] >= 0
        elif row["status"] == "REJECTED":
            # rejected orders have no fill
            assert not row["fill_price"] or row["fill_price"] == 0

    # venues: at least one venue derived from real orders
    assert len(d["venues"]) >= 1
    venue_filled = sum(v["execs"] for v in d["venues"])
    assert venue_filled <= filled


def test_d28_execution_api_offline_and_access():
    """Integration 011: offline snapshot, RBAC and the auth gate."""
    runtime.detach()

    token = _login("readonly", "readonly123")
    res = client.get("/api/dashboard/execution/center",
                     headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # offline: engine OFFLINE, zeroed KPI, empty orders
    assert d["engine"]["status"] == "OFFLINE"
    assert d["engine"]["attached"] is False
    assert d["kpi"]["orders"] == 0
    assert d["kpi"]["filled"] == 0
    assert d["kpi"]["fill_rate"] == 0
    assert d["orders"] == []

    # unauthenticated -> 401
    assert client.get("/api/dashboard/execution/center").status_code == 401


# --- D-29 Accounts API (Integration 012) -------------------------------------


def test_d29_accounts_api_integration():
    """Integration 012: Accounts Control Center reads the live adapter layer."""
    from pathlib import Path
    from apps.api import main as apps_api_main

    static = (Path(apps_api_main.__file__).resolve().parent.parent
               / "dashboard" / "static")

    # SPA: mock ACCOUNTS / AC_OVERVIEW arrays are gone; page is API-driven
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    for gone in ("var ACCOUNTS = [", "AC_OVERVIEW = {"):
        assert gone not in app_js, f"mock accounts data still present: {gone}"
    assert "AC_STATE" in app_js and "accountsCenter" in app_js
    api_js = (static / "js" / "api.js").read_text(encoding="utf-8")
    assert "accountsCenter" in api_js, "api.js missing accountsCenter"

    token = _login("trader", "trader123")

    # --- live snapshot ----------------------------------------------------
    res = client.get("/api/dashboard/accounts/center", headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # status bar
    assert d["status"]["total"] == 4
    assert d["status"]["connected"] >= 1
    assert d["status"]["total"] == sum(
        d["status"][k] for k in ("connected", "degraded", "offline"))
    assert d["status"]["last_update"]

    # cross-check overview against the accounts list (USD-normalised)
    accounts = d["accounts"]
    assert len(accounts) == 4
    fx_cny = 0.139
    expected_equity = round(
        sum(a["equity"] * (fx_cny if a["currency"] == "CNY" else 1.0)
            for a in accounts), 2)
    assert d["overview"]["total_equity"] == pytest.approx(
        expected_equity, abs=1e-2)
    assert d["overview"]["currency"] == "USD"

    # every account carries the unified Account Domain fields + permissions
    for a in accounts:
        for key in ("account_id", "name", "broker_name", "market",
                    "market_label", "currency", "type", "trading_mode",
                    "connection", "status", "equity", "cash", "buying_power",
                    "margin", "daily_pnl", "total_pnl", "drawdown",
                    "positions", "orders", "executions", "capabilities",
                    "permissions"):
            assert key in a, f"account row missing {key}"
        assert a["trading_mode"] == "PAPER"
        assert a["connection"] in ("CONNECTED", "CONNECTING",
                                   "DISCONNECTED", "ERROR")
        perms = a["permissions"]
        for pk in ("market_data", "trading", "cancel_order", "short_selling"):
            assert isinstance(perms[pk], bool)

    # cross-check KPI against the global portfolio endpoint (same source)
    portfolio = client.get("/api/dashboard/portfolio",
                           headers=_headers(token)).json()
    assert d["overview"]["gross_exposure"] == pytest.approx(
        portfolio["summary"]["gross_exposure_usd"], abs=1e-2)

    # markets breakdown: each market maps to real accounts
    market_labels = {a["market_label"] for a in accounts}
    assert {m["market_label"] for m in d["markets"]} == market_labels
    for m in d["markets"]:
        assert m["accounts"] >= 1
        assert m["connected"] <= m["accounts"]

    # account detail via the existing endpoint stays consistent
    first_id = accounts[0]["account_id"]
    detail = client.get("/api/dashboard/accounts/" + first_id,
                        headers=_headers(token)).json()
    assert detail["account_id"] == first_id
    assert detail["equity"] == accounts[0]["equity"]
    assert detail["connection"] == accounts[0]["connection"]


def test_d29_accounts_api_access():
    """Integration 012: RBAC and the auth gate."""
    # unauthenticated -> 401
    assert client.get("/api/dashboard/accounts/center").status_code == 401

    # readonly can read the accounts center (view-only role)
    token = _login("readonly", "readonly123")
    res = client.get("/api/dashboard/accounts/center", headers=_headers(token))
    assert res.status_code == 200
    assert res.json()["status"]["total"] == 4


# ============================================================================
# Integration 013 — Data API
# ============================================================================

def test_d30_data_api_integration():
    """Integration 013: Data Control Center reads the on-disk data layer
    (data/real/d1 + data/processed/manifests + data/lakehouse/_state.json)."""
    from pathlib import Path
    from apps.api import main as apps_api_main

    static = (Path(apps_api_main.__file__).resolve().parent.parent
               / "dashboard" / "static")

    # SPA: mock DT_OVERVIEW / DT_MARKETS / DT_DATASETS / DT_QUALITY /
    # DT_PIPELINE arrays are gone; the page is API-driven via DT_STATE.
    app_js = (static / "js" / "app.js").read_text(encoding="utf-8")
    for gone in ("var DT_OVERVIEW = {", "var DT_MARKETS = [",
                 "var DT_DATASETS = [", "var DT_QUALITY = [",
                 "var DT_PIPELINE = ["):
        assert gone not in app_js, f"mock data still present: {gone}"
    assert "DT_STATE" in app_js and "dataCenter" in app_js
    api_js = (static / "js" / "api.js").read_text(encoding="utf-8")
    assert "dataCenter" in api_js, "api.js missing dataCenter"

    token = _login("trader", "trader123")

    # --- live snapshot ----------------------------------------------------
    res = client.get("/api/dashboard/data/center", headers=_headers(token))
    assert res.status_code == 200
    d = res.json()

    # overview KPI: reads the real on-disk manifests
    ov = d["overview"]
    assert ov["datasets"] >= 1
    assert ov["symbols"] >= 1
    assert ov["records"] >= 1
    assert ov["data_service"] in ("HEALTHY", "EMPTY", "DEGRADED")
    assert ov["last_update"]  # fetched_at present from real manifest

    # datasets: every row carries the unified schema
    datasets = d["datasets"]
    assert datasets, "datasets list empty"
    required_ds = ("id", "name", "type", "tf", "assets", "bars",
                   "status", "date_range", "missing", "duplicates",
                   "last_update", "source")
    for ds in datasets:
        for key in required_ds:
            assert key in ds, f"dataset row missing {key}"
        assert ds["status"] in ("READY", "STALE", "DEGRADED")
        assert ds["tf"] in ("D1", "1H", "15m")

    # real-d1 dataset is present and aggregated from the real manifest
    real_ds = next((x for x in datasets if x["id"] == "real-d1"), None)
    assert real_ds is not None, "Real Daily dataset missing"
    assert real_ds["type"] == "Real"
    assert real_ds["assets"] == 3  # NVDA, QQQ, SPY
    assert real_ds["bars"] == 665 * 3  # 665 rows each per manifest

    # symbols: every symbol has asset_class / exchange / market / tf / range
    symbols = d["symbols"]
    assert symbols, "symbols list empty"
    sym_ids = {s["symbol"] for s in symbols}
    # the 9-asset research universe must all appear
    expected = {"NVDA", "QQQ", "SPY", "000688.SH", "HSTECH",
                "EURUSD", "XAUUSD", "AU", "AG"}
    assert expected.issubset(sym_ids), f"missing symbols: {expected - sym_ids}"
    for s in symbols:
        for key in ("symbol", "asset_class", "exchange", "market",
                    "first_date", "last_date", "bars", "timeframes",
                    "status"):
            assert key in s, f"symbol row missing {key}"
        assert s["status"] in ("READY", "STALE", "DEGRADED")

    # NVDA / QQQ / SPY are flagged real (sourced from data/real/d1).
    # Date range is the union of processed (2023-01-02 → 2025-12-31)
    # and real (2024-01-02 → 2026-08-26) manifests.
    for sym in ("NVDA", "QQQ", "SPY"):
        row = next(s for s in symbols if s["symbol"] == sym)
        assert row["real"] is True
        assert row["bars"] >= 665
        assert row["first_date"] == "2023-01-02"  # processed manifest start
        assert row["last_date"] == "2026-08-26"   # real manifest end

    # quality: aggregates over the processed manifests' quality_gate
    q = d["quality"]
    assert q["datasets_total"] == 27  # 9 symbols × 3 timeframes
    assert q["datasets_pass"] >= 1
    assert q["datasets_pass"] + q["datasets_fail"] == q["datasets_total"]
    assert q["checks"]
    for c in q["checks"]:
        assert c["pass"] <= c["total"]

    # pipeline: stages derived from the on-disk state
    p = d["pipeline"]
    assert p["status"] in ("HEALTHY", "EMPTY", "DEGRADED")
    assert len(p["stages"]) == 5
    stage_labels = [s["label"] for s in p["stages"]]
    assert stage_labels == ["Fetch", "Normalize", "Validate", "Store", "Ready"]
    # fetch + normalize + validate must be 'done' (real + processed exist)
    assert p["stages"][0]["state"] == "done"  # Fetch
    assert p["stages"][1]["state"] == "done"  # Normalize
    assert p["stages"][2]["state"] == "done"  # Validate

    # markets: grouped by market label, every market has at least one symbol
    markets = d["markets"]
    assert markets
    market_labels = {s["market"] for s in symbols}
    assert {m["market"] for m in markets} == market_labels
    for m in markets:
        assert m["symbols"] >= 1
        assert m["status"] in ("healthy", "degraded", "down")

    # real_daily mirrors the on-disk manifest
    rd = d["real_daily"]
    assert rd["fetched_at"]
    assert rd["range"] == ["2024-01-01", "2026-08-27"]
    assert len(rd["rows"]) == 3
    for r in rd["rows"]:
        assert r["status"] == "READY"
        assert r["bars"] == 665


def test_d30_data_api_access():
    """Integration 013: RBAC and the auth gate."""
    # unauthenticated -> 401
    assert client.get("/api/dashboard/data/center").status_code == 401

    # readonly can read the data center (view-only role)
    token = _login("readonly", "readonly123")
    res = client.get("/api/dashboard/data/center", headers=_headers(token))
    assert res.status_code == 200
    assert res.json()["overview"]["datasets"] >= 1
