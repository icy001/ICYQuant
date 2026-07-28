from dataclasses import dataclass


@dataclass
class WorkflowVersion:

    version: str
    active: bool = True
