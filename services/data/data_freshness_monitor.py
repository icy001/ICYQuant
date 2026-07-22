"""
Freshness monitor.
"""

from datetime import datetime


class DataFreshnessMonitor:

    def evaluate(
        self,
        updated_at,
    ):

        age = (
            datetime.utcnow()
            - updated_at
        ).total_seconds()

        return {
            "age_seconds": age,
            "healthy": age < 60,
        }