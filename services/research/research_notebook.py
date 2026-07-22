"""
Research notebook model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ResearchNotebook:

    notebook_id: str

    name: str

    project_id: str

    created_at: datetime

    content: str