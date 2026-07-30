"""
ICYQuant Knowledge Intelligence Layer.

Alternative Data & Knowledge Graph Platform:
- News Intelligence
- Financial NLP
- Sentiment Analysis
- Entity & Event Extraction
- Knowledge Graph
- Relation Mapping
- Event-driven Alpha Signals
"""

from services.knowledge.ingestion import (
    DataSource, RawDocument, DocumentType, IngestionConfig, IngestionPipeline,
)
from services.knowledge.news_engine import (
    NewsEngine, NewsArticle, NewsConfig, NewsCategory, NewsSentiment,
)
from services.knowledge.nlp_processor import (
    NLPProcessor, NLPResult, NLPTask, NLPTopic, NLPConfig,
)
from services.knowledge.sentiment import (
    SentimentEngine, SentimentResult, SentimentDirection, SentimentConfig,
    SentimentMomentum, SentimentAcceleration, SentimentTrend,
)
from services.knowledge.entity_extraction import (
    EntityExtractor, ExtractedEntity, EntityType, EntityMention, ExtractionConfig,
)
from services.knowledge.event_engine import (
    EventEngine, MarketEvent, EventType, EventImpact, EventConfig, EventExtractionResult,
)
from services.knowledge.knowledge_graph import (
    KnowledgeGraph, GraphNode, GraphEdge, EdgeType, NodeType, GraphQuery,
)
from services.knowledge.relation_engine import (
    RelationEngine, EntityRelation, RelationType, RelationStrength, RelationConfig,
)
from services.knowledge.embedding import (
    EmbeddingEngine, DocumentEmbedding, EmbeddingConfig, EmbeddingModel,
    SimilarityResult, SearchQuery,
)
from services.knowledge.alpha_signal import (
    EventAlphaEngine, AlphaSignal, SignalType, SignalConfidence, AlphaConfig,
    SignalPipeline, EventToSignalMapping,
)
from services.knowledge.service import (
    KnowledgeService, KnowledgeConfig, AnalysisRequest, AnalysisResult,
    PipelineResult, PipelineStatus,
)

__all__ = [
    # Ingestion
    "DataSource", "RawDocument", "DocumentType", "IngestionConfig", "IngestionPipeline",
    # News Engine
    "NewsEngine", "NewsArticle", "NewsConfig", "NewsCategory", "NewsSentiment",
    # NLP Processor
    "NLPProcessor", "NLPResult", "NLPTask", "NLPTopic", "NLPConfig",
    # Sentiment
    "SentimentEngine", "SentimentResult", "SentimentDirection", "SentimentConfig",
    "SentimentMomentum", "SentimentAcceleration", "SentimentTrend",
    # Entity Extraction
    "EntityExtractor", "ExtractedEntity", "EntityType", "EntityMention", "ExtractionConfig",
    # Event Engine
    "EventEngine", "MarketEvent", "EventType", "EventImpact", "EventConfig", "EventExtractionResult",
    # Knowledge Graph
    "KnowledgeGraph", "GraphNode", "GraphEdge", "EdgeType", "NodeType", "GraphQuery",
    # Relation Engine
    "RelationEngine", "EntityRelation", "RelationType", "RelationStrength", "RelationConfig",
    # Embedding
    "EmbeddingEngine", "DocumentEmbedding", "EmbeddingConfig", "EmbeddingModel",
    "SimilarityResult", "SearchQuery",
    # Alpha Signal
    "EventAlphaEngine", "AlphaSignal", "SignalType", "SignalConfidence", "AlphaConfig",
    "SignalPipeline", "EventToSignalMapping",
    # Service
    "KnowledgeService", "KnowledgeConfig", "AnalysisRequest", "AnalysisResult",
    "PipelineResult", "PipelineStatus",
]
