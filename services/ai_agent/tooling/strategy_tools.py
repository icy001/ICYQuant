"""Strategy Tools — platform adapter for Strategy Runtime operations.

Provides tool definitions that bridge the AI Agent with the
ICYQuant Strategy Runtime for strategy management and execution.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.ai_agent.tooling.tool_definition import ToolDefinition, ToolInput, ToolOutput

logger = logging.getLogger(__name__)


# ── StrategyTools ──

class StrategyTools:
    """Adapter providing Strategy Runtime tools for AI Agent.

    Exposes strategy management operations as discoverable tools
    for creating, configuring, executing, and monitoring strategies.

    Supports:
        - Strategy creation and configuration
        - Strategy execution (paper/live)
        - Strategy status monitoring
        - Strategy performance tracking
        - Strategy parameter management

    Usage:
        strat_tools = StrategyTools()
        tools = strat_tools.get_tool_definitions()
        registry.register_tools(tools)
    """

    def __init__(self) -> None:
        """Initialize strategy tools adapter."""
        self._initialized: bool = False
        logger.info("StrategyTools adapter created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
        logger.info("StrategyTools initialized")

    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        self._initialized = False
        logger.info("StrategyTools shutdown complete")

    # ── Tool Definitions ──

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """Get all strategy tool definitions.

        Returns:
            List of ToolDefinition objects.
        """
        definitions: List[ToolDefinition] = []

        # ── strategy.list ──
        definitions.append(
            ToolDefinition(
                name="strategy.list",
                description="List all available strategies",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "list"],
                capability="strategy",
                permission="strategy.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="category", type="string", description="Strategy category"),
                    ToolInput(name="status", type="string", description="Filter by status"),
                    ToolInput(name="limit", type="integer", description="Max results", default=50),
                ],
                outputs=[
                    ToolOutput(name="strategies", type="array", description="Strategy list"),
                    ToolOutput(name="total", type="integer", description="Total count"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── strategy.get ──
        definitions.append(
            ToolDefinition(
                name="strategy.get",
                description="Get detailed strategy configuration",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "detail", "config"],
                capability="strategy",
                permission="strategy.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="strategy", type="object", description="Strategy details"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── strategy.create ──
        definitions.append(
            ToolDefinition(
                name="strategy.create",
                description="Create a new strategy instance",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "create"],
                capability="strategy",
                permission="strategy.write",
                risk_level="medium",
                inputs=[
                    ToolInput(name="name", type="string", description="Strategy name", required=True),
                    ToolInput(name="description", type="string", description="Strategy description"),
                    ToolInput(name="strategy_type", type="string", description="Strategy type identifier", required=True),
                    ToolInput(name="params", type="object", description="Strategy parameters", required=True),
                    ToolInput(name="universe", type="array", description="Stock universe"),
                    ToolInput(name="benchmark", type="string", description="Benchmark symbol"),
                ],
                outputs=[
                    ToolOutput(name="strategy_id", type="string", description="Created strategy ID"),
                    ToolOutput(name="status", type="string", description="Creation status"),
                ],
                timeout_seconds=30.0,
                is_idempotent=False,
            )
        )

        # ── strategy.update_params ──
        definitions.append(
            ToolDefinition(
                name="strategy.update_params",
                description="Update strategy parameters",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "update", "params"],
                capability="strategy",
                permission="strategy.write",
                risk_level="medium",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy ID", required=True),
                    ToolInput(name="params", type="object", description="Updated parameters", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Update status"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── strategy.start ──
        definitions.append(
            ToolDefinition(
                name="strategy.start",
                description="Start a strategy in paper or live mode",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "start", "execute"],
                capability="strategy",
                permission="strategy.execute",
                risk_level="high",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy ID", required=True),
                    ToolInput(name="mode", type="string", description="Execution mode (paper/live)", default="paper"),
                    ToolInput(name="capital", type="number", description="Allocated capital"),
                ],
                outputs=[
                    ToolOutput(name="execution_id", type="string", description="Execution ID"),
                    ToolOutput(name="status", type="string", description="Start status"),
                ],
                timeout_seconds=30.0,
                is_idempotent=False,
            )
        )

        # ── strategy.stop ──
        definitions.append(
            ToolDefinition(
                name="strategy.stop",
                description="Stop a running strategy",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "stop"],
                capability="strategy",
                permission="strategy.execute",
                risk_level="high",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution ID", required=True),
                    ToolInput(name="reason", type="string", description="Stop reason"),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Stop status"),
                ],
                timeout_seconds=15.0,
                is_idempotent=True,
            )
        )

        # ── strategy.status ──
        definitions.append(
            ToolDefinition(
                name="strategy.status",
                description="Get strategy execution status",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "status", "monitor"],
                capability="strategy",
                permission="strategy.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="execution_id", type="string", description="Execution ID", required=True),
                ],
                outputs=[
                    ToolOutput(name="status", type="string", description="Execution status"),
                    ToolOutput(name="pnl", type="number", description="Current PnL"),
                    ToolOutput(name="positions", type="array", description="Current positions"),
                    ToolOutput(name="signals_today", type="integer", description="Signals generated today"),
                ],
                timeout_seconds=10.0,
                is_idempotent=True,
            )
        )

        # ── strategy.performance ──
        definitions.append(
            ToolDefinition(
                name="strategy.performance",
                description="Get strategy performance metrics",
                version="1.0.0",
                category="strategy",
                tags=["strategy", "performance", "metrics"],
                capability="strategy",
                permission="strategy.read",
                risk_level="low",
                inputs=[
                    ToolInput(name="strategy_id", type="string", description="Strategy ID", required=True),
                    ToolInput(name="period", type="string", description="Time period (1d,1w,1m,ytd,all)", default="all"),
                ],
                outputs=[
                    ToolOutput(name="total_return", type="number", description="Total return"),
                    ToolOutput(name="sharpe_ratio", type="number", description="Sharpe ratio"),
                    ToolOutput(name="max_drawdown", type="number", description="Max drawdown"),
                    ToolOutput(name="win_rate", type="number", description="Win rate"),
                    ToolOutput(name="profit_factor", type="number", description="Profit factor"),
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
