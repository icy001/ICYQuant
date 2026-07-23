"""
AI task framework.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AITask:

    task_id: str

    task_type: str

    priority: int