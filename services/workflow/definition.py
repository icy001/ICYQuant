from dataclasses import dataclass


@dataclass
class WorkflowDefinition:

    workflow_id: str
    name: str
    tasks: list
