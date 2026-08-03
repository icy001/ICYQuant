"""
Context enrichment filter.

Automatically enriches log records with
environment, hostname, service, and version
information from the current context,
ensuring consistent metadata across all
log entries.
"""

from __future__ import annotations

import socket
from typing import Any, Dict, Optional

from ..models import LogEntry
from .manager import ContextManager


class ContextFilter:
    """
    Log context enrichment filter.

    Enriches log records with contextual
    metadata before they are dispatched
    to handlers:

    - trace_id, span_id (from context)
    - request_id, correlation_id (from context)
    - user_id, strategy_id, order_id (from context)
    - environment, hostname (static/default)
    - service, module, version (configurable)

    Usage:
        enricher = ContextFilter(
            service="oms",
            version="0.4.0",
        )

        # Enrich a log entry
        enriched = enricher.enrich(log_entry)
    """

    def __init__(
        self,
        service: str = "icyquant",
        module: str = "",
        version: str = "0.4.0-alpha2",
        environment: str = "production",
        hostname: Optional[str] = None,
    ) -> None:
        """
        Initialize context filter.

        Args:
            service: Service name.
            module: Module name.
            version: Service version.
            environment: Deployment environment.
            hostname: Machine hostname.
        """

        self._service = service
        self._module = module
        self._version = version
        self._environment = environment
        self._hostname = hostname or socket.gethostname()

    def enrich(
        self,
        record: LogEntry,
    ) -> LogEntry:
        """
        Enrich a log record with context.

        Injects context fields into the record's
        fields dictionary, overriding any
        existing values.

        Args:
            record: LogEntry to enrich.

        Returns:
            Enriched LogEntry (same instance).
        """

        ctx = ContextManager.get()

        # Inject trace context
        if ctx.trace_id and not record.trace_id:
            record.trace_id = ctx.trace_id
        if ctx.span_id and not record.span_id:
            record.span_id = ctx.span_id

        # Inject business context
        if ctx.request_id:
            record.fields["request_id"] = ctx.request_id
        if ctx.correlation_id:
            record.fields["correlation_id"] = ctx.correlation_id
        if ctx.session_id:
            record.fields["session_id"] = ctx.session_id
        if ctx.user_id:
            record.fields["user_id"] = ctx.user_id
        if ctx.strategy_id:
            record.fields["strategy_id"] = ctx.strategy_id
        if ctx.order_id:
            record.fields["order_id"] = ctx.order_id
        if ctx.position_id:
            record.fields["position_id"] = ctx.position_id
        if ctx.account_id:
            record.fields["account_id"] = ctx.account_id

        # Inject static metadata
        record.fields.setdefault("service", self._service)
        record.fields.setdefault("environment", self._environment)
        record.fields.setdefault("hostname", self._hostname)
        record.fields.setdefault("version", self._version)
        if self._module:
            record.fields.setdefault("module", self._module)

        # Inject extra context metadata
        for key, value in ctx.metadata.items():
            record.fields.setdefault(key, value)

        return record

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Filter interface (always allows).

        This filter enriches rather than filters.
        Provided for compatibility with the
        LogFilter interface.

        Args:
            record: LogEntry to check.

        Returns:
            Always True.
        """

        self.enrich(record)
        return True

    def get_stats(
        self,
    ) -> dict:
        """Get filter statistics."""

        return {
            "service": self._service,
            "module": self._module,
            "version": self._version,
            "environment": self._environment,
            "hostname": self._hostname,
        }
