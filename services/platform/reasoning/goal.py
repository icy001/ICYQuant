"""
Goal model.
"""

from dataclasses import dataclass, field


@dataclass
class Goal:

    goal_id: str

    description: str

    priority: int = 1

    metadata: dict = field(default_factory=dict)