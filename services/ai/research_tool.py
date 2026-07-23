"""
Research knowledge tool.
"""

from .tool_result import ToolResult


class ResearchTool:

    name = "research"

    def __init__(
        self,
        research_service,
    ):

        self.research_service = research_service

    def execute(
        self,
        arguments,
    ):

        result = self.research_service.search(
            arguments["query"]
        )

        return ToolResult(
            self.name,
            True,
            result,
            {},
        )