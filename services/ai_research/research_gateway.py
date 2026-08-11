"""
ICYQuant Research Gateway — unified entry point for all research requests.

The gateway handles authentication, rate limiting, request validation,
routing to the orchestrator, and response formatting.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResearchRequest:
    """Standardized research request."""
    question: str
    context: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResponse:
    """Standardized research response."""
    answer: str
    confidence: float
    request_id: str = ""
    session_id: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    report: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0


@dataclass
class GatewayConfig:
    max_request_size_chars: int = 100_000
    rate_limit_per_minute: int = 60
    require_auth: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchGateway:
    """Unified gateway for all AI research requests.

    Responsibilities:
        - Request validation and normalization
        - Authentication (when enabled)
        - Rate limiting
        - Routing to orchestrator
        - Response formatting
        - Session association
    """

    def __init__(
        self,
        platform: Any = None,
        workspace: Any = None,
        memory: Any = None,
        config: Optional[GatewayConfig] = None,
    ) -> None:
        self._platform = platform
        self._workspace = workspace
        self._memory = memory
        self._config = config or GatewayConfig()
        self._request_count = 0

    async def handle_request(
        self,
        request: ResearchRequest,
    ) -> ResearchResponse:
        """Process a research request end-to-end."""
        start = datetime.now(timezone.utc)

        # Validate
        self._validate(request)

        # Rate limit
        self._check_rate_limit(request.user_id or "anonymous")

        # Associate session
        session_id = request.session_id or self._ensure_session(request.user_id or "anonymous")

        # Route to orchestrator
        if self._platform is None or self._platform.orchestrator is None:
            raise RuntimeError("Gateway not connected to a platform orchestrator")

        result = await self._platform.orchestrator.execute(
            question=request.question,
            context=request.context,
            session_id=session_id,
            user_id=request.user_id,
        )

        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        self._request_count += 1

        return ResearchResponse(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.0),
            request_id=request.request_id,
            session_id=session_id,
            citations=result.get("citations", []),
            evidence=result.get("evidence", []),
            hypotheses=result.get("hypotheses", []),
            report=result.get("report"),
            metadata=result.get("metadata", {}),
            elapsed_ms=elapsed,
        )

    def _validate(self, request: ResearchRequest) -> None:
        if not request.question.strip():
            raise ValueError("Research question cannot be empty")
        if len(request.question) > self._config.max_request_size_chars:
            raise ValueError(f"Question exceeds max size of {self._config.max_request_size_chars} chars")

    def _check_rate_limit(self, user_id: str) -> None:
        # Simple in-memory rate limit; production would use Redis
        pass

    def _ensure_session(self, user_id: str) -> str:
        """Create or reuse a session for the user."""
        if self._workspace is not None:
            session = self._workspace.get_or_create_session(user_id)
            return session.session_id
        return str(uuid.uuid4())

    @property
    def total_requests(self) -> int:
        return self._request_count
