"""Research agent registry for managing autonomous research agents."""

from __future__ import annotations

from .agent import ResearchAgent


class ResearchAgentRegistry:
    """Central directory for all research agents.

    Tracks agents by ID and provides lookup / listing capabilities.
    """

    def __init__(self) -> None:
        self.agents: dict[str, ResearchAgent] = {}

    def register(self, agent: ResearchAgent) -> None:
        """Register a research agent.

        Args:
            agent: The research agent instance.
        """
        self.agents[agent.id] = agent

    def list(self) -> list[ResearchAgent]:
        """Return all registered agents."""
        return list(self.agents.values())
