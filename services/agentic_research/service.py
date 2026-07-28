"""Agentic research service — top-level entry point."""

from __future__ import annotations

from .planner import ResearchTaskPlanner


class AgenticResearchService:
    """Top-level service for the AI Agentic Research Platform.

    Accepts research topics and delegates to the task planner to
    decompose and route work across specialized research agents.
    """

    def __init__(self, planner: ResearchTaskPlanner) -> None:
        self.planner = planner

    def research(self, topic: str) -> list[str]:
        """Initiate a research workflow for a given topic.

        Args:
            topic: The research topic (e.g. company ticker).

        Returns:
            Ordered list of analysis modules to execute.
        """
        return self.planner.plan(topic)
