"""
Scenario analysis model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:

    scenario_id: str

    name: str

    factors: dict