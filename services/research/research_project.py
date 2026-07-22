"""
Research project model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ResearchProject:

    project_id: str

    name: str

    description: str

    created_at: datetime

    status: str