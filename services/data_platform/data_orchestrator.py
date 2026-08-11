"""
ICYQuant Unified Data Orchestrator.

Commit 16 Part 1.5 — Central orchestrator that coordinates all data
requests through a unified flow: Permission Check → Catalog Lookup →
Route to Subsystem → Response Assembly.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    """Phases of the orchestration pipeline."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    CATALOG_LOOKUP = "catalog_lookup"
    ROUTING = "routing"
    EXECUTION = "execution"
    TRANSFORMATION = "transformation"
    RESPONSE = "response"
    AUDIT = "audit"


@dataclass
class OrchestrationContext:
    """Context carried through the orchestration pipeline."""
    request_id: str = ""
    principal: str = ""
    dataset_id: str = ""
    phases_completed: list[str] = field(default_factory=list)
    routing_target: str = ""
    started_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class OrchestrationError(Exception):
    """Error during orchestration pipeline execution."""
    def __init__(self, phase: OrchestrationPhase, message: str) -> None:
        self.phase = phase
        self.message = message
        super().__init__(f"[{phase.value}] {message}")


class DataOrchestrator:
    """Central orchestrator for unified data access.

    Orchestration flow:
      1. Authentication — verify caller identity
      2. Authorization  — check permissions (RBAC/ABAC)
      3. Catalog Lookup — resolve dataset, check availability
      4. Routing        — determine backend (live/historical/replay)
      5. Execution      — dispatch to appropriate subsystem
      6. Transformation — apply transforms, aggregations
      7. Response       — assemble and return result
      8. Audit          — record access for compliance
    """

    def __init__(
        self,
        access_control: Any = None,
        catalog: Any = None,
        pipeline: Any = None,
        audit: Any = None,
    ) -> None:
        self._access_control = access_control
        self._catalog = catalog
        self._pipeline = pipeline
        self._audit = audit
        self._orchestration_count = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("DataOrchestrator started")

    async def stop(self) -> None:
        logger.info("DataOrchestrator stopped")

    # ------------------------------------------------------------------
    # Core Orchestration
    # ------------------------------------------------------------------

    async def subscribe(self, request: Any) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate a real-time subscription request."""
        ctx = await self._create_context(request)
        try:
            await self._authorize(ctx, "subscribe")
            await self._catalog_lookup(ctx)
            self._routing_target = "streaming"

            if self._pipeline:
                async for event in self._pipeline.subscribe_stream(request):
                    yield event
            else:
                return  # empty stream

            await self._audit_log(ctx, "subscribe", success=True)
        except OrchestrationError as exc:
            logger.warning("Orchestration error: %s", exc)
            await self._audit_log(ctx, "subscribe", success=False, error=str(exc))
            raise

    async def query(self, request: Any) -> Any:
        """Orchestrate a historical query request."""
        ctx = await self._create_context(request)
        try:
            await self._authorize(ctx, "query")
            await self._catalog_lookup(ctx)

            if request.as_of:
                self._routing_target = "data_lake"
            else:
                self._routing_target = "data_lake"

            response = None
            if self._pipeline:
                response = await self._pipeline.query(request)

            await self._audit_log(ctx, "query", success=True)
            return response
        except OrchestrationError as exc:
            logger.warning("Orchestration error: %s", exc)
            await self._audit_log(ctx, "query", success=False, error=str(exc))
            raise

    async def replay(self, request: Any) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate a replay request."""
        ctx = await self._create_context(request)
        try:
            await self._authorize(ctx, "replay")
            await self._catalog_lookup(ctx)
            self._routing_target = "data_lake"

            if self._pipeline:
                async for event in self._pipeline.replay_stream(request):
                    yield event
            else:
                return

            await self._audit_log(ctx, "replay", success=True)
        except OrchestrationError as exc:
            logger.warning("Orchestration error: %s", exc)
            await self._audit_log(ctx, "replay", success=False, error=str(exc))
            raise

    async def publish(self, request: Any) -> Any:
        """Orchestrate a data publish/ingest request."""
        ctx = await self._create_context(request)
        try:
            await self._authorize(ctx, "publish")
            await self._catalog_lookup(ctx)
            self._routing_target = "streaming"

            response = None
            if self._pipeline:
                response = await self._pipeline.publish(request)

            await self._audit_log(ctx, "publish", success=True)
            return response
        except OrchestrationError as exc:
            logger.warning("Orchestration error: %s", exc)
            await self._audit_log(ctx, "publish", success=False, error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Pipeline Phases
    # ------------------------------------------------------------------

    async def _authorize(self, ctx: OrchestrationContext, operation: str) -> None:
        """Check authorization for the requested operation."""
        ctx.phases_completed.append(OrchestrationPhase.AUTHORIZATION.value)
        if self._access_control:
            allowed = await self._access_control.check_access(
                ctx.principal, ctx.dataset_id, operation,
            )
            if not allowed:
                raise OrchestrationError(
                    OrchestrationPhase.AUTHORIZATION,
                    f"Access denied for {ctx.principal} on {ctx.dataset_id}",
                )

    async def _catalog_lookup(self, ctx: OrchestrationContext) -> None:
        """Look up the dataset in the catalog."""
        ctx.phases_completed.append(OrchestrationPhase.CATALOG_LOOKUP.value)
        if self._catalog:
            entry = await self._catalog.get(ctx.dataset_id)
            if not entry:
                raise OrchestrationError(
                    OrchestrationPhase.CATALOG_LOOKUP,
                    f"Dataset not found: {ctx.dataset_id}",
                )

    async def _audit_log(
        self, ctx: OrchestrationContext, operation: str,
        success: bool = True, error: str = "",
    ) -> None:
        """Record an audit entry for the operation."""
        ctx.phases_completed.append(OrchestrationPhase.AUDIT.value)
        if self._audit:
            await self._audit.log(
                principal=ctx.principal,
                operation=operation,
                dataset_id=ctx.dataset_id,
                request_id=ctx.request_id,
                success=success,
                error=error,
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _create_context(self, request: Any) -> OrchestrationContext:
        async with self._lock:
            self._orchestration_count += 1
            req_id = f"orch-{self._orchestration_count:08d}"

        principal = getattr(request, 'principal', 'anonymous')
        dataset_id = getattr(request, 'dataset_id', '')
        return OrchestrationContext(
            request_id=req_id,
            principal=principal,
            dataset_id=dataset_id,
            started_at=datetime.now(timezone.utc),
        )

    @property
    def orchestration_count(self) -> int:
        return self._orchestration_count

    @property
    def routing_target(self) -> str:
        return self._routing_target
