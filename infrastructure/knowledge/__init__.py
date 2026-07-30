"""
Knowledge Infrastructure layer.

Background services, storage, and pipelines for the Knowledge Platform.
"""

from infrastructure.knowledge.vector_store import (
    VectorStore, VectorConfig, VectorIndex, StoredVector, VectorDistance,
)
from infrastructure.knowledge.graph_database import (
    GraphDatabase, GraphDBConfig, StoredNode, StoredEdge, GraphQueryResult,
)
from infrastructure.knowledge.crawler import (
    WebCrawler, CrawlerConfig, CrawlJob, CrawlResult, CrawlSource,
)
from infrastructure.knowledge.pipeline import (
    KnowledgePipeline, PipelineConfig, PipelineTask, TaskStatus, TaskResult,
)

__all__ = [
    # Vector Store
    "VectorStore", "VectorConfig", "VectorIndex", "StoredVector", "VectorDistance",
    # Graph Database
    "GraphDatabase", "GraphDBConfig", "StoredNode", "StoredEdge", "GraphQueryResult",
    # Crawler
    "WebCrawler", "CrawlerConfig", "CrawlJob", "CrawlResult", "CrawlSource",
    # Pipeline
    "KnowledgePipeline", "PipelineConfig", "PipelineTask", "TaskStatus", "TaskResult",
]
