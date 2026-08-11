"""
ICYQuant Research Orchestrator — coordinates the full research workflow.

Orchestrates the end-to-end research flow: task planning → knowledge
retrieval → hypothesis generation → evidence collection → report
generation, with session state management.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    REASONING = "reasoning"
    EVIDENCE = "evidence"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestrationContext:
    """Mutable context carried through the orchestration pipeline."""
    question: str
    context: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    user_id: str = ""
    phase: OrchestrationPhase = OrchestrationPhase.PLANNING

    # Intermediate results
    plan: list[dict[str, Any]] = field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)

    # Final output
    answer: str = ""
    confidence: float = 0.0
    report: Optional[dict[str, Any]] = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    phase_timings: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class ResearchOrchestrator:
    """Coordinates the full AI research workflow.

    Flow:
        1. Task Planning    — decompose the research question
        2. Knowledge Retrieval — semantic search + knowledge graph
        3. Hypothesis Generation — formulate testable hypotheses
        4. Evidence Collection — gather supporting/counter evidence
        5. Report Generation — produce structured research report

    All phases are tracked in the OrchestrationContext for auditability.
    """

    def __init__(
        self,
        gateway: Any = None,
        pipeline: Any = None,
        knowledge_engine: Any = None,
        report_generator: Any = None,
        workspace: Any = None,
    ) -> None:
        self._gateway = gateway
        self._pipeline = pipeline
        self._knowledge_engine = knowledge_engine
        self._report_generator = report_generator
        self._workspace = workspace

    async def execute(
        self,
        question: str,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute the full research workflow."""
        ctx = OrchestrationContext(
            question=question,
            context=context or {},
            session_id=session_id or str(uuid.uuid4()),
            user_id=user_id or "anonymous",
        )

        try:
            # Phase 1: Task Planning
            ctx.phase = OrchestrationPhase.PLANNING
            await self._plan(ctx)

            # Phase 2: Knowledge Retrieval
            ctx.phase = OrchestrationPhase.RETRIEVING
            await self._retrieve(ctx)

            # Phase 3: Hypothesis Generation
            ctx.phase = OrchestrationPhase.REASONING
            await self._reason(ctx)

            # Phase 4: Evidence Collection
            ctx.phase = OrchestrationPhase.EVIDENCE
            await self._collect_evidence(ctx)

            # Phase 5: Report Generation
            ctx.phase = OrchestrationPhase.REPORTING
            await self._report(ctx)

            ctx.phase = OrchestrationPhase.COMPLETED

        except Exception as exc:
            ctx.phase = OrchestrationPhase.FAILED
            ctx.errors.append(str(exc))
            logger.error("Orchestration failed: %s", exc)

        return self._build_result(ctx)

    async def _plan(self, ctx: OrchestrationContext) -> None:
        """Decompose the research question into actionable sub-tasks."""
        if self._pipeline is not None:
            ctx.plan = await self._pipeline.plan_task(ctx.question, ctx.context)
        else:
            ctx.plan = [{"task": "analyze", "description": ctx.question}]

    async def _retrieve(self, ctx: OrchestrationContext) -> None:
        """Retrieve relevant knowledge from the knowledge engine."""
        if self._knowledge_engine is not None:
            ctx.retrieved_docs = await self._knowledge_engine.search(
                query=ctx.question,
                top_k=10,
                context=ctx.context,
            )

    async def _reason(self, ctx: OrchestrationContext) -> None:
        """Generate hypotheses based on retrieved knowledge."""
        if self._pipeline is not None:
            ctx.hypotheses = await self._pipeline.generate_hypotheses(
                question=ctx.question,
                retrieved_docs=ctx.retrieved_docs,
                context=ctx.context,
            )

    async def _collect_evidence(self, ctx: OrchestrationContext) -> None:
        """Collect supporting and counter evidence for each hypothesis."""
        if self._pipeline is not None:
            evidence_result = await self._pipeline.collect_evidence(
                hypotheses=ctx.hypotheses,
                retrieved_docs=ctx.retrieved_docs,
                context=ctx.context,
            )
            ctx.evidence = evidence_result.get("evidence", [])
            ctx.citations = evidence_result.get("citations", [])

    async def _report(self, ctx: OrchestrationContext) -> None:
        """Generate the final research report."""
        if self._report_generator is not None:
            ctx.report = await self._report_generator.generate(
                question=ctx.question,
                plan=ctx.plan,
                hypotheses=ctx.hypotheses,
                evidence=ctx.evidence,
                citations=ctx.citations,
            )
            ctx.answer = ctx.report.get("summary", "")
            ctx.confidence = ctx.report.get("confidence", 0.0)
        else:
            ctx.answer = f"Research completed for: {ctx.question}"
            ctx.confidence = 0.5

    def _build_result(self, ctx: OrchestrationContext) -> dict[str, Any]:
        return {
            "answer": ctx.answer,
            "confidence": ctx.confidence,
            "session_id": ctx.session_id,
            "phase": ctx.phase.value,
            "plan": ctx.plan,
            "hypotheses": ctx.hypotheses,
            "evidence": ctx.evidence,
            "citations": ctx.citations,
            "report": ctx.report,
            "errors": ctx.errors,
            "metadata": {
                "retrieved_doc_count": len(ctx.retrieved_docs),
                "hypothesis_count": len(ctx.hypotheses),
                "evidence_count": len(ctx.evidence),
                "citation_count": len(ctx.citations),
            },
        }
