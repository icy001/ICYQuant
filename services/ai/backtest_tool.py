"""
Backtest execution tool.
"""

from .tool_result import ToolResult


class BacktestTool:

    name = "backtest"

    def __init__(
        self,
        backtest_service,
    ):

        self.backtest_service = backtest_service

    def execute(
        self,
        arguments,
    ):

        result = self.backtest_service.run(
            arguments
        )

        return ToolResult(
            self.name,
            True,
            result,
            {},
        )