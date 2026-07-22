"""
Stress test result.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StressResult:

    scenario_id: str

    before_value: float

    after_value: float

    pnl_change: float