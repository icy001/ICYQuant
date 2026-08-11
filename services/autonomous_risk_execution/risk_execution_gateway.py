"""
Risk & Execution Gateway — unified API entry point.

Exposes all risk optimization, execution optimization, and feedback
capabilities through a single consistent interface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class GatewayRequest:
    """Unified request envelope."""
    id: str = field(default_factory=lambda: str(uuid4()))
    operation: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class GatewayResponse:
    """Unified response envelope."""
    request_id: str = ""
    success: bool = False
    data: Any = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskExecutionGateway:
    """
    Unified API gateway for risk & execution operations.

    Operations:
        - Risk: optimize_risk, analyze_risk, check_constraints
        - Risk Engines: marginal_risk, factor_risk, scenario_analysis, stress_test
        - Execution: plan_execution, optimize_execution, slice_orders
        - Guards: pre_trade_check, validate_order, kill_switch_status
        - Feedback: analyze_fill, measure_slippage, compute_shortfall, quality_score
        - Learning: record_execution, get_execution_insights
        - Memory: save_risk_snapshot, query_history
    """

    def __init__(self) -> None:
        self._id = str(uuid4())
        self._handlers: dict[str, Any] = {}
        logger.info("RiskExecutionGateway created id=%s", self._id)

    async def handle(self, request: GatewayRequest) -> GatewayResponse:
        """Route a request to the appropriate handler."""
        try:
            handler = self._get_handler(request.operation)
            result = await handler(request.payload)
            return GatewayResponse(
                request_id=request.id,
                success=True,
                data=result,
                metadata={"operation": request.operation},
            )
        except ValueError as e:
            return GatewayResponse(
                request_id=request.id,
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error("Gateway error operation=%s: %s", request.operation, e)
            return GatewayResponse(
                request_id=request.id,
                success=False,
                error=str(e),
            )

    # ── Risk Operations ────────────────────────────────────────

    async def optimize_risk(self, portfolio: dict) -> dict:
        """Run full risk optimization pipeline."""
        return await self._dispatch("optimize_risk", portfolio)

    async def analyze_risk(self, portfolio: dict) -> dict:
        """Analyze portfolio risk without optimization."""
        return await self._dispatch("analyze_risk", portfolio)

    async def check_constraints(self, portfolio: dict) -> dict:
        """Check portfolio against all risk constraints."""
        return await self._dispatch("check_constraints", portfolio)

    async def marginal_risk(self, portfolio: dict, new_position: dict) -> dict:
        """Compute marginal risk of adding a position."""
        return await self._dispatch("marginal_risk", {
            "portfolio": portfolio, "new_position": new_position,
        })

    async def factor_risk(self, portfolio: dict) -> dict:
        """Compute factor risk decomposition."""
        return await self._dispatch("factor_risk", portfolio)

    async def scenario_analysis(self, portfolio: dict, scenarios: list) -> dict:
        """Run scenario analysis."""
        return await self._dispatch("scenario_analysis", {
            "portfolio": portfolio, "scenarios": scenarios,
        })

    async def stress_test(self, portfolio: dict) -> dict:
        """Run stress test suite."""
        return await self._dispatch("stress_test", portfolio)

    async def tail_risk(self, portfolio: dict) -> dict:
        """Compute tail risk metrics."""
        return await self._dispatch("tail_risk", portfolio)

    async def var(self, portfolio: dict, confidence: float = 0.95) -> dict:
        """Compute VaR."""
        return await self._dispatch("var", {
            "portfolio": portfolio, "confidence": confidence,
        })

    async def expected_shortfall(self, portfolio: dict, confidence: float = 0.95) -> dict:
        """Compute Expected Shortfall."""
        return await self._dispatch("expected_shortfall", {
            "portfolio": portfolio, "confidence": confidence,
        })

    # ── Execution Operations ───────────────────────────────────

    async def plan_execution(self, target: dict) -> dict:
        """Generate execution plan."""
        return await self._dispatch("plan_execution", target)

    async def optimize_execution(self, plan: dict) -> dict:
        """Optimize execution plan."""
        return await self._dispatch("optimize_execution", plan)

    async def slice_orders(self, parent_order: dict) -> dict:
        """Slice a parent order into child orders."""
        return await self._dispatch("slice_orders", parent_order)

    async def select_strategy(self, order: dict, market: dict) -> dict:
        """Select optimal execution strategy."""
        return await self._dispatch("select_strategy", {
            "order": order, "market": market,
        })

    async def estimate_cost(self, order: dict) -> dict:
        """Estimate execution cost."""
        return await self._dispatch("estimate_cost", order)

    async def estimate_impact(self, order: dict) -> dict:
        """Estimate market impact."""
        return await self._dispatch("estimate_impact", order)

    async def estimate_fill_probability(self, order: dict) -> dict:
        """Estimate fill probability."""
        return await self._dispatch("estimate_fill_prob", order)

    # ── Guard Operations ───────────────────────────────────────

    async def pre_trade_check(self, order: dict) -> dict:
        """Run pre-trade safety checks."""
        return await self._dispatch("pre_trade_check", order)

    async def validate_order(self, order: dict) -> dict:
        """Validate a single order."""
        return await self._dispatch("validate_order", order)

    async def kill_switch_status(self) -> dict:
        """Get kill switch status."""
        return await self._dispatch("kill_switch_status", {})

    async def engage_kill_switch(self, reason: str) -> dict:
        """Engage kill switch."""
        return await self._dispatch("engage_kill_switch", {"reason": reason})

    # ── Feedback Operations ────────────────────────────────────

    async def analyze_fill(self, fill: dict) -> dict:
        """Analyze a fill event."""
        return await self._dispatch("analyze_fill", fill)

    async def measure_slippage(self, order: dict, fill: dict) -> dict:
        """Measure realized slippage."""
        return await self._dispatch("measure_slippage", {
            "order": order, "fill": fill,
        })

    async def compute_shortfall(self, decision: dict, execution: dict) -> dict:
        """Compute implementation shortfall."""
        return await self._dispatch("compute_shortfall", {
            "decision": decision, "execution": execution,
        })

    async def quality_score(self, execution: dict) -> dict:
        """Compute execution quality score."""
        return await self._dispatch("quality_score", execution)

    # ── Learning Operations ────────────────────────────────────

    async def record_execution(self, execution_data: dict) -> dict:
        """Record execution for learning."""
        return await self._dispatch("record_execution", execution_data)

    async def get_execution_insights(self, filters: Optional[dict] = None) -> dict:
        """Get execution learning insights."""
        return await self._dispatch("get_insights", filters or {})

    # ── Memory Operations ──────────────────────────────────────

    async def save_risk_snapshot(self, snapshot: dict) -> dict:
        """Save risk snapshot to memory."""
        return await self._dispatch("save_risk_snapshot", snapshot)

    async def query_history(self, query: dict) -> dict:
        """Query risk/execution history."""
        return await self._dispatch("query_history", query)

    # ── Internal ───────────────────────────────────────────────

    def _get_handler(self, operation: str):
        handler = self._handlers.get(operation)
        if handler is None:
            raise ValueError(f"No handler for operation: {operation}")
        return handler

    async def _dispatch(self, operation: str, payload: dict) -> dict:
        """Dispatch to handler with logging."""
        logger.debug("Dispatching operation=%s", operation)
        return {"operation": operation, "status": "stub"}
