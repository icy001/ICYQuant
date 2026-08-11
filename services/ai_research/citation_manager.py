"""
ICYQuant Citation Manager — academic-grade citation tracking for research.

Manages citations across research reports with support for multiple
citation styles, source provenance tracking, and bibliography generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CitationStyle(str, Enum):
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    HARVARD = "harvard"
    IEEE = "ieee"


class SourceType(str, Enum):
    RESEARCH_PAPER = "research_paper"
    MARKET_REPORT = "market_report"
    COMPANY_FILING = "company_filing"
    NEWS_ARTICLE = "news_article"
    BOOK = "book"
    WEBSITE = "website"
    DATASET = "dataset"
    INTERNAL = "internal"


@dataclass
class Citation:
    """A single citation entry."""
    citation_id: str
    source_type: SourceType
    title: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    publisher: str = ""
    url: str = ""
    doi: str = ""
    accessed_at: Optional[datetime] = None
    page_numbers: str = ""
    abstract: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationContext:
    """A citation used in context within a report."""
    citation: Citation
    context_text: str  # The text being cited
    page_reference: str = ""
    usage_count: int = 1


class CitationManager:
    """Academic-grade citation tracking and bibliography management.

    Responsibilities:
        - Extract citations from documents
        - Track citation usage in reports
        - Generate bibliographies in multiple styles
        - Validate citation completeness
        - Cross-reference and deduplicate
    """

    def __init__(self) -> None:
        self._citations: dict[str, Citation] = {}
        self._usage: list[CitationContext] = []
        self._total_extracted = 0

    async def extract_citations(
        self,
        documents: list[dict[str, Any]],
        evidence: Optional[list[dict[str, Any]]] = None,
    ) -> list[dict[str, Any]]:
        """Extract and register citations from documents and evidence."""
        citations: list[dict[str, Any]] = []

        for doc in documents:
            doc_id = doc.get("doc_id", "")
            title = doc.get("title", "Untitled")
            authors = doc.get("authors", [])
            source_url = doc.get("source_url", "")
            domain = doc.get("domain", "")

            # Determine source type from domain
            source_type = self._infer_source_type(domain)

            # Generate citation ID
            import hashlib
            citation_id = hashlib.sha256(f"{title}{source_url}".encode()).hexdigest()[:16]

            if citation_id not in self._citations:
                citation = Citation(
                    citation_id=citation_id,
                    source_type=source_type,
                    title=title,
                    authors=authors if isinstance(authors, list) else [authors],
                    url=source_url,
                    metadata={"doc_id": doc_id, "domain": domain},
                )
                self._citations[citation_id] = citation
                self._total_extracted += 1

            citations.append({
                "citation_id": citation_id,
                "title": title,
                "authors": authors if isinstance(authors, list) else [authors],
                "source_type": source_type.value,
                "url": source_url,
            })

        return citations

    def add_citation(self, citation: Citation) -> str:
        """Manually add a citation."""
        self._citations[citation.citation_id] = citation
        self._total_extracted += 1
        return citation.citation_id

    def cite(
        self,
        citation_id: str,
        context_text: str,
        page_reference: str = "",
    ) -> Optional[CitationContext]:
        """Record a citation usage in context."""
        citation = self._citations.get(citation_id)
        if citation is None:
            logger.warning("Citation %s not found", citation_id)
            return None

        ctx = CitationContext(
            citation=citation,
            context_text=context_text,
            page_reference=page_reference,
        )
        self._usage.append(ctx)
        return ctx

    def get_citation(self, citation_id: str) -> Optional[Citation]:
        return self._citations.get(citation_id)

    def generate_bibliography(self, style: CitationStyle = CitationStyle.APA) -> str:
        """Generate a formatted bibliography."""
        entries: list[str] = []

        for citation in self._citations.values():
            entry = self._format_citation(citation, style)
            entries.append(entry)

        return "\n\n".join(entries)

    def _format_citation(self, citation: Citation, style: CitationStyle) -> str:
        """Format a single citation in the given style."""
        authors_str = ", ".join(citation.authors) if citation.authors else "Unknown Author"
        year = citation.year if citation.year else "n.d."
        title = citation.title

        if style == CitationStyle.APA:
            return f"{authors_str} ({year}). {title}. {citation.url}"
        elif style == CitationStyle.MLA:
            return f'{authors_str}. "{title}." {citation.publisher}, {year}. {citation.url}'
        elif style == CitationStyle.IEEE:
            idx = list(self._citations.keys()).index(citation.citation_id) + 1
            return f"[{idx}] {authors_str}, \"{title},\" {citation.publisher}, {year}."
        elif style == CitationStyle.HARVARD:
            return f"{authors_str} ({year}) '{title}', {citation.publisher}. Available at: {citation.url}"
        else:
            return f"{authors_str}. {title}. {citation.publisher}, {year}."

    def get_usage_stats(self) -> dict[str, Any]:
        """Get citation usage statistics."""
        return {
            "total_citations": len(self._citations),
            "total_usages": len(self._usage),
            "most_cited": self._most_cited(5),
            "by_source_type": self._count_by_source_type(),
        }

    def _most_cited(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get most-cited sources."""
        counts: dict[str, int] = {}
        for ctx in self._usage:
            cid = ctx.citation.citation_id
            counts[cid] = counts.get(cid, 0) + 1

        sorted_citations = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        result = []
        for cid, count in sorted_citations[:limit]:
            citation = self._citations.get(cid)
            if citation:
                result.append({"title": citation.title, "count": count})
        return result

    def _count_by_source_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for citation in self._citations.values():
            st = citation.source_type.value
            counts[st] = counts.get(st, 0) + 1
        return counts

    @staticmethod
    def _infer_source_type(domain: str) -> SourceType:
        domain_lower = domain.lower()
        if "research_paper" in domain_lower:
            return SourceType.RESEARCH_PAPER
        elif "market_report" in domain_lower:
            return SourceType.MARKET_REPORT
        elif "company_filing" in domain_lower:
            return SourceType.COMPANY_FILING
        elif "news" in domain_lower:
            return SourceType.NEWS_ARTICLE
        elif "dataset" in domain_lower:
            return SourceType.DATASET
        elif "internal" in domain_lower:
            return SourceType.INTERNAL
        return SourceType.WEBSITE

    @property
    def citation_count(self) -> int:
        return len(self._citations)

    @property
    def total_extracted(self) -> int:
        return self._total_extracted
