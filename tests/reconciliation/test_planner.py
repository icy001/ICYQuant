from decimal import Decimal

from services.reconciliation.models.difference import (
    Difference,
    DifferenceType,
)
from services.reconciliation.models.repair import RepairActionType
from services.reconciliation.models.result import ReconciliationResult
from services.reconciliation.models.status import ReconciliationStatus
from services.reconciliation.planner import RepairPlanner


def make_difference(difference_type, expected, actual):
    return Difference(
        type=difference_type,
        expected=expected,
        actual=actual,
        delta=actual - expected,
    )


def make_result(status, differences=()):
    return ReconciliationResult(
        symbol="AAPL",
        status=status,
        differences=tuple(differences),
    )


def test_matched_requires_no_action():
    result = make_result(ReconciliationStatus.MATCHED)

    plan = RepairPlanner().plan(result)

    assert plan.action == RepairActionType.NO_ACTION
    assert plan.reason == "Reconciliation matched"
    assert plan.differences == ()


def test_quantity_mismatch_creates_rebuild_plan():
    differences = (
        make_difference(
            DifferenceType.QUANTITY_MISMATCH,
            Decimal("100"),
            Decimal("80"),
        ),
    )
    result = make_result(ReconciliationStatus.MISMATCH, differences)

    plan = RepairPlanner().plan(result)

    assert plan.action == RepairActionType.REBUILD_POSITION
    assert plan.differences == differences


def test_multiple_mismatch_creates_rebuild_plan():
    differences = (
        make_difference(
            DifferenceType.QUANTITY_MISMATCH,
            Decimal("100"),
            Decimal("80"),
        ),
        make_difference(
            DifferenceType.REALIZED_PNL_MISMATCH,
            Decimal("1200"),
            Decimal("900"),
        ),
    )
    result = make_result(ReconciliationStatus.MISMATCH, differences)

    plan = RepairPlanner().plan(result)

    assert plan.action == RepairActionType.REBUILD_POSITION
    assert plan.differences == differences


def test_unknown_mismatch_requires_manual_review():
    differences = (
        make_difference(
            DifferenceType.UNKNOWN_MISMATCH,
            Decimal("0"),
            Decimal("1"),
        ),
    )
    result = make_result(ReconciliationStatus.MISMATCH, differences)

    plan = RepairPlanner().plan(result)

    assert plan.action == RepairActionType.MANUAL_REVIEW
    assert plan.reason == "Unknown reconciliation difference requires manual review"
    assert plan.differences == differences


def test_mismatch_without_differences_requires_manual_review():
    result = make_result(ReconciliationStatus.MISMATCH)

    plan = RepairPlanner().plan(result)

    assert plan.action == RepairActionType.MANUAL_REVIEW
    assert plan.reason == "Mismatch detected without classified differences"
    assert plan.differences == ()
