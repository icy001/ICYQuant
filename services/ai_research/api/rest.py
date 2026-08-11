"""
ICYQuant AI Research REST API.

Provides HTTP REST endpoints for the AI Research Platform, including
research submission, session management, knowledge search, and report retrieval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RESTConfig:
    host: str = "0.0.0.0"
    port: int = 8100
    prefix: str = "/api/v1/research"
    enable_cors: bool = True
    enable_docs: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIResponse:
    """Standardized REST API response."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    request_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ResearchRESTAPI:
    """REST API endpoints for the AI Research Platform.

    Endpoints:
        POST   /research          — Submit a research question
        GET    /research/{id}     — Get research result
        GET    /sessions          — List research sessions
        POST   /sessions          — Create a research session
        GET    /sessions/{id}     — Get session details
        DELETE /sessions/{id}     — Close a session
        GET    /knowledge/search  — Search the knowledge base
        POST   /knowledge/index   — Index a document
        GET    /reports/{id}      — Get a research report
        GET    /experiments       — List experiments
        GET    /health            — Health check
    """

    def __init__(self, platform: Any = None, config: Optional[RESTConfig] = None) -> None:
        self._platform = platform
        self._config = config or RESTConfig()
        self._request_count = 0

    async def handle_submit_research(self, body: dict[str, Any]) -> APIResponse:
        """POST /research — Submit a research question."""
        self._request_count += 1
        question = body.get("question", "")
        context = body.get("context", {})
        session_id = body.get("session_id")
        user_id = body.get("user_id")

        if not question:
            return APIResponse(success=False, error="Question is required")

        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        try:
            result = await self._platform.submit_research(
                question=question,
                context=context,
                session_id=session_id,
                user_id=user_id,
            )
            return APIResponse(success=True, data=result)
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    async def handle_list_sessions(self, user_id: str = "") -> APIResponse:
        """GET /sessions — List research sessions."""
        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        sessions = []
        if user_id:
            sessions = self._platform.workspace.list_sessions_by_user(user_id)
        else:
            sessions = self._platform.workspace.list_active_sessions()

        return APIResponse(success=True, data={
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })

    async def handle_create_session(self, body: dict[str, Any]) -> APIResponse:
        """POST /sessions — Create a research session."""
        user_id = body.get("user_id", "anonymous")
        title = body.get("title", "")

        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        session = self._platform.create_session(user_id=user_id, title=title)
        return APIResponse(success=True, data=session.to_dict())

    async def handle_get_session(self, session_id: str) -> APIResponse:
        """GET /sessions/{id} — Get session details."""
        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        session = self._platform.workspace.get_session(session_id)
        if session is None:
            return APIResponse(success=False, error="Session not found")

        return APIResponse(success=True, data=session.to_dict())

    async def handle_search_knowledge(self, query_params: dict[str, Any]) -> APIResponse:
        """GET /knowledge/search — Search the knowledge base."""
        query = query_params.get("q", "")
        top_k = int(query_params.get("top_k", 10))

        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        results = await self._platform.knowledge_engine.search(query=query, top_k=top_k)
        return APIResponse(success=True, data={
            "query": query,
            "results": results,
            "total": len(results),
        })

    async def handle_get_report(self, report_id: str) -> APIResponse:
        """GET /reports/{id} — Get a research report."""
        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        report = self._platform.report_generator.get_report(report_id)
        if report is None:
            return APIResponse(success=False, error="Report not found")

        return APIResponse(success=True, data={
            "report_id": report.report_id,
            "title": report.title,
            "summary": report.summary,
            "conclusions": report.conclusions,
            "confidence": report.confidence,
            "status": report.status.value,
        })

    async def handle_health(self) -> APIResponse:
        """GET /health — Health check."""
        if self._platform is None:
            return APIResponse(success=False, error="Platform not available")

        info = self._platform.get_info()
        return APIResponse(success=True, data={
            "status": info.status.value,
            "version": info.version,
            "uptime_seconds": info.uptime_seconds,
            "active_sessions": info.active_sessions,
        })

    @property
    def total_requests(self) -> int:
        return self._request_count
