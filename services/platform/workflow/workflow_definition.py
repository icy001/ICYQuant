"""
Workflow definition.
"""

from dataclasses import dataclass, field


@dataclass
class WorkflowDefinition:

    workflow_id: str

    name: str

    steps: list = field(default_factory=list)

    metadata: dict = field(default_factory=dict)