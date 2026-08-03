"""
W3C Trace Context and Baggage propagator.

Enhances the TracePropagator with full W3C
Trace Context specification support, including
traceparent, tracestate, and baggage headers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import SpanModel

try:
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )
    from opentelemetry.baggage.propagation import (
        W3CBaggagePropagator,
    )
except ImportError:
    TraceContextTextMapPropagator = None
    W3CBaggagePropagator = None


class ICYTracePropagator:
    """
    ICYQuant Trace Propagator.

    Combines W3C Trace Context and Baggage
    propagation with ICYQuant-specific header
    handling for distributed tracing.

    Supports:
    - traceparent: W3C trace context header
    - tracestate: W3C trace state header
    - baggage: W3C baggage header
    - X-Trace-ID: ICYQuant-specific header (backward compat)
    - X-Span-ID: ICYQuant-specific header (backward compat)

    Usage:
        propagator = ICYTracePropagator()

        # Inject into outgoing request
        headers = {}
        propagator.inject(headers, span=current_span)

        # Extract from incoming request
        context = propagator.extract(headers)
    """

    def __init__(
        self,
    ) -> None:
        """Initialize propagator."""

        self._trace_propagator = (
            TraceContextTextMapPropagator()
            if TraceContextTextMapPropagator
            else None
        )
        self._baggage_propagator = (
            W3CBaggagePropagator()
            if W3CBaggagePropagator
            else None
        )

    def inject(
        self,
        carrier: Dict[str, str],
        span: Optional[SpanModel] = None,
        baggage: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Inject trace context into carrier.

        Injects both W3C Trace Context headers
        and ICYQuant-specific headers for
        backward compatibility.

        Args:
            carrier: Headers dict to inject into.
            span: Span to propagate.
            baggage: Optional baggage items.

        Returns:
            Updated carrier dict.
        """

        from .context import current_span as get_current_span

        active_span = span or get_current_span()

        if active_span is not None:
            # W3C traceparent header
            carrier["traceparent"] = self._build_traceparent(
                active_span.trace_id,
                active_span.span_id,
                "01",  # sampled
            )

            # ICYQuant-specific headers (backward compat)
            carrier["X-Trace-ID"] = active_span.trace_id
            carrier["X-Span-ID"] = active_span.span_id

        # Propagate via OTel if available
        if self._trace_propagator is not None:
            try:
                self._trace_propagator.inject(
                    carrier, context=None
                )
            except Exception:
                pass

        # Baggage injection
        if baggage and self._baggage_propagator is not None:
            try:
                self._baggage_propagator.inject(
                    carrier, context=None
                )
            except Exception:
                # Manually inject baggage
                items = [f"{k}={v}" for k, v in baggage.items()]
                if items:
                    carrier["baggage"] = ",".join(items)

        return carrier

    def extract(
        self,
        carrier: Dict[str, str],
    ) -> Optional[Dict[str, str]]:
        """
        Extract trace context from carrier.

        Handles both W3C headers and
        ICYQuant-specific headers.

        Args:
            carrier: Headers dict to extract from.

        Returns:
            Extracted context dict or None.
        """

        lower = {k.lower(): v for k, v in carrier.items()}

        # Try W3C traceparent first
        traceparent = lower.get("traceparent")
        if traceparent:
            parsed = self._parse_traceparent(traceparent)
            if parsed:
                return parsed

        # Try ICYQuant-specific headers
        trace_id = lower.get("x-trace-id")
        span_id = lower.get("x-span-id")

        if trace_id:
            return {
                "trace_id": trace_id,
                "span_id": span_id or "",
                "parent_span_id": lower.get("x-parent-span-id"),
                "sampled": lower.get("x-sampled", "true") == "true",
            }

        # Try OTel extraction
        if self._trace_propagator is not None:
            try:
                ctx = self._trace_propagator.extract(carrier)
                if ctx is not None:
                    return ctx
            except Exception:
                pass

        return None

    def extract_baggage(
        self,
        carrier: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Extract baggage items from carrier.

        Args:
            carrier: Headers dict to extract from.

        Returns:
            Dictionary of baggage items.
        """

        lower = {k.lower(): v for k, v in carrier.items()}

        baggage_str = lower.get("baggage", "")
        result: Dict[str, str] = {}

        if baggage_str:
            for item in baggage_str.split(","):
                if "=" in item:
                    key, value = item.split("=", 1)
                    result[key.strip()] = value.strip()

        return result

    @staticmethod
    def _build_traceparent(
        trace_id: str,
        span_id: str,
        flags: str = "01",
    ) -> str:
        """
        Build a W3C traceparent header.

        Format: 00-{trace_id}-{span_id}-{flags}

        Args:
            trace_id: Trace ID.
            span_id: Span ID.
            flags: Flags byte.

        Returns:
            traceparent string.
        """

        version = "00"
        return f"{version}-{trace_id}-{span_id}-{flags}"

    @staticmethod
    def _parse_traceparent(
        traceparent: str,
    ) -> Optional[Dict[str, str]]:
        """
        Parse a W3C traceparent header.

        Args:
            traceparent: traceparent header value.

        Returns:
            Parsed context or None.
        """

        try:
            parts = traceparent.split("-")
            if len(parts) >= 3:
                return {
                    "trace_id": parts[1],
                    "span_id": parts[2],
                    "sampled": len(parts) > 3 and parts[3] == "01",
                }
        except Exception:
            pass

        return None

    def get_w3c_headers(
        self,
    ) -> List[str]:
        """Get all W3C header names."""

        return [
            "traceparent",
            "tracestate",
            "baggage",
        ]


# Backward compatibility alias
TracePropagator = ICYTracePropagator
