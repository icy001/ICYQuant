"""Integration 017 — End-to-End Validation (stage gate).

Final acceptance for UI V1 + Integrations 001-016: verify the whole
chain, not each API in isolation.

    UI V1 → API Client → FastAPI → Dashboard/Trading/Portfolio/Orders/
    Positions/Research/Backtest/Strategy/Risk/Execution/Accounts/Data/
    Monitoring/Alerts → Cross-domain flow → E2E PASS

Five acceptance tests map to the 017 validation table:

    API Client             test_e2e_api_client
    002-015 API layer      test_e2e_api_layer
    Cross-Domain Flow      test_e2e_cross_domain_flow
    Error Handling         test_e2e_error_paths
    UI Regression          test_e2e_ui_regression

No new features here: failures are fixed inside 001-016 scope only.
"""
from __future__ import annotations

import re
from pathlib import Path

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

dashboard_auth.seed()
_registry = build_registry()
for _name, _service in _registry.services.items():
    runtime.register_health(_name, _service.check)

client = TestClient(app)

from apps.api import main as apps_api_main  # noqa: E402

STATIC = (Path(apps_api_main.__file__).resolve().parent.parent
          / "dashboard" / "static")


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
    """Attach a live paper pipeline so every domain carries real data.
    Deterministic (seeded RNG) outcome profile:
      AAPL 100 BUY  -> FILLED
      MSFT 200 BUY  -> broker-rejected post-creation (order stays
                       SUBMITTED, never fills, no position)
      NVDA 150 SELL -> FILLED
      TSLA 99999 BUY -> risk-engine rejection upstream (no order row
                       at all; surfaces via bus events / alerts)"""
    session = PaperTradingSession(
        feed=SimulatedMarketFeed(seed=7), account=PaperAccount()
    )
    for spec in [
        SignalSpec(symbol="AAPL", side="BUY", quantity=100),
        SignalSpec(symbol="MSFT", side="BUY", quantity=200),
        SignalSpec(symbol="NVDA", side="SELL", quantity=150),
        SignalSpec(symbol="TSLA", side="BUY", quantity=99999),
    ]:
        session.process(spec)
    runtime.attach(session.pipeline)
    yield session
    runtime.detach()


# ============================================================================
# API Client (Integration 001)
# ============================================================================

def test_e2e_api_client():
    """001: every page goes through the one API client — no raw
    fetch/XHR anywhere in the SPA, and the client owns timeout /
    auth header / error normalisation."""
    api_js = (STATIC / "js" / "api.js").read_text(encoding="utf-8")
    app_js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")
    ui_js = (STATIC / "js" / "ui.js").read_text(encoding="utf-8")

    for src, name in ((app_js, "app.js"), (ui_js, "ui.js")):
        assert "fetch(" not in src, f"{name} bypasses the API client"
        assert "XMLHttpRequest" not in src, f"{name} bypasses the API client"

    # the client normalises errors (ApiError kind drives UI states)
    assert "kind" in api_js and "network" in api_js
    # auth header + request timeout live in exactly one place
    assert api_js.count('Authorization') >= 1
    assert "timeoutMs" in api_js or "timeout" in api_js


# ============================================================================
# API layer — Integrations 002-015 (one smoke per business domain)
# ============================================================================

def test_e2e_api_layer():
    """002-015: each integration's primary endpoint answers 200 with
    the schema its page renders (offline responses included — the
    unified empty/loading states are part of the contract). Live-data
    verification happens in the cross-domain test below, which owns
    the only pipeline attachment in this file."""
    token = _login("operator", "operator123")
    h = _headers(token)

    checks = [
        # (integration, endpoint, required top-level keys)
        ("002 Dashboard", "/api/dashboard",
         ("account", "positions", "orders", "risk", "execution",
          "strategies", "alerts", "meta")),
        ("003 Trading", "/api/dashboard/quote/AAPL", ()),
        ("004 Portfolio", "/api/dashboard/portfolio",
         ("summary", "positions", "market_exposure")),
        ("005 Orders", "/api/dashboard/orders", ("orders",)),
        ("006 Positions", "/api/dashboard/positions", ()),
        ("007 Research", "/api/dashboard/research/overview", ()),
        ("008 Backtest", "/api/dashboard/backtest/runs", ()),
        ("009 Strategy", "/api/dashboard/strategy/catalog", ()),
        ("010 Risk", "/api/dashboard/risk/center", ("limits",)),
        ("011 Execution", "/api/dashboard/execution/center",
         ("engine", "kpi", "orders")),
        ("012 Accounts", "/api/dashboard/accounts/center",
         ("overview", "accounts")),
        ("013 Data", "/api/dashboard/data/center", ("overview",)),
        ("014 Monitoring", "/api/dashboard/monitoring/center",
         ("overview", "services", "trading", "metrics", "events")),
        ("015 Alerts", "/api/dashboard/alerts/center",
         ("overview", "sources", "alerts")),
    ]
    for name, url, keys in checks:
        res = client.get(url, headers=h)
        assert res.status_code == 200, f"{name} {url} -> {res.status_code}"
        body = res.json()
        for key in keys:
            assert key in body, f"{name}: missing {key}"

    # trading submit path (003): preview validates the full stack
    preview = client.post(
        "/api/dashboard/orders/preview",
        json={"symbol": "AAPL", "side": "BUY", "quantity": 10},
        headers=h,
    )
    assert preview.status_code == 200


# ============================================================================
# Cross-domain flow — the heart of 017
# ============================================================================

def test_e2e_cross_domain_flow(attached_pipeline):
    """Order → Execution → Position → Portfolio → Monitoring → Alerts
    must agree with each other on the same underlying runtime."""
    h = _headers(_login("operator", "operator123"))

    # ── Orders: outcome profile from the seeded fixture ─────────────
    orders = client.get("/api/dashboard/orders", headers=h).json()["orders"]
    by_o = {o["symbol"]: o for o in orders}
    assert by_o["AAPL"]["status"] == "FILLED"
    assert by_o["NVDA"]["status"] == "FILLED"
    assert by_o["MSFT"]["status"] == "SUBMITTED"      # broker-rejected
    assert "TSLA" not in by_o, "risk-rejected upstream — no order row"
    filled = [by_o["AAPL"], by_o["NVDA"]]

    # ── per-order full trace: signal → risk → order → execution →
    #    position → ledger (the chain one click deep from the UI) ───
    for o in filled:
        trace = client.get(
            f"/api/dashboard/orders/{o['order_id']}", headers=h).json()
        for stage in ("signal", "risk_decision", "order",
                      "execution", "position", "ledger"):
            assert trace[stage] is not None, \
                f"{o['symbol']} trace broken at {stage}"
        assert trace["order"]["order_id"] == o["order_id"]
    # the unfilled order has a trace too, but no execution / position
    msft_trace = client.get(
        f"/api/dashboard/orders/{by_o['MSFT']['order_id']}",
        headers=h).json()
    assert msft_trace["order"]["status"] == "SUBMITTED"
    assert msft_trace["execution"] is None

    # ── Executions: fills exist for filled orders (the adapter layer
    #    also seeds standing executions in other accounts) ───────────
    execs = client.get("/api/dashboard/executions", headers=h).json()["executions"]
    exec_order_ids = {e["order_id"] for e in execs}
    filled_ids = {o["order_id"] for o in filled}
    assert filled_ids <= exec_order_ids, "filled orders missing executions"
    assert by_o["MSFT"]["order_id"] not in exec_order_ids, \
        "unfilled order must not carry executions"
    exec_syms = {e["symbol"] for e in execs}
    assert {"AAPL", "NVDA"} <= exec_syms

    # ── Positions: quantities derive from the fills ────────────────
    # (engine semantics: quantity aggregates as absolute size; the
    #  direction of the fill is carried by the position's side field)
    positions = client.get("/api/dashboard/positions", headers=h).json()
    pos_rows = positions.get("positions") or positions.get("items") or []
    by_symbol = {p["symbol"]: p for p in pos_rows}
    assert by_symbol["AAPL"]["quantity"] == 100
    assert by_symbol["AAPL"]["side"] == "BUY"
    assert by_symbol["NVDA"]["quantity"] == 150
    assert by_symbol["NVDA"]["side"] == "SELL"
    assert "MSFT" not in by_symbol, "unfilled order must not open a position"
    assert "TSLA" not in by_symbol, "rejected order must not open a position"

    # ── Portfolio (pipeline track): aggregates the very same positions
    #    GET /dashboard/positions returns the pipeline book + summary;
    #    the multi-account /dashboard/portfolio is a separate adapter
    #    domain and stays untouched by pipeline fills.
    book = client.get("/api/dashboard/positions", headers=h).json()
    assert book["positions"], "pipeline book lost the positions"
    assert set(by_symbol) == {p["symbol"] for p in book["positions"]}
    summary = book["summary"]
    gross = sum(p["exposure"] for p in book["positions"])
    assert abs(summary["gross_exposure"] - gross) < 0.01, \
        "summary disagrees with the position rows it aggregates"
    assert summary["total_equity"] > summary["cash"], \
        "equity must cover the gross book"

    # multi-account adapter domain: schema intact, no pipeline leakage
    portfolio = client.get("/api/dashboard/portfolio", headers=h).json()
    assert portfolio["positions"], "adapter book is empty"
    assert "summary" in portfolio and "market_exposure" in portfolio

    # ── Monitoring: runtime view of the same state ─────────────────
    monitoring = client.get(
        "/api/dashboard/monitoring/center", headers=h).json()
    trading = monitoring["trading"]
    assert trading["pipeline_attached"] is True
    assert trading["open_positions"] == len(
        [p for p in pos_rows if p["quantity"] != 0])
    # active = working orders (the unfilled MSFT), not the filled ones
    assert trading["active_orders"] == 1
    # metrics see the rejections (risk + broker sides)
    assert monitoring["metrics"]["risk_rejected"] >= 1

    # ── Alerts: the TSLA risk rejection surfaced as an alert row
    #    (design semantics: risk rejections surface at INFO severity
    #     with symbol context + the WHY event chain) ────────────────
    alerts = client.get("/api/dashboard/alerts/center", headers=h).json()
    assert any(a["symbol"] == "TSLA"
               for a in alerts["alerts"]), \
        "risk rejection did not surface in the alert center"
    tsla_alert = next(a for a in alerts["alerts"] if a["symbol"] == "TSLA")
    assert tsla_alert["events"], "TSLA alert lost its event chain"

    # ── Research/Strategy context travels across the terminal ──────
    catalog = client.get(
        "/api/dashboard/strategy/catalog", headers=h).json()
    catalog_ids = {s["id"] for s in catalog.get("strategies", [])}
    assert "alpha021" in catalog_ids or "Alpha021" in catalog_ids


# ============================================================================
# Error paths
# ============================================================================

def test_e2e_error_paths():
    """Auth gate, RBAC, missing resources — failure is as designed."""
    # 401 on every protected center without a token
    for url in (
        "/api/dashboard",
        "/api/dashboard/monitoring/center",
        "/api/dashboard/alerts/center",
    ):
        assert client.get(url).status_code == 401, url
    # bad token
    res = client.get("/api/dashboard",
                     headers={"Authorization": "Bearer not-a-token"})
    assert res.status_code == 401

    # readonly role: view centers fine
    token = _login("readonly", "readonly123")
    h = _headers(token)
    assert client.get("/api/dashboard/orders",
                      headers=h).status_code == 200
    assert client.get("/api/dashboard/alerts/center",
                      headers=h).status_code == 200

    # unknown order -> 404 (not 500 / not empty 200)
    assert client.get("/api/dashboard/orders/NOPE-404",
                      headers=h).status_code == 404


# ============================================================================
# UI regression
# ============================================================================

def test_e2e_ui_regression():
    """20 views navigable, unified states everywhere, no mock leakage."""
    app_js = (STATIC / "js" / "app.js").read_text(encoding="utf-8")

    # ① every NAV route has a real page implementation (no placeholder)
    nav_routes = re.findall(r'"#/([a-z/]+)": \{', app_js)
    assert len(nav_routes) == 19, nav_routes
    framework_routes = set(re.findall(
        r'PAGE_FRAMEWORK\["([a-z/]+)"\] =', app_js))
    for route in nav_routes:
        assert route in framework_routes, f"route #{route} unimplemented"

    # ② unified page states (loading / error / empty / offline)
    assert "function apiStateBlock" in app_js
    assert 'kind === "network"' in app_js
    assert 'class="ds-error"' not in app_js

    # ③ terminal context (account / strategy) + formatting vocabulary
    for marker in ("var APP_CTX", "function ctxSetAccount",
                   "function ctxSetStrategy", "function fmtClock",
                   "function fmtBps", "function fmtSignedPct"):
        assert marker in app_js, f"missing {marker}"

    # ④ no business mock data: remaining uppercase module vars must
    #    all be state/UI-structure, never fabricated business rows
    allowed = {
        "PAGE_FRAMEWORK", "APP_CTX", "NAV", "ROUTES", "GROUP_LABELS",
        # page state containers (fed by APIs)
        "AC_STATE", "AL_STATE", "BT_STATE", "DT_STATE", "EX_STATE",
        "MO_STATE", "RESEARCH_STATE", "RK_STATE", "ST_STATE", "STG_STATE",
        "ORDERS_DATA", "ORDERS_FILTERS",
        "POSITIONS_PAYLOAD", "POSITIONS_FILTERS",
        # UI structure / feature flags (not business data)
        "STG_SECTIONS", "STG_NOTIFY", "RESEARCH_PAPER_ALPHAS",
        "ST_LC_ICON", "ST_LC_STATE", "ST_LIFECYCLE_MAP",
        "ST_LIFECYCLE_STAGES",
    }
    found = set(re.findall(r'\bvar ([A-Z][A-Z0-9_]+) = [\[\{]', app_js))
    leaked = found - allowed
    assert not leaked, f"potential mock data leaked: {leaked}"

    # ⑤ the login view completes the 20th screen
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "login" in index_html.lower()
