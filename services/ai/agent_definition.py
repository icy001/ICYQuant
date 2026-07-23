"""
AI Agent definition.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:

    agent_id: str

    name: str

    role: str

    description: str