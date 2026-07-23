"""
Risk analysis tool.
"""

from .tool_result import ToolResult


class RiskAnalysisTool:

    name = "risk_analysis"

    def __init__(
        self,
        risk_service,
    ):

        self.risk_service = risk_service

    def execute(
        self,
        arguments,
    ):

        result = self.risk_service.analyze(
            arguments
        )

        return ToolResult(
            self.name,
            True,
            result,
            {},
        )