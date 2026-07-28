from dataclasses import dataclass


@dataclass
class WorkflowTask:

    task_id: str
    name: str
    action: str
    status: str
