"""
ICYQuant AI Research gRPC API.

Provides high-performance gRPC endpoints for the AI Research Platform,
supporting streaming responses for long-running research tasks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class ServiceMethod(str, Enum):
    SUBMIT_RESEARCH = "SubmitResearch"
    STREAM_RESEARCH = "StreamResearch"
    SEARCH_KNOWLEDGE = "SearchKnowledge"
    INDEX_DOCUMENT = "IndexDocument"
    CREATE_SESSION = "CreateSession"
    GET_REPORT = "GetReport"
    LIST_EXPERIMENTS = "ListExperiments"
    HEALTH_CHECK = "HealthCheck"


@dataclass
class GRPCConfig:
    host: str = "0.0.0.0"
    port: int = 8101
    max_message_size_mb: int = 100
    enable_reflection: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GRPCResponse:
    """Standardized gRPC response."""
    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error_code: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ResearchGRPCAPI:
    """gRPC API for the AI Research Platform.

    Services:
        - ResearchService: Submit and stream research tasks
        - KnowledgeService: Search and index knowledge
        - SessionService: Session management
        - ReportService: Report retrieval
        - ExperimentService: Experiment management
    """

    def __init__(self, platform: Any = None, config: Optional[GRPCConfig] = None) -> None:
        self._platform = platform
        self._config = config or GRPCConfig()
        self._request_count = 0

    async def submit_research(self, request: dict[str, Any]) -> GRPCResponse:
        """SubmitResearch — Submit a research question synchronously."""
        self._request_count += 1

        if self._platform is None:
            return GRPCResponse(success=False, message="Platform not available", error_code=1)

        try:
            result = await self._platform.submit_research(
                question=request.get("question", ""),
                context=request.get("context", {}),
                session_id=request.get("session_id"),
                user_id=request.get("user_id"),
            )
            return GRPCResponse(success=True, message="Research completed", data=result)
        except Exception as exc:
            return GRPCResponse(success=False, message=str(exc), error_code=2)

    async def stream_research(self, request: dict[str, Any]) -> AsyncIterator[GRPCResponse]:
        """StreamResearch — Stream research progress updates."""
        self._request_count += 1

        # Phase 1: Planning
        yield GRPCResponse(success=True, message="Phase: Planning", data={"phase": "planning"})

        # Phase 2: Retrieving
        yield GRPCResponse(success=True, message="Phase: Retrieving knowledge", data={"phase": "retrieving"})

        # Phase 3: Reasoning
        yield GRPCResponse(success=True, message="Phase: Generating hypotheses", data={"phase": "reasoning"})

        # Phase 4: Evidence
        yield GRPCResponse(success=True, message="Phase: Collecting evidence", data={"phase": "evidence"})

        # Phase 5: Reporting
        yield GRPCResponse(success=True, message="Phase: Generating report", data={"phase": "reporting"})

        # Final result
        if self._platform is not None:
            try:
                result = await self._platform.submit_research(
                    question=request.get("question", ""),
                    context=request.get("context", {}),
                    session_id=request.get("session_id"),
                    user_id=request.get("user_id"),
                )
                yield GRPCResponse(success=True, message="Research completed", data=result)
            except Exception as exc:
                yield GRPCResponse(success=False, message=str(exc), error_code=2)

    async def search_knowledge(self, request: dict[str, Any]) -> GRPCResponse:
        """SearchKnowledge — Search the knowledge base."""
        if self._platform is None:
            return GRPCResponse(success=False, message="Platform not available", error_code=1)

        results = await self._platform.knowledge_engine.search(
            query=request.get("query", ""),
            top_k=request.get("top_k", 10),
        )
        return GRPCResponse(success=True, data={"results": results, "total": len(results)})

    async def health_check(self) -> GRPCResponse:
        """HealthCheck — Service health check."""
        if self._platform is None:
            return GRPCResponse(success=False, message="Platform not available", error_code=1)

        info = self._platform.get_info()
        return GRPCResponse(success=True, message="Healthy", data={
            "status": info.status.value,
            "version": info.version,
            "uptime_seconds": info.uptime_seconds,
        })

    @property
    def total_requests(self) -> int:
        return self._request_count
