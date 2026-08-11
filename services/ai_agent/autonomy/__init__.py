"""Autonomy Module — autonomous research and trading workflow with Human-in-the-Loop.

The autonomy module enables AI agents to independently execute complete
research-to-execution pipelines while maintaining safety through configurable
human approval gates.

Architecture:
    Market Monitor -> Opportunity Detector -> Signal Discovery -> Factor Mining
    -> Hypothesis Generator -> Autonomous Backtesting -> Portfolio Optimizer
    -> Risk Review -> Compliance Checker -> Approval Gateway -> Execution Planner
    -> Performance Reviewer -> Feedback Engine -> Continuous Learning

Key principles:
    - Human-in-the-Loop (HITL) is enabled by default for live trading
    - Research and paper trading can be fully autonomous
    - Every decision is auditable through the safety controller
    - Continuous learning feeds back into the adaptive policy engine
"""

from __future__ import annotations

# ── Core Engine ──
from services.ai_agent.autonomy.autonomy_engine import AutonomousEngine
from services.ai_agent.autonomy.autonomy_manager import AutonomyManager
from services.ai_agent.autonomy.autonomy_runtime import AutonomyRuntime, AutonomyConfig
from services.ai_agent.autonomy.goal_manager import GoalManager, Goal, GoalStatus
from services.ai_agent.autonomy.objective_manager import ObjectiveManager, Objective
from services.ai_agent.autonomy.workflow_orchestrator import WorkflowOrchestrator, WorkflowStage

# ── Market Layer ──
from services.ai_agent.autonomy.market_monitor import MarketMonitor, MarketAlert
from services.ai_agent.autonomy.anomaly_detector import AnomalyDetector, AnomalyEvent
from services.ai_agent.autonomy.signal_discovery import SignalDiscovery, SignalCandidate
from services.ai_agent.autonomy.opportunity_detector import OpportunityDetector, Opportunity

# ── Research Layer ──
from services.ai_agent.autonomy.factor_mining import FactorMining, FactorCandidate
from services.ai_agent.autonomy.hypothesis_generator import HypothesisGenerator, Hypothesis
from services.ai_agent.autonomy.experiment_scheduler import ExperimentScheduler, Experiment
from services.ai_agent.autonomy.autonomous_backtest import AutonomousBacktest, BacktestResult

# ── Portfolio & Risk ──
from services.ai_agent.autonomy.portfolio_recommender import PortfolioRecommender, PortfolioRecommendation
from services.ai_agent.autonomy.portfolio_optimizer import PortfolioOptimizer, OptimizationResult
from services.ai_agent.autonomy.risk_review import RiskReview, RiskAssessment
from services.ai_agent.autonomy.compliance_checker import ComplianceChecker, ComplianceResult

# ── Approval & Execution ──
from services.ai_agent.autonomy.approval_gateway import ApprovalGateway, ApprovalDecision
from services.ai_agent.autonomy.execution_planner import ExecutionPlanner, ExecutionPlan
from services.ai_agent.autonomy.execution_supervisor import ExecutionSupervisor

# ── Learning & Feedback ──
from services.ai_agent.autonomy.performance_reviewer import PerformanceReviewer, PerformanceReport
from services.ai_agent.autonomy.feedback_engine import FeedbackEngine, Feedback
from services.ai_agent.autonomy.learning_pipeline import LearningPipeline, LearningEvent
from services.ai_agent.autonomy.knowledge_updater import KnowledgeUpdater, KnowledgeEntry
from services.ai_agent.autonomy.adaptive_policy import AdaptivePolicy, PolicyProfile
from services.ai_agent.autonomy.confidence_engine import ConfidenceEngine, ConfidenceScore
from services.ai_agent.autonomy.safety_controller import SafetyController, SafetyDecision

# ── Observability ──
from services.ai_agent.autonomy.metrics import AutonomyMetrics
from services.ai_agent.autonomy.telemetry import AutonomyTelemetry
from services.ai_agent.autonomy.diagnostics import AutonomyDiagnostics
from services.ai_agent.autonomy.health import AutonomyHealthChecker

__all__ = [
    # Core Engine
    "AutonomousEngine",
    "AutonomyManager",
    "AutonomyRuntime",
    "AutonomyConfig",
    "GoalManager",
    "Goal",
    "GoalStatus",
    "ObjectiveManager",
    "Objective",
    "WorkflowOrchestrator",
    "WorkflowStage",
    # Market Layer
    "MarketMonitor",
    "MarketAlert",
    "AnomalyDetector",
    "AnomalyEvent",
    "SignalDiscovery",
    "SignalCandidate",
    "OpportunityDetector",
    "Opportunity",
    # Research Layer
    "FactorMining",
    "FactorCandidate",
    "HypothesisGenerator",
    "Hypothesis",
    "ExperimentScheduler",
    "Experiment",
    "AutonomousBacktest",
    "BacktestResult",
    # Portfolio & Risk
    "PortfolioRecommender",
    "PortfolioRecommendation",
    "PortfolioOptimizer",
    "OptimizationResult",
    "RiskReview",
    "RiskAssessment",
    "ComplianceChecker",
    "ComplianceResult",
    # Approval & Execution
    "ApprovalGateway",
    "ApprovalDecision",
    "ExecutionPlanner",
    "ExecutionPlan",
    "ExecutionSupervisor",
    # Learning & Feedback
    "PerformanceReviewer",
    "PerformanceReport",
    "FeedbackEngine",
    "Feedback",
    "LearningPipeline",
    "LearningEvent",
    "KnowledgeUpdater",
    "KnowledgeEntry",
    "AdaptivePolicy",
    "PolicyProfile",
    "ConfidenceEngine",
    "ConfidenceScore",
    "SafetyController",
    "SafetyDecision",
    # Observability
    "AutonomyMetrics",
    "AutonomyTelemetry",
    "AutonomyDiagnostics",
    "AutonomyHealthChecker",
]
