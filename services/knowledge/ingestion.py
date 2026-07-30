"""
Alternative Data Ingestion Pipeline.

Unified ingestion for: news, announcements, earnings transcripts,
research reports, macro data, and social media (interface reserved).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    """Types of alternative data documents."""

    NEWS_ARTICLE = "news_article"
    PRESS_RELEASE = "press_release"
    EARNINGS_TRANSCRIPT = "earnings_transcript"
    FILING = "filing"
    RESEARCH_REPORT = "research_report"
    MACRO_INDICATOR = "macro_indicator"
    SOCIAL_MEDIA = "social_media"
    REGULATORY = "regulatory"
    CORPORATE_ACTION = "corporate_action"
    ANALYST_NOTE = "analyst_note"
    CUSTOM = "custom"


class DataSource(str, Enum):
    """Alternative data sources."""

    BLOOMBERG = "bloomberg"
    REUTERS = "reuters"
    SEEKING_ALPHA = "seeking_alpha"
    SEC_EDGAR = "sec_edgar"
    EARNINGS_CALL = "earnings_call"
    TWITTER = "twitter"
    REDDIT = "reddit"
    NEWS_API = "news_api"
    RSS_FEED = "rss_feed"
    RESEARCH_PORTAL = "research_portal"
    FRED = "fred"
    CUSTOM_API = "custom_api"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class RawDocument:
    """A raw ingested document before NLP processing."""

    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: DataSource = DataSource.CUSTOM_API
    doc_type: DocumentType = DocumentType.NEWS_ARTICLE

    title: str = ""
    content: str = ""
    summary: str = ""
    url: str = ""
    language: str = "en"

    published_at: Optional[datetime] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    symbols: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    raw_payload: Optional[Dict[str, Any]] = None
    content_hash: str = ""
    status: IngestionStatus = IngestionStatus.PENDING

    def __post_init__(self):
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source": self.source.value,
            "doc_type": self.doc_type.value,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "url": self.url,
            "language": self.language,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "ingested_at": self.ingested_at.isoformat(),
            "symbols": self.symbols,
            "tags": self.tags,
            "metadata": self.metadata,
            "content_hash": self.content_hash,
            "status": self.status.value,
        }


@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline."""

    # Source filtering
    enabled_sources: Set[DataSource] = field(default_factory=lambda: {
        DataSource.BLOOMBERG, DataSource.REUTERS, DataSource.NEWS_API,
    })
    enabled_types: Set[DocumentType] = field(default_factory=lambda: {
        DocumentType.NEWS_ARTICLE, DocumentType.PRESS_RELEASE,
        DocumentType.EARNINGS_TRANSCRIPT, DocumentType.FILING,
    })

    # Content filters
    min_content_length: int = 50
    max_content_length: int = 50000
    allowed_languages: Set[str] = field(default_factory=lambda: {"en", "zh"})

    # Deduplication
    enable_dedup: bool = True
    dedup_window_days: int = 7

    # Batching
    batch_size: int = 100
    max_documents_per_run: int = 1000

    # Retry
    max_retries: int = 3
    retry_delay_seconds: float = 5.0

    # Rate limiting
    requests_per_minute: int = 60


# ── Ingestion Pipeline ───────────────────────────────────────────────────────

class IngestionPipeline:
    """
    Unified ingestion pipeline for alternative data.

    Supports multiple sources with filtering, deduplication, and
    transformation into standardized RawDocument format.
    """

    def __init__(self, config: Optional[IngestionConfig] = None):
        self.config = config or IngestionConfig()
        self._documents: List[RawDocument] = []
        self._seen_hashes: Set[str] = set()
        self._filters: List[Callable[[RawDocument], bool]] = []
        self._transformers: List[Callable[[RawDocument], RawDocument]] = []
        self._status_counts: Dict[IngestionStatus, int] = {
            s: 0 for s in IngestionStatus
        }

    # ── Filter / Transformer Registration ────────────────────────────────────

    def add_filter(self, filter_fn: Callable[[RawDocument], bool]) -> None:
        """Register a document filter."""
        self._filters.append(filter_fn)

    def add_transformer(
        self, transformer: Callable[[RawDocument], RawDocument]
    ) -> None:
        """Register a document transformer."""
        self._transformers.append(transformer)

    # ── Ingestion Methods ────────────────────────────────────────────────────

    def ingest(
        self,
        documents: List[RawDocument],
        source: Optional[DataSource] = None,
    ) -> List[RawDocument]:
        """Ingest a batch of documents through the pipeline."""
        if source and source not in self.config.enabled_sources:
            logger.debug(f"Source {source} is disabled, skipping {len(documents)} docs")
            self._status_counts[IngestionStatus.SKIPPED] += len(documents)
            return []

        accepted: List[RawDocument] = []

        for doc in documents:
            if source:
                doc.source = source

            # Check source enabled
            if doc.source not in self.config.enabled_sources:
                self._status_counts[IngestionStatus.SKIPPED] += 1
                continue

            # Check document type enabled
            if doc.doc_type not in self.config.enabled_types:
                self._status_counts[IngestionStatus.SKIPPED] += 1
                continue

            # Basic content validation
            if not self._validate_content(doc):
                doc.status = IngestionStatus.FAILED
                self._status_counts[IngestionStatus.FAILED] += 1
                continue

            # Dedup
            if self.config.enable_dedup and doc.content_hash in self._seen_hashes:
                self._status_counts[IngestionStatus.SKIPPED] += 1
                continue

            # Apply filters
            if not all(f(doc) for f in self._filters):
                self._status_counts[IngestionStatus.SKIPPED] += 1
                continue

            # Apply transformers
            for transformer in self._transformers:
                doc = transformer(doc)

            doc.status = IngestionStatus.PROCESSED
            doc.ingested_at = datetime.now(timezone.utc)
            self._seen_hashes.add(doc.content_hash)
            self._documents.append(doc)
            self._status_counts[IngestionStatus.PROCESSED] += 1
            accepted.append(doc)

            # Check max documents limit
            if len(accepted) >= self.config.max_documents_per_run:
                logger.warning("Max documents per run reached, stopping ingestion")
                break

        logger.info(
            f"Ingested {len(accepted)}/{len(documents)} documents. "
            f"Status counts: {self._status_counts}"
        )
        return accepted

    def _validate_content(self, doc: RawDocument) -> bool:
        """Validate document content meets minimum requirements."""
        if not doc.content or not doc.title:
            return False

        content_len = len(doc.content)
        if content_len < self.config.min_content_length:
            return False
        if content_len > self.config.max_content_length:
            return False

        if doc.language not in self.config.allowed_languages:
            return False

        return True

    # ── Query Methods ────────────────────────────────────────────────────────

    def get_documents(
        self,
        source: Optional[DataSource] = None,
        doc_type: Optional[DocumentType] = None,
        symbols: Optional[List[str]] = None,
        status: Optional[IngestionStatus] = None,
        limit: int = 100,
    ) -> List[RawDocument]:
        """Query ingested documents with filters."""
        results = self._documents

        if source:
            results = [d for d in results if d.source == source]
        if doc_type:
            results = [d for d in results if d.doc_type == doc_type]
        if symbols:
            sym_set = set(symbols)
            results = [d for d in results if sym_set & set(d.symbols)]
        if status:
            results = [d for d in results if d.status == status]

        return results[-limit:]

    def get_status_counts(self) -> Dict[str, int]:
        """Get ingestion status summary."""
        return {k.value: v for k, v in self._status_counts.items()}

    def clear(self) -> None:
        """Clear all ingested documents."""
        self._documents.clear()
        self._seen_hashes.clear()
        self._status_counts = {s: 0 for s in IngestionStatus}

    @property
    def document_count(self) -> int:
        return len(self._documents)
