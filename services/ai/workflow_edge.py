"""
Workflow dependency edge.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowEdge:

    source: str

    target: str