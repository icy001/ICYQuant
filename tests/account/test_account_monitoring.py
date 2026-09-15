"""Commit 015 §11 / §14 — account sync health as Commit 013 sees it.

Monitoring owns no data: it *rolls up* the §12 status vocabulary into the
four §14 health values and re-states §11's safety rule as a single flag.
So these suites check the mapping table exhaustively and then the roll-up
over several accounts, including the two things a dashboard must never get
wrong: ``OFFLINE`` outranks ``BLOCKED``, and Paper Trading is never part
of the block.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from services.account.domain.account import Account
from services.account.domain.enums import (
    AccountStatus,
    AccountSyncHealth,
    SyncSource,
)
from services.account.sync.monitoring import (
    AccountSyncHealthSnapshot,
    AccountSyncMonitor,
    health_for_status,
    is_blocking,
)

try:  # pragma: no cover - both import paths are supported
    from .helpers import ACCOUNT_ID, LATENCY_MS, T0, Harness
except ImportError:  # pragma: no cover
    from helpers import ACCOUNT_ID, LATENCY_MS, T0, Harness  # type: ignore[no-redef]

STATUS = AccountStatus
HEALTH = AccountSyncHealth

#: §12 → §14, as specified.  ``SYNCING`` counts as healthy: a sync in
#: flight is the system working, not a fault.
EXPECTED_HEALTH = {
    STATUS.CONNECTED.value: HEALTH.HEALTHY.value,
    STATUS.SYNCING.value: HEALTH.HEALTHY.value,
    STATUS.SYNCED.value: HEALTH.HEALTHY.value,
    STATUS.STALE.value: HEALTH.DEGRADED.value,
    STATUS.ERROR.value: HEALTH.DEGRADED.value,
    STATUS.MISMATCH.value: HEALTH.BLOCKED.value,
    STATUS.OFFLINE.value: HEALTH.OFFLINE.value,
}

#: §11 — only these withhold trust in the broker/ledger truth.
EXPECTED_BLOCKING = {
    STATUS.CONNECTED.value: False,
    STATUS.SYNCING.value: False,
    STATUS.SYNCED.value: False,
    STATUS.STALE.value: True,
    STATUS.ERROR.value: True,
    STATUS.MISMATCH.value: True,
    STATUS.OFFLINE.value: True,
}


class FakeSource:
    """The two methods :class:`AccountSyncMonitor` actually needs."""

    def __init__(self, statuses: dict, accounts: list) -> None:
        self._statuses = statuses
        self._accounts = accounts

    def status(self, account_id=None):
        if account_id is None:
            account_id = next(iter(self._statuses), "")
        return dict(self._statuses.get(account_id, {"account_id": account_id}))

    def accounts(self):
        return list(self._accounts)


def account(account_id: str) -> Account:
    return Account(account_id=account_id, name=account_id, broker="simulated")


# ══════════════════════════════════════════════════════════════════
# §11 / §14 — the mapping tables
# ══════════════════════════════════════════════════════════════════


class TestStatusVocabulary:
    @pytest.mark.parametrize("status", list(EXPECTED_HEALTH))
    def test_every_sync_status_maps_to_its_health(self, status: str):
        assert health_for_status(status) == EXPECTED_HEALTH[status]

    @pytest.mark.parametrize("status", list(EXPECTED_BLOCKING))
    def test_the_blocking_set_is_exactly_the_untrusted_states(self, status: str):
        assert is_blocking(status) == EXPECTED_BLOCKING[status]

    def test_an_unknown_status_degrades_rather_than_reassures(self):
        assert health_for_status("SOMETHING_NEW") == HEALTH.DEGRADED.value
        assert health_for_status("") == HEALTH.DEGRADED.value

    def test_an_unknown_status_fails_safe_on_health_only(self):
        """The two tables have deliberately different failure modes:

        * ``health_for_status`` must never *reassure*, so an unknown value
          degrades;
        * ``is_blocking`` answers for the §12 vocabulary, which is closed —
          it is fed ``state machine.state``, so an unrecognised value is a
          code change rather than data that can arrive at runtime.
        """
        assert health_for_status("SOMETHING_NEW") == HEALTH.DEGRADED.value
        assert is_blocking("SOMETHING_NEW") is False
        # the vocabulary really is closed: both tables cover every status
        assert set(EXPECTED_HEALTH) == {s.value for s in STATUS}
        assert set(EXPECTED_BLOCKING) == {s.value for s in STATUS}


# ══════════════════════════════════════════════════════════════════
# §14 — one account
# ══════════════════════════════════════════════════════════════════


class TestHealthSnapshot:
    def test_a_status_dict_becomes_a_health_snapshot(self):
        source = FakeSource(
            {
                ACCOUNT_ID: {
                    "account_id": ACCOUNT_ID,
                    "status": STATUS.SYNCED.value,
                    "connection_state": "CONNECTED",
                    "last_successful_sync": T0.isoformat(),
                    "last_sync_age_seconds": 4.0,
                    "sync_latency_ms": LATENCY_MS,
                    "position_count": 3,
                    "mismatch_count": 0,
                    "invalid_count": 0,
                    "reconciliation_status": "RECONCILED",
                    "reconciliation_outcome": "PASS",
                    "new_orders_blocked": False,
                }
            },
            [account(ACCOUNT_ID)],
        )
        snapshot = AccountSyncMonitor(source).snapshot(ACCOUNT_ID)
        assert snapshot.status == STATUS.SYNCED.value
        assert snapshot.health == HEALTH.HEALTHY.value
        assert snapshot.last_successful_sync == T0
        assert snapshot.sync_latency_ms == LATENCY_MS
        assert snapshot.reconciliation_passed is True
        assert snapshot.new_orders_blocked is False

    def test_missing_optional_fields_do_not_crash_the_roll_up(self):
        source = FakeSource({ACCOUNT_ID: {"account_id": ACCOUNT_ID}}, [])
        snapshot = AccountSyncMonitor(source).snapshot(ACCOUNT_ID)
        assert snapshot.status == STATUS.OFFLINE.value
        assert snapshot.health == HEALTH.OFFLINE.value
        assert snapshot.position_count == 0
        assert snapshot.reconciliation_passed is False

    def test_the_blocking_flag_falls_back_to_the_status(self):
        source = FakeSource(
            {ACCOUNT_ID: {"account_id": ACCOUNT_ID, "status": STATUS.MISMATCH.value}}, []
        )
        assert AccountSyncMonitor(source).snapshot(ACCOUNT_ID).new_orders_blocked is True

    def test_an_iso_timestamp_is_parsed_and_a_bad_one_is_ignored(self):
        source = FakeSource(
            {ACCOUNT_ID: {"account_id": ACCOUNT_ID, "last_successful_sync": "not-a-date"}}, []
        )
        assert AccountSyncMonitor(source).snapshot(ACCOUNT_ID).last_successful_sync is None

    def test_the_health_dict_is_serialisable(self):
        source = FakeSource(
            {ACCOUNT_ID: {"account_id": ACCOUNT_ID, "status": STATUS.SYNCED.value}},
            [account(ACCOUNT_ID)],
        )
        payload = AccountSyncMonitor(source).health(ACCOUNT_ID)
        assert payload["account_id"] == ACCOUNT_ID
        assert payload["health"] == HEALTH.HEALTHY.value
        assert payload["last_successful_sync"] is None

    def test_the_snapshot_dataclass_is_always_serialisable(self):
        payload = AccountSyncHealthSnapshot(
            account_id=ACCOUNT_ID, status="SYNCED", health="HEALTHY"
        ).as_dict()
        assert payload["new_orders_blocked"] is False
        assert payload["position_count"] == 0


# ══════════════════════════════════════════════════════════════════
# §14 — the portfolio roll-up
# ══════════════════════════════════════════════════════════════════


class TestHealthReport:
    def report(self, statuses: dict) -> dict:
        source = FakeSource(
            {k: {"account_id": k, "status": v} for k, v in statuses.items()},
            [account(k) for k in statuses],
        )
        return AccountSyncMonitor(source).health_report()

    def test_a_single_healthy_account_reports_healthy(self):
        report = self.report({ACCOUNT_ID: STATUS.SYNCED.value})
        assert report["overall_health"] == HEALTH.HEALTHY.value
        assert report["new_orders_blocked"] is False
        assert report["account_count"] == 1
        assert report["position_mismatch_count"] == 0

    def test_degraded_outranks_healthy(self):
        report = self.report(
            {"A001": STATUS.SYNCED.value, "A002": STATUS.STALE.value}
        )
        assert report["overall_health"] == HEALTH.DEGRADED.value
        assert report["new_orders_blocked"] is True

    def test_blocked_outranks_degraded(self):
        report = self.report(
            {"A001": STATUS.STALE.value, "A002": STATUS.MISMATCH.value}
        )
        assert report["overall_health"] == HEALTH.BLOCKED.value

    def test_offline_outranks_blocked(self):
        report = self.report(
            {"A001": STATUS.MISMATCH.value, "A002": STATUS.OFFLINE.value}
        )
        assert report["overall_health"] == HEALTH.OFFLINE.value

    def test_mismatch_counts_add_up_across_accounts(self):
        source = FakeSource(
            {
                "A001": {
                    "account_id": "A001",
                    "status": STATUS.MISMATCH.value,
                    "mismatch_count": 2,
                },
                "A002": {"account_id": "A002", "status": STATUS.SYNCED.value, "mismatch_count": 1},
            },
            [account("A001"), account("A002")],
        )
        report = AccountSyncMonitor(source).health_report()
        assert report["position_mismatch_count"] == 3
        assert len(report["accounts"]) == 2

    def test_no_accounts_is_healthy_and_nothing_is_blocked(self):
        report = AccountSyncMonitor(FakeSource({}, [])).health_report()
        assert report["overall_health"] == HEALTH.HEALTHY.value
        assert report["account_count"] == 0
        assert report["new_orders_blocked"] is False
        assert report["accounts"] == []


# ══════════════════════════════════════════════════════════════════
# §14 — the text block (Commit 013's alerting reads this)
# ══════════════════════════════════════════════════════════════════


class TestRendering:
    def test_a_fresh_account_renders_placeholders_not_zeros(self):
        text = AccountSyncMonitor(Harness().service).render(ACCOUNT_ID)
        assert "ACCOUNT SYNC" in text
        assert "POSITION" in text
        assert "Status:       OFFLINE" in text
        assert "Last Sync:    -" in text
        assert "Latency:      -" in text

    def test_a_synced_account_renders_its_measurements(self):
        harness = Harness()
        harness.sync()
        text = harness.service.render_health(ACCOUNT_ID)
        assert "Status:       SYNCED" in text
        assert "Health:       HEALTHY" in text
        assert "Last Sync:    09:30:00" in text
        assert "Latency:      180ms" in text
        assert "Positions:    3" in text
        assert "Mismatch:     0" in text
        assert "Reconciled:   PASS" in text
        assert "BLOCKED" not in text

    def test_the_block_line_appears_only_when_orders_are_blocked(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts(quantity=1)
        harness.sync()
        text = harness.service.render_health(ACCOUNT_ID)
        assert "Reconciled:   FAIL" in text
        assert "Orders:       BLOCKED (new Shadow/Live)" in text

    def test_staleness_is_rendered_as_degraded(self):
        harness = Harness()
        harness.sync()
        harness.clock.tick(31)
        harness.service.mark_stale()
        text = harness.service.render_health(ACCOUNT_ID)
        assert "Status:       STALE" in text
        assert "Health:       DEGRADED" in text


# ══════════════════════════════════════════════════════════════════
# §14 / §18 — the same numbers the API serves
# ══════════════════════════════════════════════════════════════════


class TestHealthOverTheWire:
    def test_the_monitor_agrees_with_the_service_status(self):
        harness = Harness()
        harness.sync()
        status = harness.service.status(ACCOUNT_ID)
        health = harness.service.health(ACCOUNT_ID)
        assert health["status"] == status["status"]
        assert health["position_count"] == status["position_count"]
        assert health["sync_latency_ms"] == status["sync_latency_ms"]
        assert health["new_orders_blocked"] == status["new_orders_blocked"]

    def test_health_is_untouched_by_paper_trading(self):
        """§11 — the block is about Shadow/Live orders.  The journal's own
        simulated account is a different concern and never appears here."""
        harness = Harness(ledger=None)
        harness.sync()
        payload = harness.service.health(ACCOUNT_ID)
        assert payload["new_orders_blocked"] is False
        assert "paper" not in str(payload).lower()

    def test_the_raw_balance_survives_a_degraded_roll_up(self):
        """Health describes trust; it must not blank the numbers (§15)."""
        harness = Harness()
        snapshot = harness.sync()
        harness.clock.tick(31)
        harness.service.mark_stale()
        balance = harness.service.balance(ACCOUNT_ID)
        assert balance.total_asset == snapshot.balance.total_asset
        assert balance.market_value == Decimal("37300")

    def test_source_is_reported_so_a_replay_is_never_mistaken_for_live(self):
        harness = Harness(source=SyncSource.REPLAY.value)
        harness.sync()
        assert harness.service.health(ACCOUNT_ID)["status"] == STATUS.SYNCED.value
        assert harness.service.source == SyncSource.REPLAY.value

    def test_latency_survives_into_the_health_payload(self):
        harness = Harness()
        harness.sync()
        assert harness.service.health(ACCOUNT_ID)["sync_latency_ms"] == LATENCY_MS

    def test_the_age_increases_while_the_latency_does_not(self):
        """§12 vs §13 — two different clocks, never conflated."""
        harness = Harness()
        harness.sync()
        harness.clock.tick(20)
        health = harness.service.health(ACCOUNT_ID)
        assert health["last_sync_age_seconds"] == 20.0
        assert health["sync_latency_ms"] == LATENCY_MS
        assert health["last_successful_sync"] == (
            T0 + timedelta(milliseconds=LATENCY_MS)
        ).isoformat()
