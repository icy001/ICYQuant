"""
ICYQuant AI Research Platform — unified AI-powered quantitative research assistant.

Provides intelligent research workflows with knowledge retrieval, hypothesis
generation, evidence collection, report generation, and team collaboration.

Architecture:
    Unified Data Platform → Research Gateway → Orchestrator → Knowledge Engine
    → Research Pipeline → Report Generator → Research Workspace

Modules:
    - ai_research_platform:  Unified research platform entry point
    - research_runtime:      Runtime execution environment
    - research_manager:      Session lifecycle management
    - research_controller:   Operational control plane
    - research_gateway:      Unified research request gateway
    - research_session:      Stateful research conversation context
    - research_workspace:    Multi-session research environment
    - research_orchestrator: Full research workflow coordination
    - research_pipeline:     Staged processing pipeline
    - knowledge_engine:      Unified knowledge management
    - knowledge_graph:       Entity relationship network
    - knowledge_index:       Dual-index retrieval system
    - semantic_search:       Embedding-based semantic search
    - retrieval_engine:      RAG-ready context assembly
    - document_parser:       Multi-format document ingestion
    - research_memory:       Persistent context storage
    - prompt_library:        Curated research prompts
    - template_registry:     Report output templates
    - task_planner:          Research task decomposition
    - hypothesis_engine:     Hypothesis generation & validation
    - evidence_engine:       Systematic evidence collection
    - citation_manager:      Academic citation tracking
    - report_generator:      Automated report generation
    - notebook_manager:      Jupyter notebook integration
    - experiment_tracker:    ML experiment tracking
    - artifact_registry:     Research artifact storage
    - collaboration:         Team collaboration services
    - api:                   REST/gRPC/WebSocket APIs
    - metrics:               Prometheus metrics
    - telemetry:             Distributed tracing
    - diagnostics:           Platform diagnostics
    - health:                Health check & circuit breaker
"""

from __future__ import annotations

# ── Core Platform ──
from services.ai_research.ai_research_platform import (
    AIResearchPlatform,
    PlatformConfig,
    PlatformInfo,
    PlatformStatus,
)
from services.ai_research.research_runtime import (
    ResearchRuntime,
    RuntimeConfig,
    RuntimeState,
    RuntimeStats,
)
from services.ai_research.research_manager import (
    ResearchManager,
    ManagerConfig,
)
from services.ai_research.research_controller import (
    ResearchController,
    ControllerConfig,
    ControllerAction,
    ControllerTarget,
    AuditEntry,
)
from services.ai_research.research_gateway import (
    ResearchGateway,
    GatewayConfig,
    ResearchRequest,
    ResearchResponse,
)

# ── Workspace Layer ──
from services.ai_research.research_session import (
    ResearchSession,
    SessionStatus,
)
from services.ai_research.research_workspace import (
    ResearchWorkspace,
    WorkspaceConfig,
)
from services.ai_research.research_orchestrator import (
    ResearchOrchestrator,
    OrchestrationContext,
    OrchestrationPhase,
)
from services.ai_research.research_pipeline import (
    ResearchPipeline,
    PipelineStage,
    PipelineResult,
)

# ── Knowledge Engine ──
from services.ai_research.knowledge_engine import (
    KnowledgeEngine,
    KnowledgeDomain,
    KnowledgeDocument,
    DocumentStatus,
    SearchResult,
    SearchResponse,
)
from services.ai_research.knowledge_graph import (
    KnowledgeGraph,
    Entity,
    Relation,
    EntityType,
    RelationType,
)
from services.ai_research.knowledge_index import (
    KnowledgeIndex,
    IndexEntry,
)
from services.ai_research.semantic_search import (
    SemanticSearch,
    SearchQuery,
    SearchHit,
)
from services.ai_research.retrieval_engine import (
    RetrievalEngine,
    RetrievalContext,
    RetrievalConfig,
)
from services.ai_research.document_parser import (
    DocumentParser,
    ParsedDocument,
    DocumentFormat,
)

# ── Research Tools ──
from services.ai_research.research_memory import (
    ResearchMemory,
    MemoryEntry,
    MemoryType,
)
from services.ai_research.prompt_library import (
    PromptLibrary,
    Prompt,
    PromptCategory,
)
from services.ai_research.template_registry import (
    TemplateRegistry,
    Template,
    TemplateCategory,
    TemplateFormat,
)
from services.ai_research.task_planner import (
    TaskPlanner,
    TaskPlan,
    ResearchTask,
    TaskPriority,
    TaskStatus,
)
from services.ai_research.hypothesis_engine import (
    HypothesisEngine,
    Hypothesis,
    HypothesisStatus,
    HypothesisType,
)
from services.ai_research.evidence_engine import (
    EvidenceEngine,
    EvidenceItem,
    EvidenceDirection,
    EvidenceStrength,
)
from services.ai_research.citation_manager import (
    CitationManager,
    Citation,
    CitationContext,
    CitationStyle,
    SourceType,
)
from services.ai_research.report_generator import (
    ReportGenerator,
    ResearchReport,
    ReportFormat,
    ReportStatus,
)

# ── Notebook & Tracking ──
from services.ai_research.notebook_manager import (
    NotebookManager,
    Notebook,
    NotebookStatus,
)
from services.ai_research.experiment_tracker import (
    ExperimentTracker,
    Experiment,
    ExperimentStatus,
)
from services.ai_research.artifact_registry import (
    ArtifactRegistry,
    Artifact,
    ArtifactType,
    ArtifactFormat,
)

# ── Collaboration ──
from services.ai_research.collaboration.comment_service import (
    CommentService,
    Comment,
    CommentTarget,
)
from services.ai_research.collaboration.review_service import (
    ReviewService,
    Review,
    ReviewTarget,
    ReviewStatus,
)
from services.ai_research.collaboration.approval_workflow import (
    ApprovalWorkflow,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStep,
    ApprovalStepResult,
)
from services.ai_research.collaboration.sharing_manager import (
    SharingManager,
    ShareLink,
    SharePermission,
    ShareTarget,
)

# ── API ──
from services.ai_research.api.rest import (
    ResearchRESTAPI,
    RESTConfig,
    APIResponse,
)
from services.ai_research.api.grpc import (
    ResearchGRPCAPI,
    GRPCConfig,
    GRPCResponse,
    ServiceMethod,
)
from services.ai_research.api.websocket import (
    ResearchWebSocketAPI,
    WSConfig,
    WSMessage,
    WSMessageType,
)

# ── Observability ──
from services.ai_research.metrics import (
    ResearchMetrics,
    MetricSnapshot,
)
from services.ai_research.telemetry import (
    ResearchTelemetry,
    Trace,
    Span,
    TraceKind,
    SpanStatus,
)
from services.ai_research.diagnostics import (
    ResearchDiagnostics,
    DiagnosticResult,
)
from services.ai_research.health import (
    ResearchHealthChecker,
    ComponentHealth,
    HealthStatus,
)

# ── Legacy compatibility ──
from services.ai_research.request import ResearchRequest as LegacyResearchRequest  # noqa: F401
from services.ai_research.response import ResearchResponse as LegacyResearchResponse  # noqa: F401
from services.ai_research.agent import ResearchAgent  # noqa: F401
from services.ai_research.tools import ResearchTool  # noqa: F401
from services.ai_research.repository import ResearchRepository  # noqa: F401
from services.ai_research.service import AIResearchService  # noqa: F401

__all__ = [
    # Core Platform
    "AIResearchPlatform",
    "PlatformConfig",
    "PlatformInfo",
    "PlatformStatus",
    "ResearchRuntime",
    "RuntimeConfig",
    "RuntimeState",
    "RuntimeStats",
    "ResearchManager",
    "ManagerConfig",
    "ResearchController",
    "ControllerConfig",
    "ControllerAction",
    "ControllerTarget",
    "ResearchGateway",
    "GatewayConfig",
    # Workspace
    "ResearchSession",
    "SessionStatus",
    "ResearchWorkspace",
    "WorkspaceConfig",
    "ResearchOrchestrator",
    "OrchestrationPhase",
    "ResearchPipeline",
    "PipelineStage",
    "PipelineResult",
    # Knowledge
    "KnowledgeEngine",
    "KnowledgeDomain",
    "KnowledgeGraph",
    "KnowledgeIndex",
    "SemanticSearch",
    "RetrievalEngine",
    "DocumentParser",
    # Tools
    "ResearchMemory",
    "MemoryType",
    "PromptLibrary",
    "PromptCategory",
    "TemplateRegistry",
    "TaskPlanner",
    "HypothesisEngine",
    "HypothesisStatus",
    "EvidenceEngine",
    "CitationManager",
    "ReportGenerator",
    "ReportFormat",
    # Tracking
    "NotebookManager",
    "ExperimentTracker",
    "ArtifactRegistry",
    # Collaboration
    "CommentService",
    "ReviewService",
    "ApprovalWorkflow",
    "SharingManager",
    # API
    "ResearchRESTAPI",
    "ResearchGRPCAPI",
    "ResearchWebSocketAPI",
    # Observability
    "ResearchMetrics",
    "ResearchTelemetry",
    "ResearchDiagnostics",
    "ResearchHealthChecker",
]
