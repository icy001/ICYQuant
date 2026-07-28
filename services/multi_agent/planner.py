"""Task planner for breaking complex tasks into sub-tasks."""

from __future__ import annotations


class TaskPlanner:
    """Plans and decomposes complex user tasks into sub-tasks.

    The planner determines which agent roles are required and in what
    order they should execute, supporting sequential, parallel, and
    conditional workflows.
    """

    def plan(self, task: str) -> list[str]:
        """Decompose a task into a sequence of agent roles.

        Args:
            task: The high-level user request.

        Returns:
            Ordered list of agent roles to execute.
        """
        # For the initial implementation, return a standard pipeline.
        # Future versions will use LLM-based reasoning to dynamically
        # decompose arbitrary tasks.
        return [
            "research",
            "risk",
            "strategy",
        ]
