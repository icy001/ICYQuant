"""
Market health monitor.
"""

from __future__ import annotations

from .statistics import MarketStatistics
from .status import MarketStatus


class MarketHealthMonitor:
    def __init__(self):
        self.status = MarketStatus.STARTING
        self.statistics = MarketStatistics()

    def mark_running(self):
        self.status = MarketStatus.RUNNING

    def mark_degraded(self):
        self.status = MarketStatus.DEGRADED

    def mark_stopped(self):
        self.status = MarketStatus.STOPPED