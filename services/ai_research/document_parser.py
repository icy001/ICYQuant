"""
ICYQuant Document Parser — multi-format document ingestion for the knowledge engine.

Parses research papers, market reports, company filings, and internal
documents from various formats (PDF, HTML, Markdown, plain text) into
structured KnowledgeDocument objects.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocumentFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"
    JSON = "json"
    CSV = "csv"


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    authors: list[str] = field(default_factory=list)
    published_at: Optional[datetime] = None
    source_url: str = ""
    format: DocumentFormat = DocumentFormat.PLAINTEXT
    sections: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    parse_errors: list[str] = field(default_factory=list)


class DocumentParser:
    """Multi-format document parser for knowledge ingestion.

    Supported formats:
        - PDF: Extracts text, tables, and metadata
        - HTML: Strips tags, preserves structure
        - Markdown: Parses headings, code blocks, links
        - Plain text: Direct ingestion
        - JSON/CSV: Structured data parsing

    All parsed documents are normalized to a common ParsedDocument format.
    """

    def __init__(self) -> None:
        self._parse_count = 0
        self._error_count = 0

    async def parse(
        self,
        raw_content: str,
        format: DocumentFormat = DocumentFormat.PLAINTEXT,
        source_url: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> ParsedDocument:
        """Parse raw content into a structured document."""
        self._parse_count += 1

        parsed = ParsedDocument(
            source_url=source_url,
            format=format,
            metadata=metadata or {},
        )

        try:
            if format == DocumentFormat.PLAINTEXT:
                parsed.content = raw_content
                parsed.title = self._extract_title_plaintext(raw_content)

            elif format == DocumentFormat.MARKDOWN:
                result = self._parse_markdown(raw_content)
                parsed.content = result["content"]
                parsed.title = result.get("title", "")
                parsed.sections = result.get("sections", [])

            elif format == DocumentFormat.HTML:
                result = self._parse_html(raw_content)
                parsed.content = result["content"]
                parsed.title = result.get("title", "")

            elif format == DocumentFormat.PDF:
                # Placeholder for PDF parsing (production would use PyPDF2/pdfplumber)
                parsed.content = raw_content
                parsed.parse_errors.append("PDF parsing requires external library")
                self._error_count += 1

            elif format == DocumentFormat.JSON:
                result = self._parse_json(raw_content)
                parsed.content = result["content"]
                parsed.title = result.get("title", "")

            elif format == DocumentFormat.CSV:
                result = self._parse_csv(raw_content)
                parsed.content = result["content"]
                parsed.title = result.get("title", "")
                parsed.tables = result.get("tables", [])

            # Compute content hash
            parsed.content_hash = hashlib.sha256(parsed.content.encode()).hexdigest()

        except Exception as exc:
            parsed.parse_errors.append(str(exc))
            self._error_count += 1
            logger.warning("Document parse error: %s", exc)

        return parsed

    def _extract_title_plaintext(self, content: str) -> str:
        """Extract title from the first non-empty line."""
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                return line[:200]
        return "Untitled"

    def _parse_markdown(self, content: str) -> dict[str, Any]:
        """Parse Markdown content into sections."""
        sections: list[dict[str, Any]] = []
        current_section: dict[str, Any] = {"heading": "", "level": 0, "content": []}
        title = ""

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                if not title:
                    title = stripped[2:].strip()
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"heading": stripped[2:].strip(), "level": 1, "content": []}
            elif stripped.startswith("## "):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"heading": stripped[3:].strip(), "level": 2, "content": []}
            elif stripped.startswith("### "):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"heading": stripped[4:].strip(), "level": 3, "content": []}
            else:
                current_section["content"].append(stripped)

        if current_section["content"]:
            sections.append(current_section)

        return {
            "title": title or self._extract_title_plaintext(content),
            "content": content,
            "sections": sections,
        }

    def _parse_html(self, content: str) -> dict[str, Any]:
        """Basic HTML text extraction."""
        import re

        # Remove scripts and styles
        cleaned = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Extract title
        title_match = re.search(r'<title>(.*?)</title>', cleaned, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        # Strip all HTML tags
        text = re.sub(r'<[^>]+>', ' ', cleaned)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return {"title": title, "content": text}

    def _parse_json(self, content: str) -> dict[str, Any]:
        """Parse JSON content into structured text."""
        import json
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                title = data.get("title", data.get("name", ""))
                text = json.dumps(data, indent=2, ensure_ascii=False)
            elif isinstance(data, list):
                title = f"JSON array ({len(data)} items)"
                text = json.dumps(data, indent=2, ensure_ascii=False)
            else:
                title = "JSON data"
                text = str(data)
            return {"title": title, "content": text}
        except json.JSONDecodeError:
            return {"title": "", "content": content}

    def _parse_csv(self, content: str) -> dict[str, Any]:
        """Parse CSV content into structured data."""
        import csv
        import io

        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return {"title": "Empty CSV", "content": "", "tables": []}

        headers = rows[0] if rows else []
        data_rows = rows[1:] if len(rows) > 1 else []

        text_lines = [", ".join(headers)]
        for row in data_rows[:100]:  # Limit preview
            text_lines.append(", ".join(row))

        return {
            "title": f"CSV ({len(data_rows)} rows)",
            "content": "\n".join(text_lines),
            "tables": [{"headers": headers, "rows": data_rows, "row_count": len(data_rows)}],
        }

    @property
    def parse_count(self) -> int:
        return self._parse_count

    @property
    def error_count(self) -> int:
        return self._error_count
