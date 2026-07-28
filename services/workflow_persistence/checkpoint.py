from dataclasses import dataclass


@dataclass
class WorkflowCheckpoint:

    checkpoint_id: str
    workflow_id: str
    sequence: int
