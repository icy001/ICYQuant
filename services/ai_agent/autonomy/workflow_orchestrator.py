"""Workflow Orchestrator — coordinates the end-to-end autonomous research pipeline.

Pipeline:
    Goal -> WorkflowOrchestrator.execute()
        -> Market Monitor (detect opportunities)
        -> Opportunity Detector (score opportunities)
        -> Signal Discovery (generate signals)
        -> Factor Mining (mine alpha factors)
        -> Hypothesis Generator (form hypotheses)
        -> Autonomous Backtesting (validate)
        -> Portfolio Recommender (construct)
        -> Risk Review (assess)
        -> Compliance Checker (verify)
        -> Approval Gateway (HITL)
        -> Execution Planner (plan)
        -> Performance Reviewer (review)
        -> Feedback Engine (learn)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """Stages in the autonomous research pipeline."""
    INIT = "init"
    MONITORING = "monitoring"
    OPPORTUNITY_DETECTION = "opportunity_detection"
    SIGNAL_DISCOVERY = "signal_discovery"
    FACTOR_MINING = "factor_mining"
    HYPOTHESIS = "hypothesis"
    BACKTESTING = "backtesting"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"
    RISK_REVIEW = "risk_review"
    COMPLIANCE = "compliance"
    APPROVAL = "approval"
    EXECUTION_PLANNING = "execution_planning"
    REVIEW = "review"
    LEARNING = "learning"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class WorkflowContext:
    """Context passed through the entire autonomous workflow pipeline.

    Attributes:
        workflow_id: Unique workflow identifier.
        goal_id: Parent goal identifier.
        status: Current workflow status.
        current_stage: Current pipeline stage.
        start_time: Workflow start time.
        artifacts: Stage outputs keyed by stage name.
        decisions: Recorded decisions at each stage.
        errors: Errors encountered at each stage.
    """

    workflow_id: str = ""
    goal_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_stage: WorkflowStage = WorkflowStage.INIT
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    artifacts: Dict[str, Any] = field(default_factory=dict)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def record_decision(self, stage: str, decision: str, detail: Dict[str, Any] = None) -> None:
        self.decisions.append({"stage": stage, "decision": decision, "detail": detail or {}, "timestamp": datetime.now(timezone.utc).isoformat()})

    def record_error(self, stage: str, error: str) -> None:
        self.errors.append({"stage": stage, "error": error, "timestamp": datetime.now(timezone.utc).isoformat()})

    def set_artifact(self, stage: str, data: Any) -> None:
        self.artifacts[stage] = data


class WorkflowOrchestrator:
    """Coordinates the end-to-end autonomous research pipeline.

    Executes the full pipeline from market monitoring through continuous
    learning, with configurable Human-in-the-Loop approval gates.

    Supports:
        - Stage-by-stage pipeline execution
        - Configurable stage skipping
        - Context propagation between stages
        - Error handling and graceful failure
        - Workflow status tracking

    Usage:
        orchestrator = WorkflowOrchestrator(...)
        context = await orchestrator.execute(goal_id="goal_123")
    """

    def __init__(
        self,
        market_monitor: Any = None,
        opportunity_detector: Any = None,
        signal_discovery: Any = None,
        factor_mining: Any = None,
        hypothesis_generator: Any = None,
        autonomous_backtest: Any = None,
        portfolio_recommender: Any = None,
        portfolio_optimizer: Any = None,
        risk_review: Any = None,
        compliance_checker: Any = None,
        approval_gateway: Any = None,
        execution_planner: Any = None,
        performance_reviewer: Any = None,
        feedback_engine: Any = None,
        safety_controller: Any = None,
        require_approval: bool = True,
    ) -> None:
        self._components = {
            "market_monitor": market_monitor,
            "opportunity_detector": opportunity_detector,
            "signal_discovery": signal_discovery,
            "factor_mining": factor_mining,
            "hypothesis_generator": hypothesis_generator,
            "autonomous_backtest": autonomous_backtest,
            "portfolio_recommender": portfolio_recommender,
            "portfolio_optimizer": portfolio_optimizer,
            "risk_review": risk_review,
            "compliance_checker": compliance_checker,
            "approval_gateway": approval_gateway,
            "execution_planner": execution_planner,
            "performance_reviewer": performance_reviewer,
            "feedback_engine": feedback_engine,
            "safety_controller": safety_controller,
        }
        self._require_approval = require_approval
        self._active_workflows: Dict[str, WorkflowContext] = {}
        self._completed_workflows: List[WorkflowContext] = []
        self._max_completed: int = 500
        self._initialized: bool = False
        logger.info("WorkflowOrchestrator created (require_approval=%s)", require_approval)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("WorkflowOrchestrator initialized")

    async def shutdown(self) -> None:
        self._active_workflows.clear()
        self._completed_workflows.clear()
        self._initialized = False
        logger.info("WorkflowOrchestrator shutdown complete")

    async def execute(self, goal_id: str = "") -> WorkflowContext:
        """Execute the full autonomous research pipeline.

        Args:
            goal_id: Optional parent goal identifier.

        Returns:
            WorkflowContext with pipeline results.
        """
        ctx = WorkflowContext(
            workflow_id=f"wf_{int(time.time() * 1000)}_{len(self._completed_workflows)}",
            goal_id=goal_id,
            status=WorkflowStatus.RUNNING,
        )
        self._active_workflows[ctx.workflow_id] = ctx
        logger.info("Workflow started: %s", ctx.workflow_id)

        try:
            await self._execute_stage(ctx, WorkflowStage.MONITORING, "market_monitor", self._monitor_stage)
            await self._execute_stage(ctx, WorkflowStage.OPPORTUNITY_DETECTION, "opportunity_detector", self._detect_opportunities_stage)
            await self._execute_stage(ctx, WorkflowStage.SIGNAL_DISCOVERY, "signal_discovery", self._discover_signals_stage)
            await self._execute_stage(ctx, WorkflowStage.FACTOR_MINING, "factor_mining", self._mine_factors_stage)
            await self._execute_stage(ctx, WorkflowStage.HYPOTHESIS, "hypothesis_generator", self._generate_hypothesis_stage)
            await self._execute_stage(ctx, WorkflowStage.BACKTESTING, "autonomous_backtest", self._backtest_stage)
            await self._execute_stage(ctx, WorkflowStage.PORTFOLIO_CONSTRUCTION, "portfolio_recommender", self._construct_portfolio_stage)
            await self._execute_stage(ctx, WorkflowStage.RISK_REVIEW, "risk_review", self._risk_review_stage)
            await self._execute_stage(ctx, WorkflowStage.COMPLIANCE, "compliance_checker", self._compliance_stage)

            # Approval gate
            ctx.current_stage = WorkflowStage.APPROVAL
            if self._require_approval and self._components["approval_gateway"]:
                ctx.status = WorkflowStatus.AWAITING_APPROVAL
                approved = await self._components["approval_gateway"].request_approval(ctx)
                if not approved:
                    ctx.status = WorkflowStatus.REJECTED
                    ctx.record_decision("approval", "rejected", {})
                    logger.info("Workflow rejected by approval gateway: %s", ctx.workflow_id)
                    self._archive(ctx)
                    return ctx
                ctx.record_decision("approval", "approved", {})

            ctx.status = WorkflowStatus.RUNNING
            await self._execute_stage(ctx, WorkflowStage.EXECUTION_PLANNING, "execution_planner", self._plan_execution_stage)
            await self._execute_stage(ctx, WorkflowStage.REVIEW, "performance_reviewer", self._review_stage)
            await self._execute_stage(ctx, WorkflowStage.LEARNING, "feedback_engine", self._learn_stage)

            ctx.status = WorkflowStatus.COMPLETED
            ctx.current_stage = WorkflowStage.COMPLETED
            logger.info("Workflow completed: %s", ctx.workflow_id)

        except Exception as e:
            ctx.status = WorkflowStatus.FAILED
            ctx.record_error(ctx.current_stage.value, str(e))
            logger.error("Workflow failed: %s (stage=%s, error=%s)", ctx.workflow_id, ctx.current_stage.value, e)

        self._archive(ctx)
        return ctx

    async def _execute_stage(self, ctx: WorkflowContext, stage: WorkflowStage, component_name: str, handler: Callable) -> None:
        ctx.current_stage = stage
        component = self._components.get(component_name)
        if component is None:
            logger.debug("Component %s not configured, skipping stage %s", component_name, stage.value)
            return
        await handler(ctx, component)

    # ── Stage Handlers ──

    async def _monitor_stage(self, ctx: WorkflowContext, monitor: Any) -> None:
        logger.debug("Stage: monitoring")
        ctx.set_artifact("monitoring", {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

    async def _detect_opportunities_stage(self, ctx: WorkflowContext, detector: Any) -> None:
        logger.debug("Stage: opportunity detection")
        ctx.set_artifact("opportunities", {"count": 0, "opportunities": []})

    async def _discover_signals_stage(self, ctx: WorkflowContext, discovery: Any) -> None:
        logger.debug("Stage: signal discovery")
        ctx.set_artifact("signals", {"count": 0, "signals": []})

    async def _mine_factors_stage(self, ctx: WorkflowContext, mining: Any) -> None:
        logger.debug("Stage: factor mining")
        ctx.set_artifact("factors", {"count": 0, "factors": []})

    async def _generate_hypothesis_stage(self, ctx: WorkflowContext, generator: Any) -> None:
        logger.debug("Stage: hypothesis generation")
        ctx.set_artifact("hypothesis", {})

    async def _backtest_stage(self, ctx: WorkflowContext, backtest: Any) -> None:
        logger.debug("Stage: backtesting")
        ctx.set_artifact("backtest", {})

    async def _construct_portfolio_stage(self, ctx: WorkflowContext, recommender: Any) -> None:
        logger.debug("Stage: portfolio construction")
        ctx.set_artifact("portfolio", {})

    async def _risk_review_stage(self, ctx: WorkflowContext, risk_review: Any) -> None:
        logger.debug("Stage: risk review")
        ctx.set_artifact("risk", {})

    async def _compliance_stage(self, ctx: WorkflowContext, checker: Any) -> None:
        logger.debug("Stage: compliance")
        ctx.set_artifact("compliance", {})

    async def _plan_execution_stage(self, ctx: WorkflowContext, planner: Any) -> None:
        logger.debug("Stage: execution planning")
        ctx.set_artifact("execution_plan", {})

    async def _review_stage(self, ctx: WorkflowContext, reviewer: Any) -> None:
        logger.debug("Stage: performance review")
        ctx.set_artifact("review", {})

    async def _learn_stage(self, ctx: WorkflowContext, feedback: Any) -> None:
        logger.debug("Stage: learning")
        ctx.set_artifact("learning", {})

    # ── Helpers ──

    def _archive(self, ctx: WorkflowContext) -> None:
        self._active_workflows.pop(ctx.workflow_id, None)
        self._completed_workflows.append(ctx)
        if len(self._completed_workflows) > self._max_completed:
            self._completed_workflows = self._completed_workflows[-self._max_completed:]

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowContext]:
        return self._active_workflows.get(workflow_id)

    def get_recent_workflows(self, limit: int = 20) -> List[WorkflowContext]:
        return self._completed_workflows[-limit:]

    def get_summary(self) -> Dict[str, Any]:
        return {
            "active_workflows": len(self._active_workflows),
            "completed_workflows": len(self._completed_workflows),
            "require_approval": self._require_approval,
            "initialized": self._initialized,
        }
