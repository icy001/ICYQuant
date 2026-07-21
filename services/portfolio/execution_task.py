"""
Distributed execution task.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionTask:

    task_id: str

    task_type: str

    payload: dict