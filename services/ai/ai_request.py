"""
AI request model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AIRequest:

    request_id: str

    task_type: str

    created_at: datetime

    payload: dict