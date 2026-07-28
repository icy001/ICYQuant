from dataclasses import dataclass


@dataclass
class TaskNode:
    task_id: str
    name: str
    status: str
