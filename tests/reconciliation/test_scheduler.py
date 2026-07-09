import pytest

from services.reconciliation.scheduler.reconciliation_scheduler import ReconciliationScheduler


class TestReconciliationScheduler:
    def test_schedule_daily(self):
        scheduler = ReconciliationScheduler()
        scheduler.schedule_daily("09:00", lambda: None)
        assert len(scheduler.jobs) == 1
        assert scheduler.jobs[0]["type"] == "DAILY"

    def test_schedule_hourly(self):
        scheduler = ReconciliationScheduler()
        scheduler.schedule_hourly(lambda: None, interval=2)
        assert len(scheduler.jobs) == 1
        assert scheduler.jobs[0]["type"] == "HOURLY"
        assert scheduler.jobs[0]["interval"] == 2
