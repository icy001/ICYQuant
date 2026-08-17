import pytest
from decimal import Decimal

from services.reconciliation.models.difference import Difference
from services.reconciliation.models.difference import DifferenceType
from services.reconciliation.models.report import ReconciliationReport


class TestReconciliationReport:
    def test_report_is_healthy(self):
        report = ReconciliationReport()
        assert report.healthy

    def test_report_has_difference(self):
        report = ReconciliationReport()
        report.differences.append(
            Difference(
                type=DifferenceType.QUANTITY_MISMATCH,
                expected=Decimal("100"),
                actual=Decimal("99"),
                delta=Decimal("-1"),
            )
        )
        assert not report.healthy

    def test_report_multiple_differences(self):
        report = ReconciliationReport()
        report.differences.extend([
            Difference(
                type=DifferenceType.QUANTITY_MISMATCH,
                expected=Decimal("100"),
                actual=Decimal("99"),
                delta=Decimal("-1"),
            ),
            Difference(
                type=DifferenceType.AVERAGE_PRICE_MISMATCH,
                expected=Decimal("1000"),
                actual=Decimal("950"),
                delta=Decimal("-50"),
            ),
        ])
        assert len(report.differences) == 2
        assert not report.healthy

    def test_report_created_at(self):
        report = ReconciliationReport()
        assert report.created_at is not None
