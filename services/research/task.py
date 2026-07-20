"""
Workflow task.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowTask:
    task_id: str
    name: str
    status: str