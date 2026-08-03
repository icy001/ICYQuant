"""
Structured logging context models.

Defines the enhanced LogContext dataclass
with full tracing, correlation, and
business context fields for distributed
log correlation across the ICYQuant platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LogContext:
    """
    Structured logging context.

    Carries request-scoped and distributed
    tracing context across the entire
    request lifecycle:

    Trace → Strategy → Signal → Order → Execution
    → Trade → Position → Ledger

    All fields are optional. Only set fields
    are included in log output.

    Attributes:
        trace_id: Distributed trace identifier.
        span_id: Span identifier within the trace.
        request_id: HTTP request identifier.
        correlation_id: Business correlation identifier.
        session_id: User session identifier.
        user_id: Authenticated user identifier.
        strategy_id: Active strategy identifier.
        order_id: Current order identifier.
        position_id: Current position identifier.
        account_id: Trading account identifier.
        environment: Deployment environment.
        hostname: Machine hostname.
        metadata: Arbitrary extra context fields.
    """

    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    strategy_id: Optional[str] = None
    order_id: Optional[str] = None
    position_id: Optional[str] = None
    account_id: Optional[str] = None
    environment: Optional[str] = None
    hostname: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Backward compat alias
    @property
    def extra(
        self,
    ) -> Dict[str, Any]:
        """Alias for metadata (backward compat)."""
        return self.metadata

    def to_fields(
        self,
    ) -> Dict[str, Any]:
        """
        Convert context to log fields dict.

        Returns only non-None fields, suitable
        for merging into a LogEntry's fields.

        Returns:
            Dictionary of non-None context fields.
        """

        fields: Dict[str, Any] = {}

        if self.trace_id is not None:
            fields["trace_id"] = self.trace_id
        if self.span_id is not None:
            fields["span_id"] = self.span_id
        if self.request_id is not None:
            fields["request_id"] = self.request_id
        if self.correlation_id is not None:
            fields["correlation_id"] = self.correlation_id
        if self.session_id is not None:
            fields["session_id"] = self.session_id
        if self.user_id is not None:
            fields["user_id"] = self.user_id
        if self.strategy_id is not None:
            fields["strategy_id"] = self.strategy_id
        if self.order_id is not None:
            fields["order_id"] = self.order_id
        if self.position_id is not None:
            fields["position_id"] = self.position_id
        if self.account_id is not None:
            fields["account_id"] = self.account_id
        if self.environment is not None:
            fields["environment"] = self.environment
        if self.hostname is not None:
            fields["hostname"] = self.hostname

        fields.update(self.metadata)

        return fields

    def merge(
        self,
        other: "LogContext",
    ) -> "LogContext":
        """
        Merge with another context.

        Non-None values from other override
        values from self. Metadata dicts are
        merged.

        Args:
            other: Context to merge with.

        Returns:
            New merged LogContext.
        """

        merged = LogContext(
            trace_id=other.trace_id or self.trace_id,
            span_id=other.span_id or self.span_id,
            request_id=other.request_id or self.request_id,
            correlation_id=other.correlation_id or self.correlation_id,
            session_id=other.session_id or self.session_id,
            user_id=other.user_id or self.user_id,
            strategy_id=other.strategy_id or self.strategy_id,
            order_id=other.order_id or self.order_id,
            position_id=other.position_id or self.position_id,
            account_id=other.account_id or self.account_id,
            environment=other.environment or self.environment,
            hostname=other.hostname or self.hostname,
        )
        merged.metadata = {**self.metadata, **other.metadata}
        return merged

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "strategy_id": self.strategy_id,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "account_id": self.account_id,
            "environment": self.environment,
            "hostname": self.hostname,
            "metadata": self.metadata,
        }

    def is_empty(
        self,
    ) -> bool:
        """Check if context has no set fields."""

        return all(
            v is None for k, v in self.to_dict().items()
            if k != "metadata"
        ) and not self.metadata
