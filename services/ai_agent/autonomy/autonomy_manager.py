"""Autonomy Manager — lifecycle coordinator for the entire autonomous research subsystem.

Pipeline:
    AutonomyManager.initialize()
        -> AutonomyRuntime (bootstrap)
        -> GoalManager + ObjectiveManager (goal setup)
        -> WorkflowOrchestrator (pipeline setup)
        -> MarketMonitor + OpportunityDetector + SignalDiscovery (market layer)
        -> FactorMining + HypothesisGenerator + AutonomousBacktest (research layer)
        -> PortfolioRecommender + RiskReview + ComplianceChecker (risk layer)
        -> ApprovalGateway + ExecutionPlanner (approval & execution)
        -> PerformanceReviewer + FeedbackEngine + LearningPipeline (learning)
        -> SafetyController + ConfidenceEngine (safety)
        -> AutonomyManager.shutdown() (graceful teardown)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.ai_agent.autonomy.autonomy_runtime import AutonomyRuntime, AutonomyConfig
from services.ai_agent.autonomy.goal_manager import GoalManager
from services.ai_agent.autonomy.objective_manager import ObjectiveManager
from services.ai_agent.autonomy.workflow_orchestrator import WorkflowOrchestrator
from services.ai_agent.autonomy.market_monitor import MarketMonitor
from services.ai_agent.autonomy.anomaly_detector import AnomalyDetector
from services.ai_agent.autonomy.signal_discovery import SignalDiscovery
from services.ai_agent.autonomy.opportunity_detector import OpportunityDetector
from services.ai_agent.autonomy.factor_mining import FactorMining
from services.ai_agent.autonomy.hypothesis_generator import HypothesisGenerator
from services.ai_agent.autonomy.experiment_scheduler import ExperimentScheduler
from services.ai_agent.autonomy.autonomous_backtest import AutonomousBacktest
from services.ai_agent.autonomy.portfolio_recommender import PortfolioRecommender
from services.ai_agent.autonomy.portfolio_optimizer import PortfolioOptimizer
from services.ai_agent.autonomy.risk_review import RiskReview
from services.ai_agent.autonomy.compliance_checker import ComplianceChecker
from services.ai_agent.autonomy.approval_gateway import ApprovalGateway
from services.ai_agent.autonomy.execution_planner import ExecutionPlanner
from services.ai_agent.autonomy.execution_supervisor import ExecutionSupervisor
from services.ai_agent.autonomy.performance_reviewer import PerformanceReviewer
from services.ai_agent.autonomy.feedback_engine import FeedbackEngine
from services.ai_agent.autonomy.learning_pipeline import LearningPipeline
from services.ai_agent.autonomy.knowledge_updater import KnowledgeUpdater
from services.ai_agent.autonomy.adaptive_policy import AdaptivePolicy
from services.ai_agent.autonomy.confidence_engine import ConfidenceEngine
from services.ai_agent.autonomy.safety_controller import SafetyController
from services.ai_agent.autonomy.metrics import AutonomyMetrics
from services.ai_agent.autonomy.telemetry import AutonomyTelemetry
from services.ai_agent.autonomy.diagnostics import AutonomyDiagnostics
from services.ai_agent.autonomy.health import AutonomyHealthChecker

logger = logging.getLogger(__name__)


class AutonomyManager:
    """Lifecycle coordinator for the entire autonomous research subsystem.

    Initializes and manages all autonomy components in correct dependency
    order, providing a single entry-point for autonomous workflows.

    Supports:
        - Ordered initialization of all subsystems
        - Graceful shutdown with resource cleanup
        - Component health aggregation
        - Runtime configuration management

    Usage:
        mgr = AutonomyManager()
        await mgr.initialize(AutonomyConfig(mode=AutonomyMode.RESEARCH_ONLY))
        result = await mgr.run_autonomous_workflow(goal_id="goal_123")
        await mgr.shutdown()
    """

    def __init__(self) -> None:
        self._initialized: bool = False
        self._config: Optional[AutonomyConfig] = None

        # Runtime
        self._runtime: Optional[AutonomyRuntime] = None

        # Goals & Objectives
        self._goal_manager: Optional[GoalManager] = None
        self._objective_manager: Optional[ObjectiveManager] = None

        # Workflow
        self._workflow_orchestrator: Optional[WorkflowOrchestrator] = None

        # Market Layer
        self._market_monitor: Optional[MarketMonitor] = None
        self._anomaly_detector: Optional[AnomalyDetector] = None
        self._signal_discovery: Optional[SignalDiscovery] = None
        self._opportunity_detector: Optional[OpportunityDetector] = None

        # Research Layer
        self._factor_mining: Optional[FactorMining] = None
        self._hypothesis_generator: Optional[HypothesisGenerator] = None
        self._experiment_scheduler: Optional[ExperimentScheduler] = None
        self._autonomous_backtest: Optional[AutonomousBacktest] = None

        # Portfolio & Risk
        self._portfolio_recommender: Optional[PortfolioRecommender] = None
        self._portfolio_optimizer: Optional[PortfolioOptimizer] = None
        self._risk_review: Optional[RiskReview] = None
        self._compliance_checker: Optional[ComplianceChecker] = None

        # Approval & Execution
        self._approval_gateway: Optional[ApprovalGateway] = None
        self._execution_planner: Optional[ExecutionPlanner] = None
        self._execution_supervisor: Optional[ExecutionSupervisor] = None

        # Learning & Feedback
        self._performance_reviewer: Optional[PerformanceReviewer] = None
        self._feedback_engine: Optional[FeedbackEngine] = None
        self._learning_pipeline: Optional[LearningPipeline] = None
        self._knowledge_updater: Optional[KnowledgeUpdater] = None
        self._adaptive_policy: Optional[AdaptivePolicy] = None

        # Safety
        self._confidence_engine: Optional[ConfidenceEngine] = None
        self._safety_controller: Optional[SafetyController] = None

        # Observability
        self._metrics: Optional[AutonomyMetrics] = None
        self._telemetry: Optional[AutonomyTelemetry] = None
        self._diagnostics: Optional[AutonomyDiagnostics] = None
        self._health_checker: Optional[AutonomyHealthChecker] = None

        logger.info("AutonomyManager created")

    async def initialize(self, config: Optional[AutonomyConfig] = None) -> None:
        if self._initialized:
            logger.warning("AutonomyManager already initialized")
            return

        self._config = config or AutonomyConfig()
        logger.info("Initializing AutonomyManager (mode=%s)", self._config.mode.value)

        # Phase 1: Runtime
        self._runtime = AutonomyRuntime(self._config)
        await self._runtime.initialize()

        # Phase 2: Goals & Objectives
        self._goal_manager = GoalManager()
        await self._goal_manager.initialize()
        self._objective_manager = ObjectiveManager()
        await self._objective_manager.initialize()

        # Phase 3: Market Layer
        self._market_monitor = MarketMonitor()
        await self._market_monitor.initialize()
        self._anomaly_detector = AnomalyDetector()
        await self._anomaly_detector.initialize()
        self._signal_discovery = SignalDiscovery()
        await self._signal_discovery.initialize()
        self._opportunity_detector = OpportunityDetector(self._signal_discovery)
        await self._opportunity_detector.initialize()

        # Phase 4: Research Layer
        self._factor_mining = FactorMining()
        await self._factor_mining.initialize()
        self._hypothesis_generator = HypothesisGenerator()
        await self._hypothesis_generator.initialize()
        self._experiment_scheduler = ExperimentScheduler()
        await self._experiment_scheduler.initialize()
        self._autonomous_backtest = AutonomousBacktest()
        await self._autonomous_backtest.initialize()

        # Phase 5: Portfolio & Risk
        self._portfolio_recommender = PortfolioRecommender()
        await self._portfolio_recommender.initialize()
        self._portfolio_optimizer = PortfolioOptimizer()
        await self._portfolio_optimizer.initialize()
        self._risk_review = RiskReview()
        await self._risk_review.initialize()
        self._compliance_checker = ComplianceChecker()
        await self._compliance_checker.initialize()

        # Phase 6: Approval & Execution
        self._approval_gateway = ApprovalGateway(config=self._config)
        await self._approval_gateway.initialize()
        self._execution_planner = ExecutionPlanner()
        await self._execution_planner.initialize()
        self._execution_supervisor = ExecutionSupervisor()
        await self._execution_supervisor.initialize()

        # Phase 7: Learning & Feedback
        self._performance_reviewer = PerformanceReviewer()
        await self._performance_reviewer.initialize()
        self._feedback_engine = FeedbackEngine()
        await self._feedback_engine.initialize()
        self._learning_pipeline = LearningPipeline()
        await self._learning_pipeline.initialize()
        self._knowledge_updater = KnowledgeUpdater()
        await self._knowledge_updater.initialize()
        self._adaptive_policy = AdaptivePolicy()
        await self._adaptive_policy.initialize()

        # Phase 8: Safety
        self._confidence_engine = ConfidenceEngine()
        await self._confidence_engine.initialize()
        self._safety_controller = SafetyController(self._confidence_engine, self._config)
        await self._safety_controller.initialize()

        # Phase 9: Workflow Orchestrator
        self._workflow_orchestrator = WorkflowOrchestrator(
            market_monitor=self._market_monitor,
            opportunity_detector=self._opportunity_detector,
            signal_discovery=self._signal_discovery,
            factor_mining=self._factor_mining,
            hypothesis_generator=self._hypothesis_generator,
            autonomous_backtest=self._autonomous_backtest,
            portfolio_recommender=self._portfolio_recommender,
            portfolio_optimizer=self._portfolio_optimizer,
            risk_review=self._risk_review,
            compliance_checker=self._compliance_checker,
            approval_gateway=self._approval_gateway,
            execution_planner=self._execution_planner,
            performance_reviewer=self._performance_reviewer,
            feedback_engine=self._feedback_engine,
            safety_controller=self._safety_controller,
            require_approval=self._config.approval_mode.value != "none",
        )
        await self._workflow_orchestrator.initialize()

        # Phase 10: Observability
        self._metrics = AutonomyMetrics()
        await self._metrics.initialize()
        self._telemetry = AutonomyTelemetry()
        await self._telemetry.initialize()
        self._diagnostics = AutonomyDiagnostics()
        await self._diagnostics.initialize()
        self._health_checker = AutonomyHealthChecker()
        await self._health_checker.initialize()

        self._initialized = True
        logger.info("AutonomyManager initialized successfully")

    async def shutdown(self) -> None:
        if not self._initialized:
            return
        logger.info("Shutting down AutonomyManager...")

        if self._health_checker:
            await self._health_checker.shutdown()
        if self._diagnostics:
            await self._diagnostics.shutdown()
        if self._telemetry:
            await self._telemetry.shutdown()
        if self._metrics:
            await self._metrics.shutdown()

        if self._workflow_orchestrator:
            await self._workflow_orchestrator.shutdown()

        if self._safety_controller:
            await self._safety_controller.shutdown()
        if self._confidence_engine:
            await self._confidence_engine.shutdown()

        if self._adaptive_policy:
            await self._adaptive_policy.shutdown()
        if self._knowledge_updater:
            await self._knowledge_updater.shutdown()
        if self._learning_pipeline:
            await self._learning_pipeline.shutdown()
        if self._feedback_engine:
            await self._feedback_engine.shutdown()
        if self._performance_reviewer:
            await self._performance_reviewer.shutdown()

        if self._execution_supervisor:
            await self._execution_supervisor.shutdown()
        if self._execution_planner:
            await self._execution_planner.shutdown()
        if self._approval_gateway:
            await self._approval_gateway.shutdown()

        if self._compliance_checker:
            await self._compliance_checker.shutdown()
        if self._risk_review:
            await self._risk_review.shutdown()
        if self._portfolio_optimizer:
            await self._portfolio_optimizer.shutdown()
        if self._portfolio_recommender:
            await self._portfolio_recommender.shutdown()

        if self._autonomous_backtest:
            await self._autonomous_backtest.shutdown()
        if self._experiment_scheduler:
            await self._experiment_scheduler.shutdown()
        if self._hypothesis_generator:
            await self._hypothesis_generator.shutdown()
        if self._factor_mining:
            await self._factor_mining.shutdown()

        if self._opportunity_detector:
            await self._opportunity_detector.shutdown()
        if self._signal_discovery:
            await self._signal_discovery.shutdown()
        if self._anomaly_detector:
            await self._anomaly_detector.shutdown()
        if self._market_monitor:
            await self._market_monitor.shutdown()

        if self._objective_manager:
            await self._objective_manager.shutdown()
        if self._goal_manager:
            await self._goal_manager.shutdown()

        if self._runtime:
            await self._runtime.shutdown()

        self._initialized = False
        logger.info("AutonomyManager shutdown complete")

    async def run_autonomous_workflow(self, goal_id: str = "") -> Any:
        if not self._workflow_orchestrator:
            raise RuntimeError("WorkflowOrchestrator not initialized")
        if self._runtime:
            self._runtime.workflow_started()
        try:
            return await self._workflow_orchestrator.execute(goal_id=goal_id)
        finally:
            if self._runtime:
                self._runtime.workflow_completed()

    # ── Accessors ──

    @property
    def orchestrator(self) -> Optional[WorkflowOrchestrator]:
        return self._workflow_orchestrator

    @property
    def market_monitor(self) -> Optional[MarketMonitor]:
        return self._market_monitor

    @property
    def safety_controller(self) -> Optional[SafetyController]:
        return self._safety_controller

    @property
    def approval_gateway(self) -> Optional[ApprovalGateway]:
        return self._approval_gateway

    @property
    def metrics(self) -> Optional[AutonomyMetrics]:
        return self._metrics

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "config": self._config.to_dict() if self._config else None,
            "goals": self._goal_manager.get_summary() if self._goal_manager else {},
            "workflows": self._workflow_orchestrator.get_summary() if self._workflow_orchestrator else {},
        }
