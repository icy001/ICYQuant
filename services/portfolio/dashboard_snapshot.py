"""
Dashboard snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardSnapshot:
    performance: dict
    risk: dict
    strategy: dict