"""
Stress scenario model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StressScenario:

    scenario_id: str

    name: str

    market_shock: float