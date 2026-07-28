"""Agent data model for the Multi-Agent Collaboration Engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Agent:
    """An AI agent with a specific role and capabilities.

    Attributes:
        id: Unique identifier for the agent.
        role: The agent's role (e.g. "research", "risk", "strategy").
        capability: List of capabilities the agent supports.
    """

    id: str
    role: str
    capability: list[str] = field(default_factory=list)
