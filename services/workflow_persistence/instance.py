from dataclasses import dataclass


@dataclass
class WorkflowInstance:

    workflow_id: str
    name: str
    state: str
