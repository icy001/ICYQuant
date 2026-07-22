"""
Distributed backtest task.
"""

from dataclasses import dataclass
from enum import Enum


class TaskStatus(Enum):

    PENDING = "PENDING"

    RUNNING = "RUNNING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"


@dataclass
class DistributedTask:

    task_id: str

    workflow_id: str

    payload: dict

    status: TaskStatus = TaskStatus.PENDING