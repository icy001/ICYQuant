"""Market Data Tools — platform adapter for Market Data operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Market Data system for real-time and historical data access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── MarketDataTools ──

class MarketDataTools:
    """Adapter providing Market Data tools for AI Agent.

    Exposes market data operations as discoverable tools for
    querying prices, bars, order books, and market statistics.

    Supports:
        - Real-time price quotes
        - Historical bar data
        - Order book depth
        - Market statistics
        - Instrument reference data

    Usage:
        md_tools = MarketDataTools()
        tools = md_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize market data tools adapter."""
        self._initialized: bool = False
        logger.info("MarketDataTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("MarketDataTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("MarketDataTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all market data tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── market.get_quote ──
        definitions.append(
            ToolDefinition(
                name="market.get_quote",
                description="Get real-time quote for a symbol",
                version="1.0.0",
                category="market_data",
                tags=["market", "quote", "realtime"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="symbol", type="string", description="Ticker symbol", required=True),
                ],
                outputs=[
                    ToolOutput(name="symbol", type="string", description="Symbol"),
                    ToolOutput(name="price", type="number", description="Last price"),
                    ToolOutput(name="volume", type="number", description="Volume"),
                    ToolOutput(name="change_pct", type="number", description="Change percentage"),
                    ToolOutput(name="timestamp", type="string", description="Quote timestamp"),
                ],
                timeout_seconds=5.0,
                is_idempotent=True,
            )
        )

        # ── market.get_bars ──
        definitions.append(
            ToolDefinition(
                name="market.get_bars",
                description="Get historical bar (OHLCV) data",
                version="1.0.0",
                category="market_data",
                tags=["market", "bars", "historical", "ohlcv"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="symbol", type="string", description="Ticker symbol", required=True),
                    ToolInput(name="frequency", type="string", description="Bar frequency (1m,5m,1h,1d)", required=True),
                    ToolInput(name="start_date", type="string", description="Start date (YYYY-MM-DD)", required=True),
                    ToolInput(name="end_date", type="string", description="End date (YYYY-MM-DD)", required=True),
                    ToolInput(name="adjustment", type="string", description="Price adjustment", default="forward"),
                ],
                outputs=[
                    ToolOutput(name="symbol", type="string", description="Symbol"),
                    ToolOutput(name="bars", type="array", description="OHLCV bar data"),
                    ToolOutput(name="count", type="integer", description="Number of bars"),
                ],
                timeout_seconds=30.0,
                is_idempotent=True,
            )
        )

        # ── market.get_order_book ──
        definitions.append(
            ToolDefinition(
                name="market.get_order_book",
                description="Get order book depth for a symbol",
                version="1.0.0",
                category="market_data",
                tags=["market", "orderbook", "depth"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="symbol", type="string", description="Ticker symbol", required=True),
                    ToolInput(name="depth", type="integer", description="Number of levels", default=10),
                ],
                outputs=[
                    ToolOutput(name="bids", type="array", description="Bid levels"),
                    ToolOutput(name="asks", type="array", description="Ask levels"),
                    ToolOutput(name="timestamp", type="string", description="Snapshot timestamp"),
                ],
                timeout_seconds=5.0,
                is_idempotent=True,
            )
        )

        # ── market.search_instruments ──
        definitions.append(
            ToolDefinition(
                name="market.search_instruments",
                description="Search for financial instruments",
                version="1.0.0",
                category="market_data",
                tags=["market", "search", "instrument"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="query", type="string", description="Search keyword", required=True),
                    ToolInput(name="asset_type", type="string", description="Asset type filter"),
                    ToolInput(name="market", type="string", description="Market filter (e.g., SH, SZ)"),
                    ToolInput(name="limit", type="integer", description="Max results", default=20),
                ],
                outputs=[
                    ToolOutput(name="results", type="array", description="Matching instruments"),
                    ToolOutput(name="total", type="integer", description="Total matches"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── market.get_market_snapshot ──
        definitions.append(
            ToolDefinition(
                name="market.get_market_snapshot",
                description="Get market-wide snapshot (indices, breadth, sentiment)",
                version="1.0.0",
                category="market_data",
                tags=["market", "snapshot", "overview"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="market", type="string", description="Market code", default="CN"),
                ],
                outputs=[
                    ToolOutput(name="indices", type="array", description="Major indices"),
                    ToolOutput(name="breadth", type="object", description="Market breadth data"),
                    ToolOutput(name="timestamp", type="string", description="Snapshot time"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── market.subscribe ──
        definitions.append(
            ToolDefinition(
                name="market.subscribe",
                description="Subscribe to real-time market data stream",
                version="1.0.0",
                category="market_data",
                tags=["market", "subscribe", "stream"],
                capability="market_data",
                permission="market_data.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="symbols", type="array", description="Symbols to subscribe", required=True),
                    ToolInput(name="data_type", type="string", description="Data type (quote,trade,depth)", default="quote"),
                ],
                outputs=[
                    ToolOutput(name="subscription_id", type="string", description="Subscription ID"),
                    ToolOutput(name="status", type="string", description="Subscription status"),
                ],
                timeout_seconds=10.0,
                is_idempotent=False,
            )
        )

        return definitions

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get adapter status."""
        return {
            "tool_count": len(self.get_tool_definitions()),
            "initialized": self._initialized,
        }
