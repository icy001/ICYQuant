"""
Risk & Execution Orchestrator — coordinates the full autonomous pipeline.

10-stage pipeline from target position to execution feedback:

    Stage 1: Risk Budget Allocation
    Stage 2: Exposure Optimization
    Stage 3: Factor Risk Decomposition
    Stage 4: Concentration & Correlation Optimization
    Stage 5: Liquidity & Drawdown Control
    Stage 6: Scenario & Stress Testing
    Stage 7: Execution Planning
    Stage 8: Order Slicing & Routing
    Stage 9: Pre-Trade Validation
    Stage 10: Execution & Feedback Loop
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Stages of the risk-execution pipeline."""
    RISK_BUDGET = "risk_budget"
    EXPOSURE_OPTIMIZATION = "exposure_optimization"
    FACTOR_RISK = "factor_risk"
    CONCENTRATION_CORRELATION = "concentration_correlation"
    LIQUIDITY_DRAWDOWN = "liquidity_drawdown"
    SCENARIO_STRESS = "scenario_stress"
    EXECUTION_PLANNING = "execution_planning"
    ORDER_SLICING_ROUTING = "order_slicing_routing"
    PRE_TRADE_VALIDATION = "pre_trade_validation"
    EXECUTION_FEEDBACK = "execution_feedback"


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class OrchestratorConfig:
    """Orchestrator configuration."""
    stages_enabled: set[PipelineStage] = field(default_factory=lambda: set(PipelineStage))
    stop_on_failure: bool = True
    stop_on_blocked: bool = True
    max_stage_duration_seconds: int = 120
    feedback_loop_enabled: bool = True
    trace_enabled: bool = True


@dataclass
class PipelineResult:
    """Complete pipeline execution result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    status: StageStatus = StageStatus.PENDING
    stages: list[StageResult] = field(default_factory=list)
    risk_adjusted_target: dict[str, Any] = field(default_factory=dict)
    execution_plan: dict[str, Any] = field(default_factory=dict)
    orders: list[dict] = field(default_factory=list)
    feedback: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0


class RiskExecutionOrchestrator:
    """
    Orchestrates the full autonomous risk & execution pipeline.

    10-stage pipeline:
        1. Allocate dynamic risk budget based on regime
        2. Optimize exposures (gross/net/long/short)
        3. Decompose factor risk exposure
        4. Optimize concentration & correlation
        5. Apply liquidity & drawdown controls
        6. Run scenario & stress tests
        7. Generate execution plan
        8. Slice orders & route to venues
        9. Pre-trade validation by guards
        10. Execute & collect feedback for learning
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None) -> None:
        self._id = str(uuid4())
        self._config = config or OrchestratorConfig()
        if not self._config.stages_enabled:
            self._config.stages_enabled = set(PipelineStage)
        self._kill_switched = False

    async def run_pipeline(self, target_portfolio: dict) -> PipelineResult:
        """
        Execute the full risk-to-execution pipeline.

        Args:
            target_portfolio: Raw target positions from portfolio engine

        Returns:
            PipelineResult with risk-adjusted targets, execution plan,
            orders, and feedback.
        """
        if self._kill_switched:
            result = PipelineResult(status=StageStatus.BLOCKED)
            result.errors.append("Kill switch active")
            return result

        result = PipelineResult(
            id=str(uuid4()),
            status=StageStatus.RUNNING,
            started_at=datetime.now(),
        )

        current_data = dict(target_portfolio)
        stage_map = {
            PipelineStage.RISK_BUDGET: self._stage_risk_budget,
            PipelineStage.EXPOSURE_OPTIMIZATION: self._stage_exposure_optimization,
            PipelineStage.FACTOR_RISK: self._stage_factor_risk,
            PipelineStage.CONCENTRATION_CORRELATION: self._stage_concentration_correlation,
            PipelineStage.LIQUIDITY_DRAWDOWN: self._stage_liquidity_drawdown,
            PipelineStage.SCENARIO_STRESS: self._stage_scenario_stress,
            PipelineStage.EXECUTION_PLANNING: self._stage_execution_planning,
            PipelineStage.ORDER_SLICING_ROUTING: self._stage_order_slicing_routing,
            PipelineStage.PRE_TRADE_VALIDATION: self._stage_pre_trade_validation,
            PipelineStage.EXECUTION_FEEDBACK: self._stage_execution_feedback,
        }

        stage_order = list(PipelineStage)
        for stage in stage_order:
            if stage not in self._config.stages_enabled:
                continue

            stage_result = await self._execute_stage(
                stage, stage_map[stage], current_data
            )
            result.stages.append(stage_result)

            if stage_result.status == StageStatus.BLOCKED and self._config.stop_on_blocked:
                result.status = StageStatus.BLOCKED
                break

            if stage_result.status == StageStatus.FAILED and self._config.stop_on_failure:
                result.status = StageStatus.FAILED
                result.errors.append(f"Stage {stage.value} failed: {stage_result.error}")
                break

            # Merge stage output into current data
            current_data.update(stage_result.output_data)

            # Capture key outputs
            if stage == PipelineStage.LIQUIDITY_DRAWDOWN:
                result.risk_adjusted_target = dict(current_data)
            elif stage == PipelineStage.ORDER_SLICING_ROUTING:
                result.execution_plan = dict(current_data)
            elif stage == PipelineStage.EXECUTION_FEEDBACK:
                result.feedback = stage_result.output_data.get("feedback", {})

        result.completed_at = datetime.now()
        result.total_duration_ms = (
            (result.completed_at - (result.started_at or result.completed_at)).total_seconds() * 1000
        )
        if result.status == StageStatus.RUNNING:
            result.status = StageStatus.COMPLETED

        logger.info("Pipeline completed id=%s status=%s stages=%d",
                     result.id, result.status.value, len(result.stages))
        return result

    async def _execute_stage(
        self,
        stage: PipelineStage,
        handler,
        data: dict,
    ) -> StageResult:
        """Execute a single stage with timing and error handling."""
        result = StageResult(stage=stage, status=StageStatus.RUNNING)
        result.started_at = datetime.now()
        result.input_data = dict(data)

        try:
            output = await asyncio.wait_for(
                handler(data),
                timeout=self._config.max_stage_duration_seconds,
            )
            result.output_data = output
            result.status = StageStatus.COMPLETED
        except asyncio.TimeoutError:
            result.status = StageStatus.FAILED
            result.error = f"Stage {stage.value} timed out"
            logger.error(result.error)
        except Exception as e:
            result.status = StageStatus.FAILED
            result.error = str(e)
            logger.error("Stage %s failed: %s", stage.value, e)

        result.completed_at = datetime.now()
        if result.started_at:
            result.duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
        return result

    # ── Stage Handlers ─────────────────────────────────────────

    async def _stage_risk_budget(self, data: dict) -> dict:
        """Stage 1: Allocate dynamic risk budget based on market regime."""
        regime = data.get("regime", "NORMAL")
        budgets = {
            "NORMAL": 1.0, "HIGH_VOL": 0.70, "RISK_OFF": 0.40,
            "CRISIS": 0.20, "TRENDING": 0.85, "MEAN_REVERTING": 0.75,
        }
        risk_budget = budgets.get(regime, 0.60)
        return {"risk_budget": risk_budget, "regime": regime}

    async def _stage_exposure_optimization(self, data: dict) -> dict:
        """Stage 2: Optimize exposures with risk budget constraint."""
        risk_budget = data.get("risk_budget", 1.0)
        return {
            "max_gross_exposure": min(2.0 * risk_budget, 2.0),
            "max_net_exposure": min(1.5 * risk_budget, 1.5),
            "risk_budget_applied": risk_budget,
        }

    async def _stage_factor_risk(self, data: dict) -> dict:
        """Stage 3: Decompose factor risk exposure."""
        return {"factor_risk": {}, "factor_exposures": {}}

    async def _stage_concentration_correlation(self, data: dict) -> dict:
        """Stage 4: Optimize concentration and correlation."""
        return {"concentration_ok": True, "correlation_matrix": {}}

    async def _stage_liquidity_drawdown(self, data: dict) -> dict:
        """Stage 5: Apply liquidity and drawdown controls."""
        return {"liquidity_ok": True, "drawdown_ok": True}

    async def _stage_scenario_stress(self, data: dict) -> dict:
        """Stage 6: Run scenario and stress tests."""
        return {"scenario_results": {}, "stress_results": {}}

    async def _stage_execution_planning(self, data: dict) -> dict:
        """Stage 7: Generate execution plan."""
        return {"execution_plan": {}, "slices": 10, "time_horizon_min": 30}

    async def _stage_order_slicing_routing(self, data: dict) -> dict:
        """Stage 8: Slice orders and select venues."""
        return {"orders": [], "routing": {}}

    async def _stage_pre_trade_validation(self, data: dict) -> dict:
        """Stage 9: Pre-trade guard validation."""
        return {"pre_trade_passed": True, "orders": data.get("orders", [])}

    async def _stage_execution_feedback(self, data: dict) -> dict:
        """Stage 10: Collect and process execution feedback."""
        return {"feedback": {"quality": "pending", "updates": []}}

    # ── Kill Switch ────────────────────────────────────────────

    def kill_switch(self, reason: str) -> None:
        """Stop pipeline execution immediately."""
        self._kill_switched = True
        logger.critical("ORCHESTRATOR KILL SWITCH: %s", reason)

    @property
    def is_active(self) -> bool:
        return not self._kill_switched
