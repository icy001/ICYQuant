"""
Pipeline task definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineTask:
    task_id: str
    name: str
    status: str = "PENDING"