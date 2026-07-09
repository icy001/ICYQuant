from datetime import datetime, timedelta
from typing import Callable, Optional


class ReconciliationScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []

    def schedule_daily(
        self,
        time: str,
        task: Callable,
    ) -> None:
        self.jobs.append(
            {
                "type": "DAILY",
                "time": time,
                "task": task,
            }
        )

    def schedule_hourly(
        self,
        task: Callable,
        interval: int = 1,
    ) -> None:
        self.jobs.append(
            {
                "type": "HOURLY",
                "interval": interval,
                "task": task,
            }
        )

    def schedule_cron(
        self,
        cron_expression: str,
        task: Callable,
    ) -> None:
        self.jobs.append(
            {
                "type": "CRON",
                "expression": cron_expression,
                "task": task,
            }
        )

    def run_pending(self) -> None:
        pass
