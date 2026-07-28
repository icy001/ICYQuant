from dataclasses import dataclass


@dataclass
class WorkflowSnapshot:

    workflow_id: str
    checkpoint: str
    payload: dict
