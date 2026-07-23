"""
Agent task model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTask:

    task_id: str

    agent_id: str

    objective: str

    priority: int