"""
Workflow states.
"""

from enum import Enum


class WorkflowState(Enum):

    CREATED = "CREATED"

    PREPARING = "PREPARING"

    RUNNING = "RUNNING"

    ANALYZING = "ANALYZING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"