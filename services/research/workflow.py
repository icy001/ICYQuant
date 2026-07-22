"""
Research workflow.
"""

from dataclasses import dataclass


@dataclass
class ResearchWorkflow:

    workflow_id: str

    project_id: str = ""

    notebook_id: str = ""

    state: str = ""

    name: str = ""

    tasks: list = None

    def __post_init__(self):
        if self.tasks is None:
            self.tasks = []