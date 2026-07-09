import pytest

from services.reconciliation.models.difference import Difference
from services.reconciliation.models.report import ReconciliationReport
from services.reconciliation.models.types import DifferenceType


class TestReconciliationReport:
    def test_report_is_healthy(self):
        report = ReconciliationReport()
        assert report.healthy

    def test_report_has_difference(self):
        report = ReconciliationReport()
        report.differences.append(
            Difference(
                diff_type=DifferenceType.POSITION,
                entity_id="AAPL",
                expected=100.0,
                actual=99.0,
            )
        )
        assert not report.healthy

    def test_report_multiple_differences(self):
        report = ReconciliationReport()
        report.differences.extend([
            Difference(
                diff_type=DifferenceType.POSITION,
                entity_id="AAPL",
                expected=100.0,
                actual=99.0,
            ),
            Difference(
                diff_type=DifferenceType.CASH,
                entity_id="user1",
                expected=1000.0,
                actual=950.0,
            ),
        ])
        assert len(report.differences) == 2
        assert not report.healthy

    def test_report_created_at(self):
        report = ReconciliationReport()
        assert report.created_at is not None
