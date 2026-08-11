"""Risk Tools — platform adapter for Risk Engine operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Risk Engine for risk assessment, limits monitoring,
and compliance checks.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── RiskTools ──

class RiskTools:
    """Adapter providing Risk Engine tools for AI Agent.

    Exposes risk management operations as discoverable tools
    for risk assessment, limit monitoring, and pre-trade checks.

    Supports:
        - Risk metrics calculation
        - Position limits monitoring
        - Pre-trade risk checks
        - Stress testing
        - Risk report generation

    Usage:
        risk_tools = RiskTools()
        tools = risk_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize risk tools adapter."""
        self._initialized: bool = False
        logger.info("RiskTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("RiskTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("RiskTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all risk tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── risk.check_order ──
        definitions.append(
            ToolDefinition(
                name="risk.check_order",
                description="Pre-trade risk check for an order",
                version="1.0.0",
                category="risk",
                tags=["risk", "order", "pretrade", "check"],
                capability="risk",
                permission="risk.execute",
                risk_level="high",
                inputs=[
                    ToolInput(name="symbol", type="string", description="Ticker symbol", required=True),
                    ToolInput(name="side", type="string", description="Order side (buy/sell)", required=True),
                    ToolInput(name="quantity", type="number", description="Order quantity", required=True),
                    ToolInput(name="price", type="number", description="Order price"),
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="order_type", type="string", description="Order type", default="limit"),
                ],
                outputs=[
                    ToolOutput(name="approved", type="boolean", description="Whether order is approved"),
                    ToolOutput(name="risk_score", type="number", description="Risk score"),
                    ToolOutput(name="violations", type="array", description="Risk violations"),
                    ToolOutput(name="max_allowed_quantity", type="number", description="Max allowed quantity"),
                ],
                timeout_seconds=5.0,
                is_idempotent=True,
            )
        )

        # ── risk.position_limits ──
        definitions.append(
            ToolDefinition(
                name="risk.position_limits",
                description="Check current position against risk limits",
                version="1.0.0",
                category="risk",
                tags=["risk", "position", "limits"],
                capability="risk",
                permission="risk.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="limits", type="array", description="Limit checks"),
                    ToolOutput(name="breaches", type="array", description="Limit breaches"),
                    ToolOutput(name="overall_status", type="string", description="Overall status"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── risk.portfolio_var ──
        definitions.append(
            ToolDefinition(
                name="risk.portfolio_var",
                description="Calculate portfolio Value at Risk",
                version="1.0.0",
                category="risk",
                tags=["risk", "var", "value_at_risk"],
                capability="risk",
                permission="risk.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="confidence", type="number", description="Confidence level", default=0.95),
                    ToolInput(name="horizon", type="integer", description="Time horizon in days", default=1),
                    ToolInput(name="method", type="string", description="VaR method (historical/parametric/mc)", default="historical"),
                ],
                outputs=[
                    ToolOutput(name="var", type="number", description="Value at Risk"),
                    ToolOutput(name="cvar", type="number", description="Conditional VaR"),
                    ToolOutput(name="var_pct", type="number", description="VaR as percentage"),
                ],
                timeout_seconds=30.0,
                is_idempotent=True,
            )
        )

        # ── risk.stress_test ──
        definitions.append(
            ToolDefinition(
                name="risk.stress_test",
                description="Run stress test scenarios on portfolio",
                version="1.0.0",
                category="risk",
                tags=["risk", "stress_test", "scenario"],
                capability="risk",
                permission="risk.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="scenarios", type="array", description="Scenario names to run"),
                ],
                outputs=[
                    ToolOutput(name="results", type="array", description="Scenario results"),
                    ToolOutput(name="worst_case", type="object", description="Worst case scenario"),
                ],
                timeout_seconds=60.0,
                is_idempotent=False,
            )
        )

        # ── risk.exposure_report ──
        definitions.append(
            ToolDefinition(
                name="risk.exposure_report",
                description="Generate comprehensive risk exposure report",
                version="1.0.0",
                category="risk",
                tags=["risk", "exposure", "report"],
                capability="risk",
                permission="risk.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                    ToolInput(name="include_stress_test", type="boolean", description="Include stress tests", default=False),
                ],
                outputs=[
                    ToolOutput(name="report", type="object", description="Risk report data"),
                    ToolOutput(name="summary", type="string", description="Executive summary"),
                ],
                timeout_seconds=60.0,
                is_idempotent=False,
            )
        )

        # ── risk.liquidity_check ──
        definitions.append(
            ToolDefinition(
                name="risk.liquidity_check",
                description="Check position liquidity and market impact",
                version="1.0.0",
                category="risk",
                tags=["risk", "liquidity", "market_impact"],
                capability="risk",
                permission="risk.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="symbol", type="string", description="Ticker symbol", required=True),
                    ToolInput(name="quantity", type="number", description="Trade quantity", required=True),
                    ToolInput(name="side", type="string", description="Trade side (buy/sell)", required=True),
                ],
                outputs=[
                    ToolOutput(name="avg_daily_volume", type="number", description="Average daily volume"),
                    ToolOutput(name="volume_participation", type="number", description="Volume participation rate"),
                    ToolOutput(name="estimated_impact_bps", type="number", description="Estimated market impact in bps"),
                    ToolOutput(name="liquidity_score", type="number", description="Liquidity score (0-100)"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── risk.concentration ──
        definitions.append(
            ToolDefinition(
                name="risk.concentration",
                description="Analyze portfolio concentration risk",
                version="1.0.0",
                category="risk",
                tags=["risk", "concentration", "diversification"],
                capability="risk",
                permission="risk.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="portfolio_id", type="string", description="Portfolio ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="top_holdings", type="array", description="Top concentration"),
                    ToolOutput(name="hhi", type="number", description="Herfindahl-Hirschman Index"),
                    ToolOutput(name="sector_concentration", type="object", description="Sector concentration"),
                    ToolOutput(name="single_stock_risk", type="array", description="Single stock risk"),
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
