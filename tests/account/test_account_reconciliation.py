"""Commit 015 §9 / §10 / §11 — broker vs ledger reconciliation.

§10 names five checks and §11 turns the verdict into a safety rule, so
these suites assert both the *arithmetic* (which check fired, on which
symbol, with which difference) and the *consequence* (PASS/FAIL ⇒
Shadow/Live orders open/blocked, with Paper Trading never involved).

§9 is asserted negatively throughout: reconciling must leave the broker
snapshot and the ledger holding exactly what they held before.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from services.account.domain.enums import (
    ReconciliationCheck,
    ReconciliationOutcome,
    ReconciliationStatus,
    worst_status,
)
from services.account.sync.ledger import LedgerBalance
from services.account.sync.reconciliation import (
    AccountReconciler,
    ReconciliationItem,
    ReconciliationReport,
)

try:  # pragma: no cover - both import paths are supported
    from .helpers import (
        ACCOUNT_ID,
        LATENCY_MS,
        T0,
        Harness,
        account_payload,
        demo_position_payloads,
        ledger_position,
        make_normalizer,
        position_payload,
    )
except ImportError:  # pragma: no cover
    from helpers import (  # type: ignore[no-redef]
        ACCOUNT_ID,
        LATENCY_MS,
        T0,
        Harness,
        account_payload,
        demo_position_payloads,
        ledger_position,
        make_normalizer,
        position_payload,
    )

CHECK = ReconciliationCheck
STATUS = ReconciliationStatus
OUTCOME = ReconciliationOutcome

RECEIVED = T0 + timedelta(milliseconds=LATENCY_MS)

#: The demo broker book, as the ledger believes it (§9).
DEMO_LEDGER = {
    "159852": {"quantity": "10000", "available_quantity": "10000", "average_cost": "1.250"},
    "159559": {"quantity": "20000", "available_quantity": "0", "average_cost": "0.800"},
    "513050": {"quantity": "5000", "available_quantity": "5000", "average_cost": "1.600"},
}


def reconcile(snapshot, rows, balance=None, **kwargs) -> ReconciliationReport:
    return AccountReconciler(**kwargs).reconcile(snapshot, rows, balance)


def broker_snapshot(rows=None, account=None, **config_overrides):
    """A snapshot straight out of the normalizer — no valuation, no ledger."""
    return make_normalizer(**config_overrides).normalize_snapshot(
        ACCOUNT_ID,
        account if account is not None else account_payload(),
        demo_position_payloads() if rows is None else rows,
        received_timestamp=RECEIVED,
    )


def ledger_rows(drop=(), **per_symbol):
    """The demo ledger, optionally drifting one symbol or dropping one row."""
    rows = []
    for symbol, defaults in DEMO_LEDGER.items():
        if symbol in drop:
            continue
        fields = {**defaults, **per_symbol.get(symbol, {})}
        rows.append(ledger_position(symbol, **fields))
    return rows


def item(report: ReconciliationReport, symbol: str, check: str) -> ReconciliationItem:
    matches = [
        i for i in report.items if i.symbol == symbol and i.check == check.value
    ]
    assert len(matches) == 1, f"expected exactly one {check.value} item for {symbol}"
    return matches[0]


def checks_for(report: ReconciliationReport, symbol: str) -> set[str]:
    return {i.check for i in report.items_for(symbol)}


# ══════════════════════════════════════════════════════════════════
# §10 — the happy path
# ══════════════════════════════════════════════════════════════════


class TestMatchingBook:
    def test_a_clean_book_reconciles_every_check(self):
        report = reconcile(broker_snapshot(), ledger_rows())
        assert report.status == STATUS.RECONCILED.value
        assert report.outcome == OUTCOME.PASS.value
        assert report.failed is False
        # 3 symbols × (quantity + available + cost); no market value on
        # the ledger side and no ledger balance ⇒ those checks are skipped
        assert report.checked == 9
        assert report.matched == 9
        assert report.mismatch_count == 0
        assert report.mismatch == report.missing_broker == report.missing_ledger == 0
        assert all(i.matched for i in report.items)

    def test_all_three_checks_run_per_position(self):
        report = reconcile(broker_snapshot(), ledger_rows())
        for symbol in DEMO_LEDGER:
            assert checks_for(report, symbol) == {
                CHECK.POSITION_QUANTITY.value,
                CHECK.AVAILABLE_QUANTITY.value,
                CHECK.AVERAGE_COST.value,
            }

    def test_the_t_plus_one_frozen_leg_is_not_a_mismatch(self):
        """§19 — 159559 is fully frozen on both sides; that is agreement."""
        report = reconcile(broker_snapshot(), ledger_rows())
        frozen = item(report, "159559", CHECK.AVAILABLE_QUANTITY)
        assert frozen.broker_value == frozen.ledger_value == Decimal("0")
        assert frozen.status == STATUS.RECONCILED.value

    def test_the_report_is_traceable_to_the_snapshot_it_came_from(self):
        snapshot = broker_snapshot()
        report = reconcile(snapshot, ledger_rows())
        assert report.account_id == ACCOUNT_ID
        assert report.snapshot_id == snapshot.snapshot_id
        assert report.timestamp == snapshot.timestamp

    def test_two_empty_books_agree(self):
        report = reconcile(broker_snapshot(rows=[]), [])
        assert report.checked == 0
        assert report.status == STATUS.RECONCILED.value
        assert report.outcome == OUTCOME.PASS.value


# ══════════════════════════════════════════════════════════════════
# §10 — the four ways a book can disagree
# ══════════════════════════════════════════════════════════════════


class TestDisagreements:
    def test_a_quantity_drift_is_a_mismatch_with_a_signed_difference(self):
        report = reconcile(broker_snapshot(), ledger_rows(**{"159852": {"quantity": "9900"}}))
        drift = item(report, "159852", CHECK.POSITION_QUANTITY)
        assert drift.status == STATUS.MISMATCH.value
        assert drift.broker_value == Decimal("10000")
        assert drift.ledger_value == Decimal("9900")
        assert drift.difference == Decimal("100")  # broker − ledger
        assert report.status == STATUS.MISMATCH.value
        assert report.failed is True

    def test_only_the_drifting_check_fires(self):
        report = reconcile(broker_snapshot(), ledger_rows(**{"159852": {"quantity": "9900"}}))
        assert checks_for(report, "159559") == {
            CHECK.POSITION_QUANTITY.value,
            CHECK.AVAILABLE_QUANTITY.value,
            CHECK.AVERAGE_COST.value,
        }
        assert [
            i.check for i in report.items_for("159852") if not i.matched
        ] == [CHECK.POSITION_QUANTITY.value]

    def test_an_availability_drift_is_its_own_check(self):
        report = reconcile(
            broker_snapshot(), ledger_rows(**{"159852": {"available_quantity": "9000"}})
        )
        availability = item(report, "159852", CHECK.AVAILABLE_QUANTITY)
        assert availability.status == STATUS.MISMATCH.value
        assert item(report, "159852", CHECK.POSITION_QUANTITY).matched is True

    def test_a_cost_drift_is_its_own_check(self):
        report = reconcile(broker_snapshot(), ledger_rows(**{"159852": {"average_cost": "1.30"}}))
        cost = item(report, "159852", CHECK.AVERAGE_COST)
        assert cost.status == STATUS.MISMATCH.value
        assert cost.difference == Decimal("-0.05")

    def test_ledger_only_position_is_missing_broker(self):
        rows = ledger_rows()
        rows.append(ledger_position("510300", "1000"))
        report = reconcile(broker_snapshot(), rows)
        missing = item(report, "510300", CHECK.POSITION_QUANTITY)
        assert missing.status == STATUS.MISSING_BROKER.value
        assert missing.broker_value is None
        assert missing.ledger_value == Decimal("1000")
        assert missing.difference is None  # undefined, not zero
        assert report.missing_broker == 1
        assert report.status == STATUS.MISSING_BROKER.value
        assert report.failed is True

    def test_broker_only_position_is_missing_ledger(self):
        report = reconcile(broker_snapshot(), ledger_rows(drop=("513050",)))
        missing = item(report, "513050", CHECK.POSITION_QUANTITY)
        assert missing.status == STATUS.MISSING_LEDGER.value
        assert missing.ledger_value is None
        assert missing.broker_value == Decimal("5000")
        assert report.missing_ledger == 1
        assert report.status == STATUS.MISSING_LEDGER.value

    def test_missing_broker_outranks_nothing_but_a_real_mismatch(self):
        rows = ledger_rows(**{"159852": {"quantity": "9900"}})
        rows.append(ledger_position("510300", "1000"))
        report = reconcile(broker_snapshot(), rows)
        assert report.status == STATUS.MISMATCH.value  # MISMATCH > MISSING_BROKER
        assert (report.mismatch, report.missing_broker) == (1, 1)

    def test_an_invalid_broker_position_is_reported_not_compared(self):
        """§3 / §19 — the broker never sent a split, so there is nothing
        trustworthy to compare; the row is INVALID and short-circuits."""
        snapshot = broker_snapshot(
            rows=[position_payload("159852", **{"可用数量": None, "冻结数量": None})]
        )
        report = reconcile(
            snapshot, [ledger_position("159852", "10000", available_quantity="10000")]
        )
        assert len(report.items) == 1
        invalid = report.items[0]
        assert invalid.check == CHECK.POSITION_QUANTITY.value
        assert invalid.status == STATUS.INVALID.value
        assert invalid.broker_value == Decimal("10000")  # the number is kept
        assert report.status == STATUS.INVALID.value
        assert report.invalid == 1
        assert report.failed is True

    def test_invalid_outranks_a_mismatch(self):
        rows = demo_position_payloads()
        # 159852: the broker omitted the availability split outright (§19)
        rows[0] = {
            k: v for k, v in rows[0].items() if k not in ("可用数量", "冻结数量")
        }
        # 513050: a plain quantity + availability drift
        rows[2] = {**rows[2], "持仓数量": "4000", "可用数量": "4000", "冻结数量": "0"}
        report = reconcile(broker_snapshot(rows=rows), ledger_rows())
        assert report.status == STATUS.INVALID.value
        # 159852 → INVALID; 513050 drifts on quantity and availability only
        assert (report.invalid, report.mismatch) == (1, 2)


# ══════════════════════════════════════════════════════════════════
# §10 — optional checks
# ══════════════════════════════════════════════════════════════════


class TestOptionalChecks:
    def test_market_value_is_compared_when_both_sides_have_a_price(self):
        """§18 — the broker half is valued by Market Data, so the check is
        meaningful exactly when the ledger also carries a value."""
        snapshot = Harness(ledger=None).sync()
        rows = ledger_rows()
        rows[0] = ledger_position(
            "159852",
            "10000",
            available_quantity="10000",
            average_cost="1.250",
            market_value="12800",
        )
        report = reconcile(snapshot, rows)
        value = item(report, "159852", CHECK.MARKET_VALUE)
        assert value.status == STATUS.RECONCILED.value
        assert value.broker_value == Decimal("12800")

    def test_a_stale_ledger_price_is_a_mismatch(self):
        snapshot = Harness(ledger=None).sync()
        rows = ledger_rows()
        rows[0] = ledger_position(
            "159852",
            "10000",
            available_quantity="10000",
            average_cost="1.250",
            market_value="12700",
        )
        report = reconcile(snapshot, rows)
        assert item(report, "159852", CHECK.MARKET_VALUE).status == STATUS.MISMATCH.value

    def test_the_price_check_is_skipped_when_the_broker_side_is_unvalued(self):
        """An absent price is *unknown*, never zero — so there is nothing
        to compare and the check must not report a mismatch (§18)."""
        report = reconcile(broker_snapshot(), ledger_rows())
        symbols = {i.symbol for i in report.items if i.check == CHECK.MARKET_VALUE.value}
        assert symbols == set()
        assert report.status == STATUS.RECONCILED.value

    def test_the_cost_check_is_skipped_without_a_cost_on_either_side(self):
        snapshot = broker_snapshot(rows=[position_payload("159852", **{"成本价": None})])
        report = reconcile(
            snapshot, [ledger_position("159852", "10000", available_quantity="10000")]
        )
        assert report.status == STATUS.RECONCILED.value
        assert checks_for(report, "159852") == {
            CHECK.POSITION_QUANTITY.value,
            CHECK.AVAILABLE_QUANTITY.value,
        }

    def test_a_ledger_without_availability_skips_only_that_check(self):
        report = reconcile(
            broker_snapshot(rows=[position_payload("159852")]),
            [ledger_position("159852", "10000", average_cost="1.250")],
        )
        assert checks_for(report, "159852") == {
            CHECK.POSITION_QUANTITY.value,
            CHECK.AVERAGE_COST.value,
        }
        assert report.status == STATUS.RECONCILED.value

    def test_the_balance_is_checked_only_when_the_ledger_tracks_one(self):
        report = reconcile(broker_snapshot(), ledger_rows())
        assert not [
            i for i in report.items if i.check == CHECK.ACCOUNT_BALANCE.value
        ]

    def test_a_matching_balance_reconciles(self):
        snapshot = broker_snapshot()
        balance = LedgerBalance(
            account_id=ACCOUNT_ID,
            cash="83500",
            total_asset=snapshot.balance.total_asset,
        )
        report = reconcile(snapshot, ledger_rows(), balance)
        check = item(report, ACCOUNT_ID, CHECK.ACCOUNT_BALANCE)
        assert check.broker_value == check.ledger_value == Decimal("211500")
        assert check.status == STATUS.RECONCILED.value
        assert report.checked == 10
        assert report.outcome == OUTCOME.PASS.value

    def test_a_drifting_balance_is_a_mismatch(self):
        report = reconcile(
            broker_snapshot(),
            ledger_rows(),
            LedgerBalance(account_id=ACCOUNT_ID, total_asset="211000"),
        )
        check = item(report, ACCOUNT_ID, CHECK.ACCOUNT_BALANCE)
        assert check.status == STATUS.MISMATCH.value
        assert check.difference == Decimal("500")
        assert report.status == STATUS.MISMATCH.value

    def test_a_cash_only_ledger_is_compared_against_its_cash(self):
        """With no total on the ledger side, ``cash`` *is* the total."""
        report = reconcile(
            broker_snapshot(), ledger_rows(), LedgerBalance(account_id=ACCOUNT_ID, cash="83500")
        )
        check = item(report, ACCOUNT_ID, CHECK.ACCOUNT_BALANCE)
        assert check.ledger_value == Decimal("83500")
        assert check.status == STATUS.MISMATCH.value  # 211500 ≠ 83500


# ══════════════════════════════════════════════════════════════════
# §10 — tolerances
# ══════════════════════════════════════════════════════════════════


class TestTolerances:
    def test_a_sub_tolerance_cost_difference_is_reconciled(self):
        """A vendor rounding a cost to 3dp must not block trading."""
        report = reconcile(
            broker_snapshot(), ledger_rows(**{"159852": {"average_cost": "1.253"}})
        )
        assert item(report, "159852", CHECK.AVERAGE_COST).status == STATUS.RECONCILED.value
        assert report.outcome == OUTCOME.PASS.value

    def test_a_difference_beyond_tolerance_is_a_mismatch(self):
        report = reconcile(
            broker_snapshot(), ledger_rows(**{"159852": {"average_cost": "1.260"}})
        )
        assert item(report, "159852", CHECK.AVERAGE_COST).status == STATUS.MISMATCH.value

    def test_quantity_has_zero_tolerance_by_default(self):
        report = reconcile(broker_snapshot(), ledger_rows(**{"159852": {"quantity": "9999.5"}}))
        assert item(report, "159852", CHECK.POSITION_QUANTITY).status == STATUS.MISMATCH.value

    def test_a_quantity_tolerance_can_be_configured(self):
        report = reconcile(
            broker_snapshot(),
            ledger_rows(**{"159852": {"quantity": "9999"}}),
            quantity_tolerance=Decimal("1"),
        )
        assert item(report, "159852", CHECK.POSITION_QUANTITY).status == STATUS.RECONCILED.value

    def test_tolerances_are_configurable_per_check(self):
        reconciler = AccountReconciler(
            quantity_tolerance=Decimal("5"),
            available_tolerance=Decimal("5"),
            cost_tolerance=Decimal("0.5"),
            value_tolerance=Decimal("0.5"),
            balance_tolerance=Decimal("1"),
        )
        report = reconciler.reconcile(
            broker_snapshot(),
            ledger_rows(**{"159852": {"quantity": "9997", "average_cost": "1.70"}}),
        )
        assert report.status == STATUS.RECONCILED.value


# ══════════════════════════════════════════════════════════════════
# §9 / §11 — read-only, and the order-safety consequence
# ══════════════════════════════════════════════════════════════════


class TestRollUpAndSideEffects:
    def test_the_report_rolls_up_to_the_worst_item(self):
        assert worst_status([]) == STATUS.RECONCILED.value
        assert worst_status([STATUS.RECONCILED.value]) == STATUS.RECONCILED.value
        assert (
            worst_status([STATUS.RECONCILED.value, STATUS.MISSING_LEDGER.value])
            == STATUS.MISSING_LEDGER.value
        )
        assert (
            worst_status([STATUS.MISSING_BROKER.value, STATUS.MISMATCH.value])
            == STATUS.MISMATCH.value
        )
        assert (
            worst_status([STATUS.MISMATCH.value, STATUS.INVALID.value])
            == STATUS.INVALID.value
        )

    def test_reconciling_touches_neither_side(self):
        """§9 — the reconciler only *reports*."""
        snapshot = broker_snapshot()
        rows = ledger_rows(**{"159852": {"quantity": "9900"}})
        before_positions = [p.quantity for p in snapshot.positions]
        before_ledger = [(r.symbol, r.quantity) for r in rows]
        reconcile(snapshot, rows)

        assert [p.quantity for p in snapshot.positions] == before_positions
        assert [(r.symbol, r.quantity) for r in rows] == before_ledger
        # and the broker's number was never nudged toward the ledger's
        assert {p.symbol: p.quantity for p in snapshot.positions}["159852"] == Decimal("10000")

    def test_the_report_serialises_for_the_api(self):
        report = reconcile(
            broker_snapshot(), ledger_rows(**{"159852": {"quantity": "9900"}})
        )
        payload = report.as_dict()
        assert payload["status"] == STATUS.MISMATCH.value
        assert payload["outcome"] == OUTCOME.FAIL.value
        assert payload["checked"] == payload["matched"] + payload["mismatch"]
        assert payload["timestamp"] == report.timestamp.isoformat()
        drifted = [
            i
            for i in payload["items"]
            if i["symbol"] == "159852" and i["check"] == "POSITION_QUANTITY"
        ][0]
        assert drifted == {
            "symbol": "159852",
            "check": "POSITION_QUANTITY",
            "broker_value": 10000.0,
            "ledger_value": 9900.0,
            "difference": 100.0,
            "status": STATUS.MISMATCH.value,
        }

    def test_a_missing_side_serialises_as_null_not_zero(self):
        payload = reconcile(
            broker_snapshot(), ledger_rows(drop=("513050",))
        ).as_dict()
        missing = [
            i for i in payload["items"] if i["status"] == STATUS.MISSING_LEDGER.value
        ][0]
        assert missing["ledger_value"] is None
        assert missing["difference"] is None

    def test_reconciliation_is_built_from_a_config(self):
        from services.account.sync.config import AccountSyncConfig

        reconciler = AccountReconciler.from_config(AccountSyncConfig())
        assert isinstance(reconciler, AccountReconciler)


class TestOrderSafety:
    """§11 — a failure blocks *new* Shadow/Live orders; Paper is untouched."""

    def test_a_pass_leaves_new_orders_open(self):
        harness = Harness()
        harness.sync()
        assert harness.service.reconciliation(ACCOUNT_ID)["outcome"] == OUTCOME.PASS.value
        assert harness.service.new_orders_blocked() is False

    def test_a_failure_blocks_new_orders(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts(quantity=1, available_quantity=1)
        harness.sync()
        assert harness.service.reconciliation(ACCOUNT_ID)["outcome"] == OUTCOME.FAIL.value
        assert harness.service.new_orders_blocked() is True

    def test_the_block_lifts_once_the_books_agree_again(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts(quantity=1)
        harness.sync()
        assert harness.service.new_orders_blocked() is True
        harness.restore_ledger()
        harness.sync()
        assert harness.service.new_orders_blocked() is False
        assert harness.service.state(ACCOUNT_ID) == "SYNCED"

    def test_a_failure_blocks_orders_but_must_not_blind_the_dashboard(self):
        """§11 blocks *new Shadow/Live orders* — reads keep working, and
        Paper Trading (an independent simulated account) is out of scope."""
        harness = Harness()
        harness.sync()
        harness.ledger_drifts(quantity=1)
        harness.sync()
        assert harness.service.new_orders_blocked() is True
        assert harness.service.new_orders_blocked(ACCOUNT_ID) is True
        assert harness.service.health(ACCOUNT_ID)["health"] == "BLOCKED"
        # the failure is visible *and* the account stays fully readable
        assert harness.service.balance(ACCOUNT_ID) is not None
        assert len(harness.service.positions(ACCOUNT_ID)) == 3

    def test_the_service_exposes_the_latest_report_per_account(self):
        harness = Harness()
        harness.sync()
        harness.ledger_drifts(quantity=1)
        snapshot = harness.sync()
        report = harness.service.report(ACCOUNT_ID)
        assert report.snapshot_id == snapshot.snapshot_id
        assert harness.service.reconciliation(ACCOUNT_ID) == report.as_dict()
        assert harness.service.reconciliation(ACCOUNT_ID) == snapshot.reconciliation
