"""
ICYQuant Research Pipeline — staged processing pipeline for research workflows.

Executes the research pipeline stages: task planning, knowledge retrieval,
hypothesis generation, evidence collection, and citation management,
with observability at each stage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    HYPOTHESIZING = "hypothesizing"
    EVIDENCE = "evidence"
    REPORTING = "reporting"
    DONE = "done"


@dataclass
class PipelineResult:
    stage: PipelineStage
    output: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None


class ResearchPipeline:
    """Staged processing pipeline for AI research workflows.

    Each stage transforms input → output with:
        - Metrics collection (duration, success/failure)
        - Error isolation (stage failures don't crash the pipeline)
        - Pause/resume support
        - Drain capability for graceful shutdown
    """

    def __init__(
        self,
        knowledge_engine: Any = None,
        task_planner: Any = None,
        hypothesis_engine: Any = None,
        evidence_engine: Any = None,
        citation_manager: Any = None,
    ) -> None:
        self._knowledge_engine = knowledge_engine
        self._task_planner = task_planner
        self._hypothesis_engine = hypothesis_engine
        self._evidence_engine = evidence_engine
        self._citation_manager = citation_manager

        self._paused = False
        self._stage_results: list[PipelineResult] = []
        self._total_processed = 0

    def pause(self) -> None:
        """Pause pipeline processing."""
        self._paused = True
        logger.info("Research pipeline paused")

    def resume(self) -> None:
        """Resume pipeline processing."""
        self._paused = False
        logger.info("Research pipeline resumed")

    async def drain(self) -> None:
        """Complete in-flight work and stop accepting new work."""
        self._paused = True
        logger.info("Research pipeline draining")

    async def plan_task(
        self,
        question: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Stage 1: Decompose research question into sub-tasks."""
        if self._paused:
            return []

        start = datetime.now(timezone.utc)
        try:
            if self._task_planner is not None:
                plan = await self._task_planner.plan(question=question, context=context)
            else:
                plan = [{"step": 1, "action": "analyze", "description": question}]

            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            self._record(PipelineStage.PLANNING, {"plan": plan}, duration)
            return plan
        except Exception as exc:
            self._record(PipelineStage.PLANNING, {}, 0.0, str(exc))
            return []

    async def retrieve_knowledge(
        self,
        query: str,
        top_k: int = 10,
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Stage 2: Semantic knowledge retrieval."""
        if self._paused:
            return []

        start = datetime.now(timezone.utc)
        try:
            if self._knowledge_engine is not None:
                docs = await self._knowledge_engine.search(
                    query=query,
                    top_k=top_k,
                    context=context or {},
                )
            else:
                docs = []

            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            self._record(PipelineStage.RETRIEVING, {"doc_count": len(docs)}, duration)
            return docs
        except Exception as exc:
            self._record(PipelineStage.RETRIEVING, {}, 0.0, str(exc))
            return []

    async def generate_hypotheses(
        self,
        question: str,
        retrieved_docs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Stage 3: Generate research hypotheses."""
        if self._paused:
            return []

        start = datetime.now(timezone.utc)
        try:
            if self._hypothesis_engine is not None:
                hypotheses = await self._hypothesis_engine.generate(
                    question=question,
                    documents=retrieved_docs,
                    context=context,
                )
            else:
                hypotheses = [{"statement": f"Hypothesis for: {question}", "confidence": 0.5}]

            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            self._record(PipelineStage.HYPOTHESIZING, {"hypothesis_count": len(hypotheses)}, duration)
            return hypotheses
        except Exception as exc:
            self._record(PipelineStage.HYPOTHESIZING, {}, 0.0, str(exc))
            return []

    async def collect_evidence(
        self,
        hypotheses: list[dict[str, Any]],
        retrieved_docs: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Stage 4: Collect evidence for/against hypotheses."""
        if self._paused:
            return {"evidence": [], "citations": []}

        start = datetime.now(timezone.utc)
        try:
            evidence = []
            citations = []

            if self._evidence_engine is not None:
                evidence = await self._evidence_engine.collect(
                    hypotheses=hypotheses,
                    documents=retrieved_docs,
                    context=context,
                )

            if self._citation_manager is not None:
                citations = await self._citation_manager.extract_citations(
                    documents=retrieved_docs,
                    evidence=evidence,
                )

            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            self._record(PipelineStage.EVIDENCE, {
                "evidence_count": len(evidence),
                "citation_count": len(citations),
            }, duration)
            return {"evidence": evidence, "citations": citations}
        except Exception as exc:
            self._record(PipelineStage.EVIDENCE, {}, 0.0, str(exc))
            return {"evidence": [], "citations": []}

    def _record(
        self,
        stage: PipelineStage,
        output: dict[str, Any],
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        self._stage_results.append(PipelineResult(
            stage=stage,
            output=output,
            duration_ms=duration_ms,
            error=error,
        ))
        self._total_processed += 1

    @property
    def stage_results(self) -> list[PipelineResult]:
        return list(self._stage_results)

    @property
    def total_processed(self) -> int:
        return self._total_processed

    @property
    def is_paused(self) -> bool:
        return self._paused
