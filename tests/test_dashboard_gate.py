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
