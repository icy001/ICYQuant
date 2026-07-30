"""
Knowledge API endpoints.

REST API for the Knowledge Intelligence Layer.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.knowledge.service import (
    KnowledgeService, KnowledgeConfig, AnalysisRequest, AnalysisResult,
    PipelineResult, PipelineStatus,
)
from services.knowledge.nlp_processor import NLPTask
from services.knowledge.event_engine import EventType as KnowledgeEventType

logger = logging.getLogger(__name__)


# ── API Response Models ─────────────────────────────────────────────────────

@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool = True
    data: Any = None
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
        }


@dataclass
class ErrorResponse:
    """Error response."""

    success: bool = False
    error: str = ""
    detail: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "detail": self.detail,
            "timestamp": self.timestamp.isoformat(),
        }


# ── Knowledge API Controller ─────────────────────────────────────────────────

class KnowledgeAPI:
    """
    Knowledge Intelligence API Controller.

    Provides endpoints for:
    - Document analysis
    - Entity graph queries
    - Event alpha signals
    - Sentiment summaries
    - Semantic search
    """

    def __init__(self, service: Optional[KnowledgeService] = None):
        self.service = service or KnowledgeService()

    # ── POST /analyze ───────────────────────────────────────────────────────

    def analyze(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a document through the knowledge pipeline.

        Request:
            {
                "text": "Company increases AI investment...",
                "title": "Optional title",
                "source": "reuters",
                "symbols": ["NVDA"],
                "generate_signals": true
            }

        Returns:
            {
                "sentiment": "positive",
                "event": "CAPEX_INCREASE",
                "entities": [...],
                "signals": [...]
            }
        """
        try:
            text = request_body.get("text", "")
            if not text:
                return ErrorResponse(error="Missing required field: text").to_dict()

            request = AnalysisRequest(
                request_id=str(uuid.uuid4()),
                text=text,
                title=request_body.get("title", ""),
                source=request_body.get("source", ""),
                url=request_body.get("url", ""),
                symbols=request_body.get("symbols", []),
                language=request_body.get("language", "en"),
                generate_signals=request_body.get("generate_signals", False),
            )

            result = self.service.analyze(request)

            return APIResponse(
                success=True,
                data={
                    "request_id": result.request_id,
                    "topics": result.topics,
                    "summary": result.summary,
                    "sentiment": result.sentiment_direction,
                    "sentiment_score": result.sentiment.score if result.sentiment else 0.5,
                    "entity_names": result.entity_names,
                    "entities": [e.to_dict() for e in result.entities],
                    "events": [e.to_dict() for e in result.events],
                    "primary_event": result.primary_event.to_dict() if result.primary_event else None,
                    "signals": [s.to_dict() for s in result.signals],
                    "processing_time_ms": result.processing_time_ms,
                },
                message=f"Analysis complete: {len(result.entities)} entities, {len(result.events)} events",
                request_id=result.request_id,
            ).to_dict()

        except Exception as e:
            logger.exception("Error in analyze endpoint")
            return ErrorResponse(error="Analysis failed", detail=str(e)).to_dict()

    # ── GET /graph/{entity} ─────────────────────────────────────────────────

    def get_entity_graph(
        self, entity: str, depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get knowledge graph for an entity.

        Returns:
            {
                "entity": "NVIDIA",
                "relations": ["TSMC", "SK Hynix", ...],
                "graph_stats": {...}
            }
        """
        try:
            result = self.service.get_entity_graph(entity, depth)
            if "error" in result:
                return ErrorResponse(error="Entity not found", detail=result["error"]).to_dict()
            return APIResponse(
                success=True,
                data=result,
                message=f"Graph for {entity}",
            ).to_dict()
        except Exception as e:
            logger.exception("Error in graph endpoint")
            return ErrorResponse(error="Graph query failed", detail=str(e)).to_dict()

    # ── GET /event-alpha ────────────────────────────────────────────────────

    def get_event_alpha(
        self, min_confidence: float = 0.3
    ) -> Dict[str, Any]:
        """
        Get event-driven alpha signals.

        Returns:
            {
                "signals": [
                    {"symbol": "NVDA", "signal": "BUY", "confidence": 0.82},
                    ...
                ]
            }
        """
        try:
            signals = self.service.get_event_alpha(min_confidence)
            return APIResponse(
                success=True,
                data={
                    "signals": signals,
                    "count": len(signals),
                },
                message=f"Found {len(signals)} alpha signals",
            ).to_dict()
        except Exception as e:
            logger.exception("Error in event-alpha endpoint")
            return ErrorResponse(error="Alpha query failed", detail=str(e)).to_dict()

    # ── GET /sentiment/{symbol} ─────────────────────────────────────────────

    def get_sentiment(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get sentiment summary for symbols.

        Returns:
            {
                "NVDA": {"sentiment": {...}, "momentum": {...}}
            }
        """
        try:
            summary = self.service.get_sentiment_summary(symbols)
            return APIResponse(
                success=True,
                data=summary,
                message=f"Sentiment for {len(symbols)} symbols",
            ).to_dict()
        except Exception as e:
            logger.exception("Error in sentiment endpoint")
            return ErrorResponse(error="Sentiment query failed", detail=str(e)).to_dict()

    # ── POST /search ────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Semantic search over knowledge base.

        Returns:
            {
                "results": [
                    {"document_id": "...", "similarity": 0.95, ...}
                ]
            }
        """
        try:
            results = self.service.search_knowledge(query, top_k)
            return APIResponse(
                success=True,
                data={
                    "query": query,
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                },
                message=f"Found {len(results)} results",
            ).to_dict()
        except Exception as e:
            logger.exception("Error in search endpoint")
            return ErrorResponse(error="Search failed", detail=str(e)).to_dict()

    # ── POST /ingest ────────────────────────────────────────────────────────

    def ingest_documents(
        self, documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingest documents for processing.

        Request:
            [
                {
                    "title": "...",
                    "content": "...",
                    "source": "reuters",
                    "symbols": ["NVDA"]
                }
            ]
        """
        try:
            from services.knowledge.ingestion import RawDocument, DocumentType, DataSource

            raw_docs = []
            for doc in documents:
                raw_docs.append(RawDocument(
                    title=doc.get("title", ""),
                    content=doc.get("content", ""),
                    source=DataSource(doc.get("source", "custom_api")),
                    doc_type=DocumentType(doc.get("doc_type", "news_article")),
                    url=doc.get("url", ""),
                    symbols=doc.get("symbols", []),
                    language=doc.get("language", "en"),
                ))

            result = self.service.run_pipeline(raw_docs, generate_signals=True)

            return APIResponse(
                success=result.status == PipelineStatus.COMPLETED,
                data={
                    "pipeline_id": result.pipeline_id,
                    "status": result.status.value,
                    "documents_ingested": result.documents_ingested,
                    "docs_processed": result.docs_processed,
                    "entities_extracted": result.entities_extracted,
                    "events_extracted": result.events_extracted,
                    "signals_generated": result.signals_generated,
                    "duration_ms": result.duration_ms,
                    "errors": result.errors,
                },
                message=f"Pipeline {result.status.value}: {result.docs_processed} docs processed",
            ).to_dict()
        except Exception as e:
            logger.exception("Error in ingest endpoint")
            return ErrorResponse(error="Ingestion failed", detail=str(e)).to_dict()

    # ── GET /health ─────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Health check."""
        return APIResponse(
            success=True,
            data={
                "status": "healthy",
                "graph_nodes": self.service.graph.node_count,
                "graph_edges": self.service.graph.edge_count,
                "embeddings_count": self.service.embedding_engine.embedding_count,
                "ingested_docs": self.service.ingestion.document_count,
                "events_count": len(self.service.event_engine._events),
            },
            message="Knowledge service is healthy",
        ).to_dict()
