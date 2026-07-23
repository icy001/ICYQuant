"""
Market data AI tool.
"""

from .tool_result import ToolResult


class MarketDataTool:

    name = "market_data"

    def __init__(
        self,
        data_service,
    ):

        self.data_service = data_service

    def execute(
        self,
        arguments,
    ):

        symbol = arguments["symbol"]

        data = self.data_service.get(
            symbol
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=data,
            metadata={},
        )