"""
Agent capability definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentCapability:

    name: str

    description: str

    version: str

    supported_tasks: list[str]