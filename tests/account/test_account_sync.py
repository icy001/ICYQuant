"""Commit 015 §5 / §6 / §7 / §12 / §13 / §18 — the sync orchestrator.

The orchestrator is where the pieces meet, so these suites assert the
*consequences* rather than the internals:

* a snapshot is append-only and traceable (§7), and §13's latency is a
  real measurement between two clocks — never zero-by-construction;
* staleness is a decision made against ``max_sync_age`` (§12), not a
  guess;
* §18 valuation comes from Market Data and *nowhere else*, and when a
  price is missing the snapshot stays unvalued instead of pretending.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from services.account.domain.enums import AccountStatus
from services.account.sync.exceptions import (
    AccountNotFoundError,
    AccountProviderUnknownError,
    AccountSnapshotNotFoundError,
    BrokerAccountNotConnectedError,
)
from services.account.sync.ledger import LedgerBalance
from services.account.sync.valuation import MappingPriceProvider
from services.broker.account.broker_account import build_account_provider

try:  # pragma: no cover - both import paths are supported
    from .helpers import (
        ACCOUNT_ID,
        DEMO_QUANTITIES,
        EXPECTED_MARKET_VALUE,
        EXPECTED_POSITION_VALUES,
        EXPECTED_TOTAL_ASSET,
        LATENCY_MS,
        PRICES,
        T0,
        Harness,
        VirtualClock,
        demo_ledger_positions,
        make_config,
    )
except ImportError:  # pragma: no cover
    from helpers import (  # type: ignore[no-redef]
        ACCOUNT_ID,
        DEMO_QUANTITIES,
        EXPECTED_MARKET_VALUE,
        EXPECTED_POSITION_VALUES,
        EXPECTED_TOTAL_ASSET,
        LATENCY_MS,
        PRICES,
        T0,
        Harness,
        VirtualClock,
        demo_ledger_positions,
        make_config,
    )


# ══════════════════════════════════════════════════════════════════
# §5 / §12 — lifecycle
# ══════════════════════════════════════════════════════════════════


class TestLifecycle:
    def test_a_fresh_service_is_offline(self):
        harness = Harness()
        assert harness.service.is_connected() is False
        assert harness.service.connection_state() == "DISCONNECTED"
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.OFFLINE.value

    def test_sync_before_connect_is_refused_and_leaves_an_error(self):
        harness = Harness()
        with pytest.raises(BrokerAccountNotConnectedError):
            harness.service.sync(ACCOUNT_ID)
        # §12 — the failure is visible in the state machine, not swallowed
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.ERROR.value
        assert harness.repository.count(ACCOUNT_ID) == 0

    def test_registering_an_account_after_connect_lands_connected(self):
        harness = Harness(register=False)
        harness.connect()
        harness.register("A002")
        assert harness.service.state("A002") == AccountStatus.CONNECTED.value

    def test_connecting_moves_every_registered_account_to_connected(self):
        harness = Harness()
        harness.connect()
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.CONNECTED.value
        assert harness.service.accounts()[0].status == AccountStatus.CONNECTED.value

    def test_disconnecting_marks_the_account_offline(self):
        harness = Harness()
        harness.sync()
        harness.service.disconnect()
        assert harness.service.connection_state() == "DISCONNECTED"
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.OFFLINE.value
        assert harness.service.new_orders_blocked() is True

    def test_an_unknown_provider_is_refused_at_build_time(self):
        with pytest.raises(AccountProviderUnknownError):
            build_account_provider(make_config(provider="not-a-broker"))

    def test_the_channel_can_be_reopened(self):
        harness = Harness()
        harness.connect()
        harness.service.disconnect()
        harness.connect()
        assert harness.service.is_connected() is True
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.CONNECTED.value


# ══════════════════════════════════════════════════════════════════
# §6 / §7 / §13 — the snapshot pipeline
# ══════════════════════════════════════════════════════════════════


class TestSnapshotPipeline:
    def test_first_snapshot_is_stored_and_readable(self):
        harness = Harness()
        snapshot = harness.sync()
        assert snapshot.sequence == 1
        assert snapshot.status == AccountStatus.SYNCED.value
        assert harness.repository.count(ACCOUNT_ID) == 1
        assert harness.repository.latest(ACCOUNT_ID).snapshot_id == snapshot.snapshot_id
        assert harness.service.latest(ACCOUNT_ID) is not None

    def test_repeated_syncs_append_and_keep_history(self):
        harness = Harness()
        first = harness.sync()
        harness.clock.tick(10)
        second = harness.sync()
        assert (first.sequence, second.sequence) == (1, 2)
        assert first.snapshot_id != second.snapshot_id
        assert harness.repository.count(ACCOUNT_ID) == 2
        history = harness.service.snapshots(ACCOUNT_ID)
        assert [s.sequence for s in history] == [2, 1]  # newest first (§7)
        assert harness.service.snapshot(ACCOUNT_ID, first.snapshot_id) is not None
        assert harness.service.snapshot("A002", first.snapshot_id) is None

    def test_the_sequence_keeps_counting_when_history_is_pruned(self):
        """§7 — a bounded store must not restart the numbering, and the
        number in the id must always be the number in the field."""
        from services.account.sync.repository import (
            InMemoryAccountSnapshotRepository,
        )

        repository = InMemoryAccountSnapshotRepository(max_history_per_account=2)
        harness = Harness(ledger=None, repository=repository)
        assert [harness.sync().sequence for _ in range(4)] == [1, 2, 3, 4]
        assert repository.count(ACCOUNT_ID) == 2
        newest = repository.latest(ACCOUNT_ID)
        assert newest.snapshot_id.split("-")[1] == f"{newest.sequence:06d}"

    def test_snapshot_can_be_fetched_by_id_only_within_its_account(self):
        harness = Harness()
        snapshot = harness.sync()
        assert harness.service.snapshot("OTHER", snapshot.snapshot_id) is None

    def test_latency_is_a_measurement_not_a_constant(self):
        harness = Harness()
        assert harness.sync().sync_latency_ms == LATENCY_MS
        # both clocks move: the broker stamps a later time and we read it
        # the same 180ms later, so the *latency* is stable while the
        # absolute receipt time proves the clock really advanced
        harness.provider_clock.tick(2)
        harness.clock.tick(2)
        assert harness.sync().sync_latency_ms == LATENCY_MS
        assert harness.service.last_successful_sync(ACCOUNT_ID) == T0 + timedelta(
            seconds=2, milliseconds=LATENCY_MS
        )

    def test_latency_is_recorded_for_the_dashboard(self):
        harness = Harness()
        harness.sync()
        assert harness.service.sync_latency_ms(ACCOUNT_ID) == LATENCY_MS

    def test_snapshots_report_their_source(self):
        harness = Harness(source="SIMULATED")
        snapshot = harness.sync()
        assert snapshot.source == "SIMULATED"
        assert harness.service.source == "SIMULATED"

    def test_source_defaults_to_broker(self):
        assert Harness().sync().source == "BROKER"

    def test_last_successful_sync_is_the_receipt_time(self):
        harness = Harness()
        harness.sync()
        assert harness.service.last_successful_sync(ACCOUNT_ID) == harness.clock.value
        assert harness.service.status(ACCOUNT_ID)["last_sync_age_seconds"] == 0.0

    def test_an_empty_broker_book_is_still_a_snapshot(self):
        """An account with no holdings is a fact, not a missing sync."""
        harness = Harness(ledger=None)  # nothing to reconcile against
        harness.connect()
        harness.provider.set_positions(ACCOUNT_ID, [])
        snapshot = harness.service.sync(ACCOUNT_ID)
        assert snapshot.position_count == 0
        assert snapshot.positions == []
        assert snapshot.status == AccountStatus.SYNCED.value
        assert harness.repository.count(ACCOUNT_ID) == 1


# ══════════════════════════════════════════════════════════════════
# §18 — valuation comes from Market Data, and only Market Data
# ══════════════════════════════════════════════════════════════════


class TestValuation:
    def test_positions_are_valued_from_the_price_provider(self):
        harness = Harness()
        harness.sync()
        positions = harness.positions_by_symbol()
        for symbol, (price, value, pnl) in EXPECTED_POSITION_VALUES.items():
            position = positions[symbol]
            assert position.market_price == price, symbol
            assert position.market_value == value, symbol
            assert position.unrealized_pnl == pnl, symbol

    def test_the_broker_book_is_quantity_only(self):
        """§18 — the broker's own 现价 / 市值 never reach the model."""
        harness = Harness()
        positions = harness.sync().positions
        assert [p.quantity for p in positions] == list(DEMO_QUANTITIES)

    def test_balance_market_value_is_the_sum_of_the_valued_book(self):
        harness = Harness()
        balance = harness.sync().balance
        assert balance.market_value == EXPECTED_MARKET_VALUE
        assert balance.total_asset == EXPECTED_TOTAL_ASSET
        assert balance.total_asset == balance.cash + balance.market_value
        assert balance.consistent is True

    def test_valuation_can_be_switched_off(self):
        harness = Harness(config=make_config(valuation_enabled=False))
        snapshot = harness.sync()
        assert all(p.market_value is None for p in snapshot.positions)
        # the broker's own balance survives untouched
        assert snapshot.balance.market_value == Decimal("128000")
        assert snapshot.balance.total_asset == Decimal("211500")

    def test_an_unpriceable_symbol_stays_unvalued_not_zero(self):
        harness = Harness(price_provider=MappingPriceProvider({}))
        snapshot = harness.sync()
        assert all(p.market_price is None for p in snapshot.positions)
        assert all(p.market_value is None for p in snapshot.positions)
        # nothing was summed from a fabricated zero — the broker total stands
        assert snapshot.balance.market_value == Decimal("128000")

    def test_a_partially_priced_book_is_not_summed_into_a_lie(self):
        harness = Harness(
            price_provider=MappingPriceProvider({"159852": PRICES["159852"]})
        )
        snapshot = harness.sync()
        valued = harness.positions_by_symbol()["159852"]
        unvalued = harness.positions_by_symbol()["159559"]
        assert valued.market_value == Decimal("12800")
        assert unvalued.market_value is None
        assert snapshot.balance.market_value == Decimal("128000")
        assert snapshot.balance.total_asset == Decimal("211500")

    def test_valuation_is_absent_when_market_data_is_absent(self):
        harness = Harness(price_provider=None)  # Valuator disables itself
        snapshot = harness.sync()
        assert all(p.market_value is None for p in snapshot.positions)
        assert snapshot.balance.total_asset == Decimal("211500")


# ══════════════════════════════════════════════════════════════════
# §12 — staleness
# ══════════════════════════════════════════════════════════════════


class TestStaleness:
    def test_a_fresh_sync_is_not_stale(self):
        harness = Harness()
        harness.sync()
        harness.clock.tick(10)  # max_sync_age is 30s
        assert harness.service.mark_stale() == []
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.SYNCED.value

    def test_a_sync_older_than_max_age_is_marked_stale(self):
        harness = Harness()
        harness.sync()
        harness.clock.tick(31)
        assert harness.service.mark_stale() == [ACCOUNT_ID]
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.STALE.value
        assert harness.service.accounts()[0].status == AccountStatus.STALE.value
        assert harness.service.new_orders_blocked() is True

    def test_an_account_that_never_synced_is_not_stale_it_is_offline(self):
        harness = Harness()
        harness.clock.tick(9999)
        assert harness.service.mark_stale() == []
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.OFFLINE.value

    def test_mark_stale_can_target_one_account(self):
        harness = Harness(ledger=None, register=False)
        harness.register(ACCOUNT_ID)
        harness.register("A002")
        harness.connect()
        harness.sync(ACCOUNT_ID)
        harness.sync("A002")
        harness.clock.tick(31)
        assert harness.service.mark_stale(ACCOUNT_ID) == [ACCOUNT_ID]
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.STALE.value
        assert harness.service.state("A002") == AccountStatus.SYNCED.value
        assert harness.service.accounts()[1].status == AccountStatus.SYNCED.value

    def test_the_age_is_reported_in_seconds(self):
        harness = Harness()
        harness.sync()
        harness.clock.tick(12)
        status = harness.service.status(ACCOUNT_ID)
        assert status["last_sync_age_seconds"] == 12.0


# ══════════════════════════════════════════════════════════════════
# §14 / §15 — status & reads
# ══════════════════════════════════════════════════════════════════


class TestStatusAndReads:
    def test_status_reports_the_facts_the_dashboard_needs(self):
        harness = Harness()
        harness.sync()
        status = harness.service.status(ACCOUNT_ID)
        assert status["account_id"] == ACCOUNT_ID
        assert status["status"] == AccountStatus.SYNCED.value
        assert status["source"] == "BROKER"
        assert status["provider"] == "simulated"
        assert status["broker_connected"] is True
        assert status["position_count"] == 3
        assert status["invalid_count"] == 0
        assert status["mismatch_count"] == 0
        assert status["reconciliation_status"] == "RECONCILED"
        assert status["reconciliation_outcome"] == "PASS"
        assert status["new_orders_blocked"] is False
        assert status["snapshot_count"] == 1

    def test_status_before_any_sync_is_offline_and_blocking(self):
        harness = Harness()
        status = harness.service.status(ACCOUNT_ID)
        assert status["status"] == AccountStatus.OFFLINE.value
        assert status["new_orders_blocked"] is True
        assert status["last_successful_sync"] is None
        assert status["last_sync_age_seconds"] is None
        assert status["position_count"] == 0

    def test_status_without_any_account_is_a_neutral_shell(self):
        harness = Harness(config=make_config(account_id=None), register=False)
        status = harness.service.status()
        assert status["account_id"] == ""
        assert status["status"] == AccountStatus.OFFLINE.value
        assert status["new_orders_blocked"] is False
        assert harness.service.accounts() == []

    def test_status_for_an_unknown_account_is_a_404(self):
        harness = Harness()
        with pytest.raises(AccountNotFoundError):
            harness.service.status("NOPE")
        with pytest.raises(AccountNotFoundError):
            harness.service.account("NOPE")

    def test_sync_with_a_configured_account_but_no_registration_is_refused(self):
        harness = Harness(config=make_config(account_id=None), register=False)
        with pytest.raises(AccountNotFoundError):
            harness.service.sync()

    def test_syncing_an_unregistered_account_is_a_404(self):
        harness = Harness()
        with pytest.raises(AccountNotFoundError):
            harness.service.sync("NOPE")

    def test_reads_before_the_first_snapshot_are_explicit_404s(self):
        harness = Harness()
        with pytest.raises(AccountSnapshotNotFoundError):
            harness.service.balance(ACCOUNT_ID)
        with pytest.raises(AccountSnapshotNotFoundError):
            harness.service.positions(ACCOUNT_ID)

    def test_registering_the_same_account_twice_is_idempotent(self):
        harness = Harness()
        harness.register()
        assert len(harness.service.accounts()) == 1
        assert harness.service.account(ACCOUNT_ID).account_id == ACCOUNT_ID

    def test_sync_all_covers_every_registered_account(self):
        harness = Harness(register=False)
        harness.register(ACCOUNT_ID)
        harness.register("A002")
        harness.connect()
        snapshots = harness.service.sync_all()
        assert {s.account_id for s in snapshots} == {ACCOUNT_ID, "A002"}
        assert harness.repository.count("A002") == 1

    def test_the_service_describes_itself(self):
        harness = Harness()
        described = harness.service.as_dict()
        assert described["provider"] == "simulated"
        assert described["connection_state"] == "DISCONNECTED"
        assert described["account_count"] == 1
        assert "sync_interval_seconds" in described["config"]


# ══════════════════════════════════════════════════════════════════
# §9 / §11 — the ledger is consulted, never rewritten
# ══════════════════════════════════════════════════════════════════


class TestLedgerBoundary:
    def test_a_matching_ledger_yields_a_synced_account(self):
        harness = Harness()
        snapshot = harness.sync()
        assert snapshot.reconciliation["outcome"] == "PASS"
        assert snapshot.status == AccountStatus.SYNCED.value
        assert harness.service.new_orders_blocked() is False

    def test_a_drifting_ledger_yields_mismatch_and_blocks_orders(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts("159852", quantity=9999, available_quantity=9999)
        snapshot = harness.sync()
        assert snapshot.status == AccountStatus.MISMATCH.value
        assert snapshot.reconciliation["outcome"] == "FAIL"
        assert snapshot.reconciliation["status"] == "MISMATCH"
        assert harness.service.new_orders_blocked() is True
        assert harness.repository.count(ACCOUNT_ID) == 2  # both snapshots kept

    def test_the_broker_book_is_never_rewritten_to_match_the_ledger(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts("159852", quantity=9999)
        harness.sync()
        assert harness.positions_by_symbol()["159852"].quantity == Decimal("10000")
        assert [p.quantity for p in harness.service.positions(ACCOUNT_ID)] == list(
            DEMO_QUANTITIES
        )

    def test_the_ledger_is_read_only_by_construction(self):
        """The service holds a reader, never a writer (§9)."""
        harness = Harness()
        assert not hasattr(harness.service.ledger, "set_positions_from_snapshot")
        assert harness.service.ledger is harness.ledger

    def test_without_a_ledger_the_snapshot_is_simply_not_reconciled(self):
        harness = Harness(ledger=None)
        snapshot = harness.sync()
        assert snapshot.reconciliation is None
        assert snapshot.status == AccountStatus.SYNCED.value
        assert harness.service.report(ACCOUNT_ID) is None
        assert harness.service.reconciliation(ACCOUNT_ID) is None

    def test_a_ledger_balance_is_compared_when_one_exists(self):
        harness = Harness()
        harness.service.connect()
        first = harness.service.sync(ACCOUNT_ID)
        harness.set_ledger_balance(
            LedgerBalance(
                account_id=ACCOUNT_ID,
                cash="83500",
                available_cash="82000",
                frozen_cash="1500",
                market_value=str(first.balance.market_value),
                total_asset=str(first.balance.total_asset),
            )
        )
        snapshot = harness.service.sync(ACCOUNT_ID)
        report = snapshot.reconciliation
        assert "ACCOUNT_BALANCE" in {item["check"] for item in report["items"]}
        assert report["outcome"] == "PASS"

    def test_the_service_reconciles_whatever_reader_it_was_wired_with(self):
        from services.account.sync.ledger import InMemoryPositionLedgerReader

        reader = InMemoryPositionLedgerReader()
        reader.set_positions(ACCOUNT_ID, demo_ledger_positions())
        snapshot = Harness(ledger=reader).sync()
        assert snapshot.reconciliation["outcome"] == "PASS"
        assert reader.balance(ACCOUNT_ID) is None  # no cash leg was seeded
        assert reader.positions("UNKNOWN") == []
        assert reader.balance("UNKNOWN") is None


# ══════════════════════════════════════════════════════════════════
# §5 — vendor failure propagation
# ══════════════════════════════════════════════════════════════════


class TestVendorFailures:
    def test_a_dropped_channel_marks_the_account_in_error(self):
        harness = Harness()
        harness.sync()
        harness.provider.disconnect()  # the vendor channel dies under us
        with pytest.raises(BrokerAccountNotConnectedError):
            harness.service.sync(ACCOUNT_ID)
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.ERROR.value
        assert harness.service.new_orders_blocked() is True
        assert harness.repository.count(ACCOUNT_ID) == 1  # the old one survives

    def test_a_channel_that_stops_serving_mid_stream_is_reported(self):
        harness = Harness()
        harness.connect()
        harness.provider.disconnect()
        with pytest.raises(BrokerAccountNotConnectedError):
            harness.service.sync(ACCOUNT_ID)
        assert harness.repository.count(ACCOUNT_ID) == 0

    def test_recovery_after_a_failure(self):
        harness = Harness()
        harness.sync()
        harness.provider.disconnect()
        with pytest.raises(BrokerAccountNotConnectedError):
            harness.service.sync(ACCOUNT_ID)
        harness.connect()  # the channel is reopened
        snapshot = harness.service.sync(ACCOUNT_ID)
        assert snapshot.status == AccountStatus.SYNCED.value
        assert harness.service.state(ACCOUNT_ID) == AccountStatus.SYNCED.value
        assert harness.service.new_orders_blocked() is False
        assert snapshot.sequence == 2

    def test_a_connect_failure_is_surfaced(self):
        from services.broker.account.broker_account import SimulatedAccountProvider

        config = make_config()
        provider = SimulatedAccountProvider(config, clock=VirtualClock(T0), fail_connect_times=1)
        harness = Harness(config=config, provider=provider)
        with pytest.raises(Exception):
            harness.service.connect()
        assert harness.service.is_connected() is False
        # the second attempt succeeds — the failure was transient
        harness.connect()
        assert harness.service.is_connected() is True
