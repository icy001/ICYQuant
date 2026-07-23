"""
Execution task model.
"""

from dataclasses import dataclass


@dataclass
class ExecutionTask:

    task_id: str

    action: str

    target: str

    parameters: dict