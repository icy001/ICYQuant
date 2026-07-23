"""
Workflow DAG node.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowNode:

    node_id: str

    task_type: str

    agent_id: str