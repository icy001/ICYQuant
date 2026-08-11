"""
ICYQuant AI Research Platform — unified entry point for quantitative research.

Acts as the top-level orchestrator that wires together the gateway,
orchestrator, knowledge engine, and reporting pipeline into a single
research platform instance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from services.ai_research.research_gateway import ResearchGateway
from services.ai_research.research_orchestrator import ResearchOrchestrator
from services.ai_research.research_runtime import ResearchRuntime
from services.ai_research.research_manager import ResearchManager
from services.ai_research.research_controller import ResearchController
from services.ai_research.research_session import ResearchSession
from services.ai_research.research_workspace import ResearchWorkspace
from services.ai_research.research_pipeline import ResearchPipeline
from services.ai_research.knowledge_engine import KnowledgeEngine
from services.ai_research.report_generator import ReportGenerator
from services.ai_research.research_memory import ResearchMemory
from services.ai_research.prompt_library import PromptLibrary
from services.ai_research.task_planner import TaskPlanner
from services.ai_research.hypothesis_engine import HypothesisEngine
from services.ai_research.evidence_engine import EvidenceEngine
from services.ai_research.citation_manager import CitationManager
from services.ai_research.experiment_tracker import ExperimentTracker
from services.ai_research.artifact_registry import ArtifactRegistry
from services.ai_research.notebook_manager import NotebookManager
from services.ai_research.metrics import ResearchMetrics
from services.ai_research.telemetry import ResearchTelemetry
from services.ai_research.diagnostics import ResearchDiagnostics
from services.ai_research.health import ResearchHealthChecker

logger = logging.getLogger(__name__)


class PlatformStatus(str, Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"


@dataclass
class PlatformConfig:
    name: str = "icyquant-ai-research"
    max_concurrent_sessions: int = 50
    knowledge_cache_ttl_seconds: int = 3600
    auto_save_interval_seconds: int = 300
    enable_collaboration: bool = True
    enable_notebooks: bool = True
    enable_experiments: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformInfo:
    status: PlatformStatus
    version: str
    uptime_seconds: float
    active_sessions: int
    total_requests: int
    component_statuses: dict[str, str]


class AIResearchPlatform:
    """Unified AI Research Platform — single entry point for all research workflows.

    Composes:
        - Research Gateway (request entry)
        - Research Orchestrator (workflow coordination)
        - Knowledge Engine (semantic retrieval + knowledge graph)
        - Report Generator (structured output)
        - Session & Workspace management
        - Experiment tracking & notebook management
    """

    VERSION = "0.4.0-alpha2"

    def __init__(self, config: Optional[PlatformConfig] = None) -> None:
        self._config = config or PlatformConfig()
        self._started_at = datetime.now(timezone.utc)

        # ── Core runtime ──
        self.runtime = ResearchRuntime()
        self.manager = ResearchManager()
        self.controller = ResearchController()

        # ── Knowledge ──
        self.knowledge_engine = KnowledgeEngine()
        self.prompt_library = PromptLibrary()

        # ── Planning & reasoning ──
        self.task_planner = TaskPlanner()
        self.hypothesis_engine = HypothesisEngine()
        self.evidence_engine = EvidenceEngine()
        self.citation_manager = CitationManager()

        # ── Session & workspace ──
        self.workspace = ResearchWorkspace()
        self.memory = ResearchMemory()

        # ── Pipeline ──
        self.pipeline = ResearchPipeline(
            knowledge_engine=self.knowledge_engine,
            task_planner=self.task_planner,
            hypothesis_engine=self.hypothesis_engine,
            evidence_engine=self.evidence_engine,
            citation_manager=self.citation_manager,
        )
        self.report_generator = ReportGenerator()

        # ── Tracking ──
        self.experiment_tracker = ExperimentTracker()
        self.artifact_registry = ArtifactRegistry()
        self.notebook_manager = NotebookManager() if self._config.enable_notebooks else None

        # ── Gateway & orchestrator (top-level) ──
        self.gateway = ResearchGateway(
            platform=self,
            workspace=self.workspace,
            memory=self.memory,
        )
        self.orchestrator = ResearchOrchestrator(
            gateway=self.gateway,
            pipeline=self.pipeline,
            knowledge_engine=self.knowledge_engine,
            report_generator=self.report_generator,
            workspace=self.workspace,
        )

        # ── Observability ──
        self._metrics = ResearchMetrics()
        self._telemetry = ResearchTelemetry()
        self._diagnostics = ResearchDiagnostics()
        self._health = ResearchHealthChecker()

        self._status = PlatformStatus.READY
        logger.info("AI Research Platform v%s initialized", self.VERSION)

    # ── Public API ──

    async def start(self) -> None:
        """Start the research platform and all subsystems."""
        self._status = PlatformStatus.INITIALIZING
        await self.runtime.start()
        await self.knowledge_engine.start()
        self._status = PlatformStatus.READY
        logger.info("AI Research Platform started")

    async def stop(self) -> None:
        """Gracefully shutdown the research platform."""
        self._status = PlatformStatus.SHUTDOWN
        await self.runtime.stop()
        await self.knowledge_engine.stop()
        logger.info("AI Research Platform stopped")

    async def submit_research(
        self,
        question: str,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Submit a research question and receive a structured analysis report.

        This is the primary entry point for all research workflows.
        """
        self._metrics.increment_request()
        with self._telemetry.trace("research.submit") as span:
            result = await self.orchestrator.execute(
                question=question,
                context=context or {},
                session_id=session_id,
                user_id=user_id,
            )
            span.set_attribute("session_id", result.get("session_id", ""))
            return result

    def create_session(self, user_id: str, title: str = "") -> ResearchSession:
        """Create a new research session."""
        session = ResearchSession(user_id=user_id, title=title)
        self.workspace.add_session(session)
        return session

    def get_info(self) -> PlatformInfo:
        """Get platform status and metrics."""
        uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()
        return PlatformInfo(
            status=self._status,
            version=self.VERSION,
            uptime_seconds=uptime,
            active_sessions=self.workspace.active_session_count,
            total_requests=self._metrics.total_requests,
            component_statuses=self._health.check_all(),
        )

    @property
    def metrics(self) -> ResearchMetrics:
        return self._metrics

    @property
    def telemetry(self) -> ResearchTelemetry:
        return self._telemetry

    @property
    def diagnostics(self) -> ResearchDiagnostics:
        return self._diagnostics

    @property
    def health(self) -> ResearchHealthChecker:
        return self._health
