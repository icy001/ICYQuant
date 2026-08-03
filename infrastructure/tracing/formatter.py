"""
Trace formatter.

Formats spans and traces for display
and export, supporting JSON and text
output formats.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .models import SpanModel, TraceModel


class TraceFormatter:
    """
    Trace and span formatter.

    Converts trace data to various output
    formats for display, logging, and export.

    Formats:
    - JSON: Structured JSON for machine consumption
    - Text: Human-readable for console output
    """

    @staticmethod
    def format_span_json(
        span: SpanModel,
    ) -> str:
        """Format a span as JSON string."""

        return json.dumps(span.to_dict(), default=str)

    @staticmethod
    def format_span_text(
        span: SpanModel,
    ) -> str:
        """Format a span as human-readable text."""

        duration = f"{span.duration_ms:.2f}ms" if not span.is_active else "active"
        parent = f" parent={span.parent_span_id[:8]}" if span.parent_span_id else ""
        return (
            f"[{span.kind.value}] {span.operation} "
            f"trace={span.trace_id[:8]} span={span.span_id[:8]}{parent} "
            f"duration={duration} status={span.status.value}"
        )

    @staticmethod
    def format_trace_json(
        trace: TraceModel,
        spans: List[SpanModel] = None,
    ) -> str:
        """
        Format a trace as JSON string.

        Args:
            trace: Trace to format.
            spans: Optional list of span models.

        Returns:
            JSON string.
        """

        data = trace.to_dict()
        if spans:
            data["span_details"] = [s.to_dict() for s in spans]
        return json.dumps(data, default=str, indent=2)

    @staticmethod
    def format_trace_text(
        trace: TraceModel,
        spans: List[SpanModel] = None,
    ) -> str:
        """Format a trace as human-readable text."""

        duration = f"{trace.duration_ms:.2f}ms"
        lines = [
            f"Trace {trace.trace_id[:8]} "
            f"({trace.span_count} spans, {duration}, sampled={trace.sampled})",
        ]

        if spans:
            for span in spans:
                indent = "  "
                if span.parent_span_id:
                    indent = "    "
                lines.append(f"{indent}{span.operation} [{span.kind.value}] {span.duration_ms:.2f}ms")

        return "\n".join(lines)

    @staticmethod
    def format_span(
        span: SpanModel,
        format_type: str = "json",
    ) -> str:
        """
        Format a span.

        Args:
            span: Span to format.
            format_type: "json" or "text".

        Returns:
            Formatted string.
        """

        if format_type == "text":
            return TraceFormatter.format_span_text(span)
        return TraceFormatter.format_span_json(span)

    @staticmethod
    def format_trace(
        trace: TraceModel,
        spans: List[SpanModel] = None,
        format_type: str = "json",
    ) -> str:
        """
        Format a trace.

        Args:
            trace: Trace to format.
            spans: Optional list of span models.
            format_type: "json" or "text".

        Returns:
            Formatted string.
        """

        if format_type == "text":
            return TraceFormatter.format_trace_text(trace, spans)
        return TraceFormatter.format_trace_json(trace, spans)
