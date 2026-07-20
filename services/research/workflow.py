"""
Research workflow.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchWorkflow:
    workflow_id: str
    name: str
    tasks: list[str]