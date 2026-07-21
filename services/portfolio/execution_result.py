"""
Execution result model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionResult:

    task_id: str

    success: bool

    result: dict