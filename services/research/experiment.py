"""
Experiment definition.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Experiment:

    experiment_id: str

    project_id: str = ""

    name: str = ""

    description: str = ""

    created_at: datetime = None

    owner: str = ""

    status: str = ""

    def __post_init__(self):
        if self.created_at is None:
            import datetime
            self.created_at = datetime.datetime.utcnow()