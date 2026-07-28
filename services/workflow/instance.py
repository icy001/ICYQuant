from dataclasses import dataclass


@dataclass
class WorkflowInstance:
    instance_id: str
    workflow_id: str
    state: str
