"""
Research team model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchTeam:

    team_id: str

    name: str

    description: str