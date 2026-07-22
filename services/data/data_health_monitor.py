"""
Data health monitor.
"""

from datetime import datetime

from .data_health import DataHealth


class DataHealthMonitor:

    def check(
        self,
        component,
        healthy=True,
    ):

        return DataHealth(
            component=component,
            status="UP" if healthy else "DOWN",
            checked_at=datetime.utcnow(),
            message="OK" if healthy else "Unavailable",
        )