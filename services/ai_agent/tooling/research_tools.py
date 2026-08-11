"""Research Tools — platform adapter for Research Platform operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Research Platform for backtesting, analysis, and
quantitative research.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── ResearchTools ──

class ResearchTools:
    """Adapter providing Research Platform tools for AI Agent.

    Exposes research and backtesting operations as discoverable
    tools for the agent to use autonomously.

    Supports:
        - Backtest execution and management
        - Parameter optimization
        - Factor analysis
        - Performance reporting
        - Research notebook integration

    Usage:
        research_tools = ResearchTools()
        tools = research_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize research tools adapter."""
        self._initialized: bool = False
        logger.info("ResearchTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("ResearchTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("ResearchTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all research tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── backtest.run ──
        definitions.append(
            ToolDefinition(
                name="backtest.run",
                description="Run a strategy backtest with specified parameters",
                version="1.0.0",
                category="research",
                tags=["research", "backtest", "strategy"],
                capability="backtest",
                permission="research.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy identifier", required=True),
                    ToolInput(name="start_date", type="string", description="Start date (YYYY-MM-DD)", required=True),
                    ToolInput(name="end_date", type="string", description="End date (YYYY-MM-DD)", required=True),
                    ToolInput(name="initial_capital", type="number", description="Initial capital", default=1000000),
                    ToolInput(name="benchmark", type="string", description="Benchmark symbol", default="000300.SH"),
                    ToolInput(name="params", type="object", description="Strategy parameters override"),
                ],
                outputs=[
                    ToolOutput(name="backtest_id", type="string", description="Backtest run ID"),
                    ToolOutput(name="sharpe_ratio", type="number", description="Sharpe ratio"),
                    ToolOutput(name="annual_return", type="number", description="Annualized return"),
                    ToolOutput(name="max_drawdown", type="number", description="Maximum drawdown"),
                    ToolOutput(name="win_rate", type="number", description="Win rate"),
                ],
                timeout_seconds=300.0,
                is_idempotent=False,
            )
        )

        # ── backtest.status ──
        definitions.append(
            ToolDefinition(
                name="backtest.status",
                description="Get the status of a backtest run",
                version="1.0.0",
                category="research",
                tags=["research", "backtest", "status"],
                capability="backtest",
                permission="research.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="backtest_id", type="string", description="Backtest run ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Backtest status"),
                    ToolOutput(name="progress", type="number", description="Progress percentage"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── backtest.results ──
        definitions.append(
            ToolDefinition(
                name="backtest.results",
                description="Get detailed results of a completed backtest",
                version="1.0.0",
                category="research",
                tags=["research", "backtest", "results"],
                capability="backtest",
                permission="research.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="backtest_id", type="string", description="Backtest run ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="metrics", type="object", description="Performance metrics"),
                    ToolOutput(name="trades", type="array", description="Trade list"),
                    ToolOutput(name="equity_curve", type="array", description="Equity curve data"),
                ],
                timeout_seconds=30.0,
                is_idempotent=True,
            )
        )

        # ── optimize.run ──
        definitions.append(
            ToolDefinition(
                name="optimize.run",
                description="Run parameter optimization for a strategy",
                version="1.0.0",
                category="research",
                tags=["research", "optimize", "parameter"],
                capability="backtest",
                permission="research.execute",
                risk_level="medium",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy identifier", required=True),
                    ToolInput(name="param_space", type="object", description="Parameter search space", required=True),
                    ToolInput(name="objective", type="string", description="Optimization objective", default="sharpe_ratio"),
                    ToolInput(name="start_date", type="string", description="Start date", required=True),
                    ToolInput(name="end_date", type="string", description="End date", required=True),
                    ToolInput(name="method", type="string", description="Optimization method", default="grid"),
                ],
                outputs=[
                    ToolOutput(name="optimization_id", type="string", description="Optimization run ID"),
                    ToolOutput(name="best_params", type="object", description="Best parameters found"),
                    ToolOutput(name="best_score", type="number", description="Best objective score"),
                ],
                timeout_seconds=600.0,
                is_idempotent=False,
            )
        )

        # ── factor.analyze ──
        definitions.append(
            ToolDefinition(
                name="factor.analyze",
                description="Analyze a factor's predictive power",
                version="1.0.0",
                category="research",
                tags=["research", "factor", "analysis"],
                capability="research",
                permission="research.execute",
                risk_level="low",
                inputs=[
                    ToolInput(name="factor_id", type="string", description="Factor identifier", required=True),
                    ToolInput(name="universe", type="string", description="Stock universe"),
                    ToolInput(name="start_date", type="string", description="Start date", required=True),
                    ToolInput(name="end_date", type="string", description="End date", required=True),
                ],
                outputs=[
                    ToolOutput(name="ic_mean", type="number", description="Mean information coefficient"),
                    ToolOutput(name="ic_ir", type="number", description="IC information ratio"),
                    ToolOutput(name="factor_return", type="number", description="Factor return"),
                ],
                timeout_seconds=120.0,
                is_idempotent=False,
            )
        )

        # ── research.report ──
        definitions.append(
            ToolDefinition(
                name="research.report",
                description="Generate a research report from analysis results",
                version="1.0.0",
                category="research",
                tags=["research", "report", "analysis"],
                capability="research",
                permission="research.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="analysis_id", type="string", description="Analysis identifier", required=True),
                    ToolInput(name="format", type="string", description="Report format", default="pdf"),
                    ToolInput(name="sections", type="array", description="Sections to include"),
                ],
                outputs=[
                    ToolOutput(name="report_id", type="string", description="Report identifier"),
                    ToolOutput(name="report_url", type="string", description="Report download URL"),
                ],
                timeout_seconds=60.0,
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
