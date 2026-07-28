"""Multi-agent service — the top-level entry point."""

from __future__ import annotations

from .orchestrator import AgentOrchestrator


class MultiAgentService:
    """Top-level service that accepts user tasks and delegates to the
    agent orchestrator.

    This is the primary API surface for the Multi-Agent Collaboration
    Engine.
    """

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orchestrator = orchestrator

    def run(self, task: list[str]) -> dict:
        """Execute a decomposed task plan.

        Args:
            task: Ordered list of agent roles to run.

        Returns:
            The orchestrator's consolidated result.
        """
        return self.orchestrator.execute(task)
