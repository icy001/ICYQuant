"""
Workflow instance.
"""

from dataclasses import dataclass


@dataclass
class WorkflowInstance:

    instance_id: str

    workflow_id: str

    current_step: int = 0

    status: str = "CREATED"