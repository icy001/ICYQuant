"""Agent registry for storing and looking up registered agents."""

from __future__ import annotations

from .agent import Agent


class AgentRegistry:
    """Central directory that stores all registered AI agents.

    Agents are indexed by their unique ID for fast lookup during
    orchestration and task assignment.
    """

    def __init__(self) -> None:
        self.agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent in the directory.

        Args:
            agent: The agent instance to register.
        """
        self.agents[agent.id] = agent

    def get(self, agent_id: str) -> Agent | None:
        """Retrieve an agent by ID.

        Args:
            agent_id: The unique agent identifier.

        Returns:
            The matching agent, or ``None`` if not found.
        """
        return self.agents.get(agent_id)
