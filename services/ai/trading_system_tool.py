"""
Trading system tool.
"""

from .tool_result import ToolResult


class TradingSystemTool:

    name = "trading_system"

    def __init__(
        self,
        trading_service,
    ):

        self.trading_service = trading_service

    def execute(
        self,
        arguments,
    ):

        result = self.trading_service.execute(
            arguments
        )

        return ToolResult(
            self.name,
            True,
            result,
            {},
        )