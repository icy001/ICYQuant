"""
Knowledge Service — Orchestrator for the Knowledge Intelligence Layer.

Unifies all knowledge components:
- Ingestion → NLP → Sentiment → Entity Extraction → Event Extraction
- → Knowledge Graph → Relation Engine → Embedding → Alpha Signals
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.knowledge.ingestion import (
    IngestionPipeline, IngestionConfig, RawDocument, DocumentType, DataSource,
)
from services.knowledge.news_engine import (
    NewsEngine, NewsConfig, NewsArticle, NewsCategory, NewsSentiment, NewsImpact,
)
from services.knowledge.nlp_processor import (
    NLPProcessor, NLPConfig, NLPResult, NLPTask, NLPTopic,
)
from services.knowledge.sentiment import (
    SentimentEngine, SentimentConfig, SentimentResult, SentimentDirection,
    SentimentMomentum, SentimentAcceleration,
)
from services.knowledge.entity_extraction import (
    EntityExtractor, ExtractionConfig, ExtractedEntity, EntityType,
)
from services.knowledge.event_engine import (
    EventEngine, EventConfig, MarketEvent, EventType as KnowledgeEventType,
    EventImpact,
)
from services.knowledge.knowledge_graph import (
    KnowledgeGraph, GraphNode, NodeType, EdgeType, GraphQuery,
)
from services.knowledge.relation_engine import (
    RelationEngine, RelationConfig, EntityRelation, RelationType, RelationStrength,
)
from services.knowledge.embedding import (
    EmbeddingEngine, EmbeddingConfig, DocumentEmbedding, SimilarityResult, SearchQuery,
)
from services.knowledge.alpha_signal import (
    EventAlphaEngine, AlphaConfig, AlphaSignal, SignalType, SignalConfidence,
    EventToSignalMapping, SignalPipeline,
)

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class PipelineStatus(str, Enum):
    IDLE = "idle"
    INGESTING = "ingesting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AnalysisRequest:
    """Request to analyze a document through the knowledge pipeline."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    title: str = ""
    source: str = ""
    url: str = ""
    symbols: List[str] = field(default_factory=list)
    language: str = "en"

    # Optional overrides
    tasks: Optional[List[NLPTask]] = None
    extract_entities: bool = True
    extract_events: bool = True
    compute_sentiment: bool = True
    generate_signals: bool = False

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnalysisResult:
    """Combined analysis result from the knowledge pipeline."""

    request_id: str = ""

    # NLP
    nlp_result: Optional[NLPResult] = None
    topics: List[str] = field(default_factory=list)

    # Sentiment
    sentiment: Optional[SentimentResult] = None
    sentiment_direction: str = ""

    # News
    news_article: Optional[NewsArticle] = None

    # Entities
    entities: List[ExtractedEntity] = field(default_factory=list)

    # Events
    events: List[MarketEvent] = field(default_factory=list)
    primary_event: Optional[MarketEvent] = None

    # Signals
    signals: List[AlphaSignal] = field(default_factory=list)

    # Timing
    processing_time_ms: float = 0.0

    # Summary
    summary: str = ""
    entity_names: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    pipeline_id: str = ""
    status: PipelineStatus = PipelineStatus.IDLE
    documents_ingested: int = 0
    docs_processed: int = 0
    entities_extracted: int = 0
    events_extracted: int = 0
    signals_generated: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0


@dataclass
class KnowledgeConfig:
    """Top-level configuration for the Knowledge Service."""

    # Sub-configs
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    nlp: NLPConfig = field(default_factory=NLPConfig)
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    event: EventConfig = field(default_factory=EventConfig)
    relation: RelationConfig = field(default_factory=RelationConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    alpha: AlphaConfig = field(default_factory=AlphaConfig)

    # Pipeline options
    enable_news_engine: bool = True
    enable_sentiment: bool = True
    enable_entities: bool = True
    enable_events: bool = True
    enable_graph: bool = True
    enable_embedding: bool = True
    enable_signals: bool = False


# ── Knowledge Service ────────────────────────────────────────────────────────

class KnowledgeService:
    """
    Unified Knowledge Intelligence Service.

    Orchestrates the entire alternative data → knowledge → alpha pipeline:
      1. Ingestion (news, reports, filings)
      2. NLP processing (topics, keywords, summarization)
      3. Sentiment analysis (direction, momentum, acceleration)
      4. Entity extraction (companies, products, people)
      5. Event extraction (earnings, M&A, regulation)
      6. Knowledge graph building (relationships, supply chains)
      7. Relation computation (strength, transitive)
      8. Semantic embedding & search
      9. Alpha signal generation
    """

    def __init__(self, config: Optional[KnowledgeConfig] = None):
        self.config = config or KnowledgeConfig()

        # Initialize all components
        self.ingestion = IngestionPipeline(self.config.ingestion)
        self.news_engine = NewsEngine(self.config.news)
        self.nlp = NLPProcessor(self.config.nlp)
        self.sentiment = SentimentEngine(self.config.sentiment)
        self.entity_extractor = EntityExtractor(self.config.extraction)
        self.event_engine = EventEngine(self.config.event)
        self.graph = KnowledgeGraph()
        self.relation_engine = RelationEngine(self.config.relation, self.graph)
        self.embedding_engine = EmbeddingEngine(self.config.embedding)
        self.alpha_engine = EventAlphaEngine(self.config.alpha, self.graph)

        self._analysis_results: List[AnalysisResult] = []

    # ── Full Pipeline: Analyze Document ──────────────────────────────────────

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """
        Run the full knowledge pipeline on a single document.

        Text → NLP → Sentiment → Entities → Events → (optional) Signals.
        """
        start = time.time()
        text = request.text
        doc_id = request.request_id

        result = AnalysisResult(request_id=request.request_id)

        # Step 1: NLP Processing
        nlp_result = self.nlp.process(
            document_id=doc_id,
            text=text,
            tasks=request.tasks or [NLPTask.TOPIC_IDENTIFICATION, NLPTask.KEYWORD_EXTRACTION, NLPTask.SUMMARIZATION, NLPTask.CLASSIFICATION],
            language=request.language,
        )
        result.nlp_result = nlp_result
        result.topics = [t.value for t in nlp_result.topics]
        result.summary = nlp_result.summary

        # Step 2: Sentiment Analysis
        if self.config.enable_sentiment and request.compute_sentiment:
            sentiment_result = self.sentiment.analyze(
                document_id=doc_id,
                text=text,
                symbol=request.symbols[0] if request.symbols else "",
                source=request.source,
            )
            result.sentiment = sentiment_result
            result.sentiment_direction = sentiment_result.direction.value

        # Step 3: News Article Processing
        if self.config.enable_news_engine:
            news_article = self.news_engine.process(
                document_id=doc_id,
                title=request.title or text[:80],
                content=text,
                source=request.source,
                url=request.url,
                symbols=request.symbols,
            )
            result.news_article = news_article

        # Step 4: Entity Extraction
        if self.config.enable_entities and request.extract_entities:
            entities = self.entity_extractor.extract(
                document_id=doc_id,
                text=text,
                symbols_hint=request.symbols,
            )
            result.entities = entities
            result.entity_names = [e.name for e in entities]

            # Populate knowledge graph with extracted entities
            if self.config.enable_graph:
                self._populate_graph(entities, doc_id)

        # Step 5: Event Extraction
        if self.config.enable_events and request.extract_events:
            event_result = self.event_engine.extract(
                document_id=doc_id,
                text=text,
                primary_entity=request.symbols[0] if request.symbols else "",
                affected_symbols=request.symbols,
                source=request.source,
            )
            result.events = event_result.events
            result.primary_event = event_result.primary_event

            # Generate alpha signals from events
            if self.config.enable_signals and request.generate_signals:
                signals = self.alpha_engine.generate_signals(event_result.events)
                result.signals = signals

        # Step 6: Create embedding (if keywords available)
        if self.config.enable_embedding and nlp_result.keywords:
            self.embedding_engine.embed(
                document_id=doc_id,
                keywords=nlp_result.keywords,
                keyword_scores=nlp_result.keyword_scores,
                title=request.title,
                summary=nlp_result.summary,
                symbols=request.symbols,
            )

        result.processing_time_ms = (time.time() - start) * 1000
        self._analysis_results.append(result)

        logger.info(
            f"Analyzed doc={doc_id}: {len(result.entities)} entities, "
            f"{len(result.events)} events, {len(result.signals)} signals "
            f"in {result.processing_time_ms:.1f}ms"
        )
        return result

    def analyze_batch(
        self, requests: List[AnalysisRequest]
    ) -> List[AnalysisResult]:
        """Run analysis on multiple documents."""
        return [self.analyze(req) for req in requests]

    # ── Ingest + Analyze Pipeline ────────────────────────────────────────────

    def run_pipeline(
        self, documents: List[RawDocument], generate_signals: bool = False
    ) -> PipelineResult:
        """
        Run full pipeline: ingest → process → analyze → signals.

        Args:
            documents: Raw documents to process.
            generate_signals: Whether to generate alpha signals.

        Returns:
            PipelineResult with summary statistics.
        """
        pipeline_id = str(uuid.uuid4())
        start = time.time()

        result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.INGESTING,
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Ingest
            accepted = self.ingestion.ingest(documents)
            result.documents_ingested = len(accepted)

            if not accepted:
                result.status = PipelineStatus.COMPLETED
                result.completed_at = datetime.now(timezone.utc)
                return result

            # Process each document
            result.status = PipelineStatus.PROCESSING
            for doc in accepted:
                try:
                    analysis = self.analyze(AnalysisRequest(
                        request_id=doc.document_id,
                        text=doc.content,
                        title=doc.title,
                        source=doc.source.value,
                        url=doc.url,
                        symbols=doc.symbols,
                        language=doc.language,
                        generate_signals=generate_signals,
                    ))

                    result.docs_processed += 1
                    result.entities_extracted += len(analysis.entities)
                    result.events_extracted += len(analysis.events)
                    result.signals_generated += len(analysis.signals)

                except Exception as e:
                    logger.error(f"Error processing document {doc.document_id}: {e}")
                    result.errors.append(str(e))

            result.status = PipelineStatus.COMPLETED

        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} failed: {e}")
            result.status = PipelineStatus.FAILED
            result.errors.append(str(e))

        finally:
            result.completed_at = datetime.now(timezone.utc)
            result.duration_ms = (time.time() - start) * 1000

        logger.info(
            f"Pipeline {pipeline_id} completed: {result.docs_processed} docs, "
            f"{result.entities_extracted} entities, {result.events_extracted} events, "
            f"{result.signals_generated} signals in {result.duration_ms:.0f}ms"
        )
        return result

    # ── Graph Operations ─────────────────────────────────────────────────────

    def _populate_graph(
        self, entities: List[ExtractedEntity], document_id: str
    ) -> None:
        """Populate knowledge graph from extracted entities."""
        for entity in entities:
            node_type = NodeType.COMPANY
            if entity.entity_type == EntityType.PRODUCT:
                node_type = NodeType.PRODUCT
            elif entity.entity_type == EntityType.INDUSTRY:
                node_type = NodeType.INDUSTRY
            elif entity.entity_type == EntityType.PERSON:
                node_type = NodeType.PERSON

            node = self.graph.add_node(
                name=entity.name,
                node_type=node_type,
                ticker=entity.ticker,
                sector=entity.sector,
                industry=entity.industry,
            )

            # Add edges for related entities
            for related in entity.related_entities:
                related_node = self.graph.find_node(related)
                if related_node:
                    self.graph.add_edge(
                        node.node_id, related_node.node_id,
                        EdgeType.RELATED_TO,
                        weight=entity.relevance_score,
                        confidence=entity.confidence,
                    )

    def build_supply_chain(
        self, company_name: str,
        suppliers: List[Tuple[str, float]],
        customers: List[Tuple[str, float]],
    ) -> None:
        """Manually build supply chain relationships in the graph."""
        company = self.graph.find_node(company_name)
        if not company:
            company = self.graph.add_node(company_name, NodeType.COMPANY)

        # Add suppliers
        for supplier_name, weight in suppliers:
            supplier = self.graph.find_node(supplier_name) or self.graph.add_node(
                supplier_name, NodeType.COMPANY
            )
            self.graph.add_edge(
                supplier.node_id, company.node_id,
                EdgeType.SUPPLIER_OF, weight=weight, confidence=0.8,
            )

        # Add customers
        for customer_name, weight in customers:
            customer = self.graph.find_node(customer_name) or self.graph.add_node(
                customer_name, NodeType.COMPANY
            )
            self.graph.add_edge(
                company.node_id, customer.node_id,
                EdgeType.CUSTOMER_OF, weight=weight, confidence=0.8,
            )

    # ── Query Methods ────────────────────────────────────────────────────────

    def search_knowledge(
        self, query_text: str, top_k: int = 10
    ) -> List[SimilarityResult]:
        """Semantic search over knowledge base."""
        return self.embedding_engine.search_by_text(query_text, top_k=top_k)

    def get_entity_graph(self, entity_name: str, depth: int = 2) -> Dict[str, Any]:
        """Get entity relationship subgraph."""
        node = self.graph.find_node(entity_name)
        if not node:
            return {"entity": entity_name, "error": "Not found"}

        bfs = self.graph.bfs(node.node_id, max_depth=depth)
        relations = self.relation_engine.compute_all_for_entity(entity_name)

        return {
            "entity": entity_name,
            "node_type": node.node_type.value,
            "ticker": node.ticker,
            "neighbors_by_depth": {
                str(d): [
                    {"name": self.graph.get_node(nid).name if self.graph.get_node(nid) else nid}
                    for nid in nids
                ]
                for d, nids in bfs.items()
            },
            "relations": [r.to_dict() for r in relations],
            "graph_stats": self.graph.get_stats(),
        }

    def get_event_alpha(self, min_confidence: float = 0.3) -> List[Dict[str, Any]]:
        """Get event-driven alpha signals."""
        aggregated = self.alpha_engine.aggregate_all()
        return [
            s.to_dict() for s in aggregated
            if s.confidence >= min_confidence
        ]

    def get_sentiment_summary(
        self, symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get sentiment summary for symbols."""
        summary = {}
        for symbol in symbols:
            sentiment = self.sentiment.get_symbol_sentiment(symbol)
            momentum = self.sentiment.compute_momentum(symbol)
            acceleration = self.sentiment.compute_acceleration(symbol)

            summary[symbol] = {
                "sentiment": sentiment.to_dict(),
                "momentum": momentum.to_dict(),
                "acceleration": acceleration.to_dict(),
            }
        return summary

    def clear(self) -> None:
        """Clear all data across all components."""
        self.ingestion.clear()
        self.news_engine.clear()
        self.nlp.clear()
        self.sentiment.clear()
        self.entity_extractor.clear()
        self.event_engine.clear()
        self.graph.clear()
        self.relation_engine.clear()
        self.embedding_engine.clear()
        self.alpha_engine.clear()
        self._analysis_results.clear()
