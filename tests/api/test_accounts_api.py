"""Commit 015 §15 / §16 / §17 — the Account / Position API contract.

§17 is the point of this suite: the Dashboard talks to the API and to
nothing else.  So the tests drive the *real* gateway
(``TestClient(apps.api.main.app)``) with a *real* service chain behind it
(the §1 assembly, a simulated vendor and the Position Ledger), and then
assert the three promises the module docstring makes:

* reads are side-effect free — a ``GET`` never opens a broker channel;
* quality is never hidden — ``status`` / ``reconciliation`` / ``null``
  prices travel next to the numbers (§3 / §10 / §18);
* no snapshot yet is honest — a 404, not a fabricated empty account.

The shared service is swapped for a per-test harness, so these tests are
deterministic and never leak state into the running singleton.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.api.routers import accounts as accounts_router
from tests.account.helpers import (
    ACCOUNT_ID,
    EXPECTED_MARKET_VALUE,
    EXPECTED_POSITION_VALUES,
    EXPECTED_TOTAL_ASSET,
    LATENCY_MS,
    Harness,
)

BASE = "/api/accounts"
UNKNOWN = "NOSUCHACCOUNT"


def login(gateway, username: str, password: str) -> dict:
    res = gateway.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture()
def make_api(gateway, monkeypatch):
    """Wire the real app to a per-test §1 chain.

    ``_service`` is the module-level seam the routes resolve at call time,
    so swapping it keeps the running singleton (and every other suite)
    untouched.
    """

    def build(role: str = "operator", **harness_kwargs) -> Harness:
        harness = Harness(**harness_kwargs)
        monkeypatch.setattr(accounts_router, "_service", lambda: harness.service)
        harness.gateway = gateway
        harness.headers = login(
            gateway,
            *(
                ("readonly", "readonly123")
                if role == "readonly"
                else ("operator", "operator123")
            ),
        )
        return harness

    return build


@pytest.fixture()
def api(make_api) -> Harness:
    return make_api()


@pytest.fixture()
def as_reader(make_api) -> Harness:
    return make_api(role="readonly")


def get(api, path, **kwargs):
    return api.gateway.get(path, headers=api.headers, **kwargs)


def post(api, path, **kwargs):
    return api.gateway.post(path, headers=api.headers, **kwargs)


# ══════════════════════════════════════════════════════════════════
# §15 — access control
# ══════════════════════════════════════════════════════════════════


class TestAccessControl:
    def test_reads_require_a_token(self, gateway, api):
        assert gateway.get(BASE).status_code == 401
        assert gateway.get(f"{BASE}/{ACCOUNT_ID}").status_code == 401
        assert gateway.get(f"{BASE}/health").status_code == 401

    def test_an_invalid_token_is_rejected(self, gateway, api):
        res = gateway.get(BASE, headers={"Authorization": "Bearer nope"})
        assert res.status_code == 401

    def test_reads_are_open_to_a_read_only_role(self, as_reader):
        assert get(as_reader, BASE).status_code == 200
        assert get(as_reader, f"{BASE}/health").status_code == 200
        assert get(as_reader, f"{BASE}/{ACCOUNT_ID}").status_code == 200

    def test_operator_actions_are_closed_to_a_read_only_role(self, as_reader):
        assert post(as_reader, f"{BASE}/connect").status_code == 403
        assert post(as_reader, f"{BASE}/disconnect").status_code == 403
        assert post(as_reader, f"{BASE}/{ACCOUNT_ID}/sync").status_code == 403

    def test_an_operator_can_drive_the_lifecycle(self, api):
        assert post(api, f"{BASE}/connect").status_code == 200
        assert post(api, f"{BASE}/{ACCOUNT_ID}/sync").status_code == 202


# ══════════════════════════════════════════════════════════════════
# §16 — the registry / health endpoints the Dashboard polls
# ══════════════════════════════════════════════════════════════════


class TestRegistry:
    def test_the_registry_lists_accounts_without_connecting(self, api):
        body = get(api, BASE).json()
        assert body["count"] == 1
        assert body["accounts"][0]["account_id"] == ACCOUNT_ID
        assert body["provider"] == "simulated"
        assert body["connection_state"] == "DISCONNECTED"
        assert body["broker_connected"] is False
        assert body["source"] == "BROKER"

    def test_the_registry_does_not_open_a_channel(self, api):
        """§15 — a read must never have a broker side effect."""
        get(api, BASE)
        assert api.service.is_connected() is False

    def test_a_never_synced_account_blocks_and_says_offline(self, api):
        body = get(api, BASE).json()
        assert body["new_orders_blocked"] is True
        assert body["accounts"][0]["status"] == "OFFLINE"

    def test_connect_and_disconnect_report_the_channel_state(self, api):
        connected = post(api, f"{BASE}/connect").json()
        assert connected["broker_connected"] is True
        assert connected["connection_state"] == "CONNECTED"
        assert connected["accounts"] == [ACCOUNT_ID]
        assert get(api, BASE).json()["accounts"][0]["status"] == "CONNECTED"

        disconnected = post(api, f"{BASE}/disconnect").json()
        assert disconnected["broker_connected"] is False
        assert get(api, BASE).json()["connection_state"] == "DISCONNECTED"

    def test_health_is_declared_before_the_account_route(self, api):
        """/health must never be read as an account id."""
        res = get(api, f"{BASE}/health")
        assert res.status_code == 200
        assert "overall_health" in res.json()

    def test_health_rolls_up_to_offline_before_the_first_sync(self, api):
        body = get(api, f"{BASE}/health").json()
        assert body["overall_health"] == "OFFLINE"
        assert body["account_count"] == 1
        assert body["new_orders_blocked"] is True
        assert body["accounts"][0]["status"] == "OFFLINE"

    def test_health_turns_healthy_after_a_clean_sync(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/health").json()
        assert body["overall_health"] == "HEALTHY"
        assert body["new_orders_blocked"] is False
        assert body["position_mismatch_count"] == 0
        assert body["accounts"][0]["sync_latency_ms"] == LATENCY_MS

    def test_health_turns_blocked_on_a_mismatch(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.ledger_drifts(quantity=1)
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/health").json()
        assert body["overall_health"] == "BLOCKED"
        assert body["new_orders_blocked"] is True
        assert body["accounts"][0]["reconciliation_outcome"] == "FAIL"


# ══════════════════════════════════════════════════════════════════
# §7 / §15 — "no snapshot yet" is a 404, not a fabricated account
# ══════════════════════════════════════════════════════════════════


class TestNoSnapshotYet:
    def test_the_account_detail_is_honest_before_the_first_sync(self, api):
        body = get(api, f"{BASE}/{ACCOUNT_ID}").json()
        assert body["account"]["account_id"] == ACCOUNT_ID
        assert body["sync_status"]["status"] == "OFFLINE"
        assert body["balance"] is None
        assert body["positions"] == []
        assert body["reconciliation"] is None

    @pytest.mark.parametrize("suffix", ["balance", "positions"])
    def test_unavailable_reads_are_404_with_a_typed_envelope(self, api, suffix):
        res = get(api, f"{BASE}/{ACCOUNT_ID}/{suffix}")
        assert res.status_code == 404
        assert res.json()["error"] == "ACCOUNT_SNAPSHOT_NOT_FOUND"

    def test_snapshot_history_of_nothing_is_an_empty_list(self, api):
        body = get(api, f"{BASE}/{ACCOUNT_ID}/snapshots").json()
        assert body == {"account_id": ACCOUNT_ID, "count": 0, "limit": 50, "snapshots": []}

    def test_an_unknown_account_is_404(self, api):
        for path in (
            BASE + "/" + UNKNOWN,
            BASE + "/" + UNKNOWN + "/balance",
            BASE + "/" + UNKNOWN + "/positions",
            BASE + "/" + UNKNOWN + "/sync-status",
            BASE + "/" + UNKNOWN + "/snapshots",
        ):
            res = get(api, path)
            assert res.status_code == 404, path
            assert res.json()["error"] == "ACCOUNT_NOT_FOUND", path

    def test_syncing_an_unknown_account_is_404_without_a_channel(self, api):
        res = post(api, f"{BASE}/{UNKNOWN}/sync")
        assert res.status_code == 404
        assert api.service.is_connected() is False


# ══════════════════════════════════════════════════════════════════
# §6 — the operator's manual pull
# ══════════════════════════════════════════════════════════════════


class TestSyncAction:
    def test_a_manual_pull_returns_202_with_the_new_snapshot(self, api):
        res = post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        assert res.status_code == 202
        body = res.json()
        assert body["account_id"] == ACCOUNT_ID
        assert body["status"] == "SYNCED"
        assert body["sequence"] == 1
        assert body["position_count"] == 3
        assert body["sync_latency_ms"] == LATENCY_MS
        assert body["reconciliation"]["outcome"] == "PASS"
        assert body["snapshot_id"].startswith(f"{ACCOUNT_ID}-000001-")

    def test_a_manual_pull_opens_the_channel_when_needed(self, api):
        assert api.service.is_connected() is False
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        assert api.service.is_connected() is True

    def test_a_pull_can_refuse_to_open_the_channel(self, api):
        res = post(api, f"{BASE}/{ACCOUNT_ID}/sync?connect=false")
        assert res.status_code == 409
        body = res.json()
        assert body["error"] == "BROKER_ACCOUNT_NOT_CONNECTED"
        assert body["state"] == "DISCONNECTED"

    def test_two_pulls_append_two_traceable_snapshots(self, api):
        first = post(api, f"{BASE}/{ACCOUNT_ID}/sync").json()
        second = post(api, f"{BASE}/{ACCOUNT_ID}/sync").json()
        assert (first["sequence"], second["sequence"]) == (1, 2)
        assert first["snapshot_id"] != second["snapshot_id"]
        history = get(api, f"{BASE}/{ACCOUNT_ID}/snapshots").json()
        assert history["count"] == 2
        assert [s["sequence"] for s in history["snapshots"]] == [2, 1]

    def test_a_mismatch_is_served_as_a_mismatch(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.ledger_drifts(quantity=9999, available_quantity=9999)
        body = post(api, f"{BASE}/{ACCOUNT_ID}/sync").json()
        assert body["status"] == "MISMATCH"
        assert body["reconciliation"]["outcome"] == "FAIL"
        assert body["reconciliation"]["status"] == "MISMATCH"
        assert body["reconciliation"]["mismatch"] >= 1

    def test_the_snapshot_is_stored_even_when_it_fails_reconciliation(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.ledger_drifts(quantity=1)
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        history = get(api, f"{BASE}/{ACCOUNT_ID}/snapshots").json()
        assert history["count"] == 2
        assert [s["reconciliation_outcome"] for s in history["snapshots"]] == [
            "FAIL",
            "PASS",
        ]


# ══════════════════════════════════════════════════════════════════
# §3 / §10 / §18 — what a served snapshot contains
# ══════════════════════════════════════════════════════════════════


class TestServedSnapshot:
    def test_the_detail_carries_status_balance_and_positions_together(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}").json()
        assert body["sync_status"]["status"] == "SYNCED"
        assert body["sync_status"]["health"] == "HEALTHY"
        assert body["balance"]["total_asset"] == EXPECTED_TOTAL_ASSET
        assert len(body["positions"]) == 3
        assert body["reconciliation"]["outcome"] == "PASS"

    def test_the_balance_route_serves_the_account_totals(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/balance").json()
        assert body["account_id"] == ACCOUNT_ID
        assert body["currency"] == "CNY"
        assert body["cash"] != 0
        assert body["market_value"] == EXPECTED_MARKET_VALUE
        assert body["total_asset"] == body["cash"] + body["market_value"]
        assert body["consistent"] is True

    def test_positions_carry_the_valuation_and_the_verdict(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/positions").json()
        assert body["count"] == 3
        assert body["status"] == "SYNCED"
        by_symbol = {p["symbol"]: p for p in body["positions"]}
        for symbol, (price, value, pnl) in EXPECTED_POSITION_VALUES.items():
            position = by_symbol[symbol]
            assert position["market_price"] == float(price), symbol
            assert position["market_value"] == float(value), symbol
            assert position["unrealized_pnl"] == float(pnl), symbol
            assert position["status"] == "VALID", symbol
            assert position["consistent"] is True, symbol
            assert position["name"], symbol  # §16 display join

    def test_the_t_plus_1_split_is_served_as_the_broker_reported_it(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/positions").json()
        frozen = {p["symbol"]: p for p in body["positions"]}["159559"]
        assert frozen["quantity"] == frozen["frozen_quantity"]
        assert frozen["available_quantity"] == 0
        assert frozen["status"] == "VALID"

    def test_the_position_totals_add_up(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/positions").json()
        assert body["positions_market_value"] == float(EXPECTED_MARKET_VALUE)
        # 10,000×1.25 + 20,000×0.80 + 5,000×1.60
        assert body["total_cost"] == pytest.approx(36500.0)
        assert body["total_unrealized_pnl"] == pytest.approx(
            float(sum(pnl for _, _, pnl in EXPECTED_POSITION_VALUES.values()))
        )
        assert body["snapshot_timestamp"] is not None

    def test_an_unpriceable_position_is_null_not_zero(self, make_api):
        """§18 — absence stays absence, all the way to the browser."""
        from services.account.sync.valuation import MappingPriceProvider

        unvalued = make_api(price_provider=MappingPriceProvider({}))
        post(unvalued, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(unvalued, f"{BASE}/{ACCOUNT_ID}/positions").json()
        for position in body["positions"]:
            assert position["market_price"] is None
            assert position["market_value"] is None
            assert position["unrealized_pnl"] is None
        assert body["positions_market_value"] == 0.0
        # and the raw broker balance is served untouched, not summed from zeros
        balance = get(unvalued, f"{BASE}/{ACCOUNT_ID}/balance").json()
        assert balance["market_value"] == 128000.0

    def test_sync_status_exposes_maturity_latency_and_safety(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/sync-status").json()
        assert body["status"] == "SYNCED"
        assert body["health"] == "HEALTHY"
        assert body["stale_after_seconds"] == 30.0
        assert body["sync_interval_seconds"] == 10.0
        assert body["sync_latency_ms"] == LATENCY_MS
        assert body["last_sync_age_seconds"] == 0.0
        assert body["snapshot_count"] == 1
        assert body["position_count"] == 3
        assert body["invalid_count"] == 0
        assert body["mismatch_count"] == 0
        assert body["reconciliation_outcome"] == "PASS"
        assert body["new_orders_blocked"] is False
        assert body["last_successful_sync"] is not None

    def test_sync_status_is_honest_before_the_first_sync(self, api):
        body = get(api, f"{BASE}/{ACCOUNT_ID}/sync-status").json()
        assert body["status"] == "OFFLINE"
        assert body["health"] == "OFFLINE"
        assert body["last_successful_sync"] is None
        assert body["last_sync_age_seconds"] is None
        assert body["sync_latency_ms"] is None
        assert body["new_orders_blocked"] is True

    def test_a_stale_account_degrades_without_losing_its_numbers(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.clock.tick(31)
        api.service.mark_stale()
        status = get(api, f"{BASE}/{ACCOUNT_ID}/sync-status").json()
        assert status["status"] == "STALE"
        assert status["health"] == "DEGRADED"
        assert status["new_orders_blocked"] is True
        balance = get(api, f"{BASE}/{ACCOUNT_ID}/balance").json()
        assert balance["total_asset"] == EXPECTED_TOTAL_ASSET

    def test_snapshot_history_serves_the_audit_chain(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        body = get(api, f"{BASE}/{ACCOUNT_ID}/snapshots?limit=1").json()
        assert body["limit"] == 1
        assert body["count"] == 1
        newest = body["snapshots"][0]
        assert newest["sequence"] == 2
        assert newest["source"] == "BROKER"
        assert newest["position_count"] == 3
        assert newest["balance"]["total_asset"] == EXPECTED_TOTAL_ASSET

    @pytest.mark.parametrize("limit", [0, 501, -1])
    def test_an_out_of_range_snapshot_limit_is_rejected(self, api, limit):
        res = get(api, f"{BASE}/{ACCOUNT_ID}/snapshots?limit={limit}")
        assert res.status_code == 422
        assert api.service.is_connected() is False


# ══════════════════════════════════════════════════════════════════
# §17 — reads never reach for a vendor
# ══════════════════════════════════════════════════════════════════


class TestReadSideEffects:
    def test_reads_serve_the_store_and_never_touch_the_broker(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.provider.disconnect()  # the vendor goes away...
        for path in (
            BASE,
            f"{BASE}/health",
            f"{BASE}/{ACCOUNT_ID}",
            f"{BASE}/{ACCOUNT_ID}/balance",
            f"{BASE}/{ACCOUNT_ID}/positions",
            f"{BASE}/{ACCOUNT_ID}/sync-status",
            f"{BASE}/{ACCOUNT_ID}/snapshots",
        ):
            assert get(api, path).status_code == 200, path

    def test_a_read_after_disconnect_serves_the_last_known_state(self, api):
        post(api, f"{BASE}/{ACCOUNT_ID}/sync")
        api.provider.disconnect()
        body = get(api, f"{BASE}/{ACCOUNT_ID}").json()
        assert body["balance"]["total_asset"] == EXPECTED_TOTAL_ASSET
        # ...while honestly reporting that the channel is gone
        assert body["sync_status"]["broker_connected"] is False

    def test_the_api_never_imports_a_vendor_module(self):
        """§17 — the coupling is checked, not just documented."""
        source = accounts_router.__file__ or ""
        text = Path(source).read_text(encoding="utf-8")
        for marker in ("import vnpy", "from vnpy", "xtquant", "THS", "eastmoney"):
            assert marker not in text, marker
