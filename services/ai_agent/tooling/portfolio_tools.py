"""Portfolio Tools — platform adapter for Portfolio Engine operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Portfolio Engine for position management and portfolio analytics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── PortfolioTools ──

class PortfolioTools:
    """Adapter providing Portfolio Engine tools for AI Agent.

    Exposes portfolio management operations as discoverable tools
    for position tracking, portfolio analytics, and rebalancing.

    Supports:
        - Portfolio summary and composition
        - Position management
        - Portfolio analytics (VaR, exposure, attribution)
        - Rebalancing suggestions
        - Trade reconciliation

    Usage:
        pf_tools = PortfolioTools()
        tools = pf_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize portfolio tools adapter."""
        self._initialized: bool = False
        logger.info("PortfolioTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("PortfolioTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("PortfolioTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all portfolio tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── portfolio.summary ──
        definitions.append(
            ToolDefinition(
                name="portfolio.summary",
                description="Get portfolio summary with key metrics",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "summary", "overview"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID"),
                ],
                outputs=[
                    ToolOutput(name="total_value", type="number", description="Total portfolio value"),
                    ToolOutput(name="cash", type="number", description="Cash balance"),
                    ToolOutput(name="market_value", type="number", description="Market value of holdings"),
                    ToolOutput(name="daily_pnl", type="number", description="Daily PnL"),
                    ToolOutput(name="total_return", type="number", description="Total return"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── portfolio.positions ──
        definitions.append(
            ToolDefinition(
                name="portfolio.positions",
                description="Get current portfolio positions",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "positions", "holdings"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID"),
                    ToolInput(name="sort_by", type="string", description="Sort field", default="weight"),
                ],
                outputs=[
                    ToolOutput(name="positions", type="array", description="Position list"),
                    ToolOutput(name="total_positions", type="integer", description="Position count"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── portfolio.exposure ──
        definitions.append(
            ToolDefinition(
                name="portfolio.exposure",
                description="Get portfolio exposure breakdown",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "exposure", "risk"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID"),
                    ToolInput(name="breakdown_by", type="string", description="Breakdown dimension (sector/industry/market)", default="sector"),
                ],
                outputs=[
                    ToolOutput(name="exposure", type="array", description="Exposure breakdown"),
                    ToolOutput(name="total_exposure", type="number", description="Total exposure"),
                    ToolOutput(name="net_exposure", type="number", description="Net exposure"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── portfolio.risk_metrics ──
        definitions.append(
            ToolDefinition(
                name="portfolio.risk_metrics",
                description="Calculate portfolio risk metrics",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "risk", "var", "volatility"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID"),
                    ToolInput(name="confidence", type="number", description="VaR confidence level", default=0.95),
                ],
                outputs=[
                    ToolOutput(name="var", type="number", description="Value at Risk"),
                    ToolOutput(name="cvar", type="number", description="Conditional VaR"),
                    ToolOutput(name="volatility", type="number", description="Portfolio volatility"),
                    ToolOutput(name="beta", type="number", description="Portfolio beta"),
                    ToolOutput(name="sharpe_ratio", type="number", description="Sharpe ratio"),
                ],
                timeout_seconds=30.0,
                is_idempotent=True,
            )
        )

        # ── portfolio.rebalance ──
        definitions.append(
            ToolDefinition(
                name="portfolio.rebalance",
                description="Generate rebalancing suggestions",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "rebalance", "optimize"],
                capability="portfolio",
                permission="portfolio.write",
                risk_level="medium",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="target_weights", type="object", description="Target weight allocation"),
                    ToolInput(name="method", type="string", description="Rebalancing method", default="threshold"),
                    ToolInput(name="threshold", type="number", description="Rebalance threshold", default=0.05),
                ],
                outputs=[
                    ToolOutput(name="trades", type="array", description="Suggested trades"),
                    ToolOutput(name="estimated_cost", type="number", description="Estimated transaction cost"),
                    ToolOutput(name="drift", type="number", description="Weight drift"),
                ],
                timeout_seconds=60.0,
                is_idempotent=False,
            )
        )

        # ── portfolio.attribution ──
        definitions.append(
            ToolDefinition(
                name="portfolio.attribution",
                description="Get performance attribution analysis",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "attribution", "performance"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="start_date", type="string", description="Start date", required=True),
                    ToolInput(name="end_date", type="string", description="End date", required=True),
                ],
                outputs=[
                    ToolOutput(name="sector_attribution", type="array", description="Sector-level attribution"),
                    ToolOutput(name="factor_attribution", type="object", description="Factor-level attribution"),
                    ToolOutput(name="selection_effect", type="number", description="Security selection effect"),
                    ToolOutput(name="allocation_effect", type="number", description="Asset allocation effect"),
                ],
                timeout_seconds=30.0,
                is_idempotent=True,
            )
        )

        # ── portfolio.history ──
        definitions.append(
            ToolDefinition(
                name="portfolio.history",
                description="Get portfolio value history",
                version="1.0.0",
                category="portfolio",
                tags=["portfolio", "history", "nav"],
                capability="portfolio",
                permission="portfolio.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="start_date", type="string", description="Start date", required=True),
                    ToolInput(name="end_date", type="string", description="End date", required=True),
                ],
                outputs=[
                    ToolOutput(name="nav_series", type="array", description="NAV time series"),
                    ToolOutput(name="benchmark_series", type="array", description="Benchmark time series"),
                ],
                timeout_seconds=20.0,
                is_idempotent=True,
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
