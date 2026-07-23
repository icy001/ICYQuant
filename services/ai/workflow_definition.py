"""
AI workflow definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowDefinition:

    workflow_id: str

    name: str

    description: str

    version: str