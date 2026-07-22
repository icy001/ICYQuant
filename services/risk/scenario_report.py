"""
Scenario report.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioReport:

    scenario_id: str

    before: float

    after: float

    pnl: float