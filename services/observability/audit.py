"""
Audit event pipeline.

Provides immutable audit records.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from datetime import datetime, timezone

from uuid import uuid4

from .correlation import (
    get_correlation,
)


@dataclass(
    frozen=True,
)
class AuditEvent:
    event_id: str
    action: str
    actor: str
    resource: str
    timestamp: str
    correlation_id: str | None
    trace_id: str | None
    metadata: dict = field(
        default_factory=dict
    )


def create_audit_event(
    action: str,
    actor: str,
    resource: str,
    metadata: dict | None = None,
) -> AuditEvent:
    correlation = get_correlation()

    return AuditEvent(
        event_id=(
            f"audit-{uuid4().hex[:12]}"
        ),
        action=action,
        actor=actor,
        resource=resource,
        timestamp=datetime.now(
            timezone.utc
        ).isoformat(),
        correlation_id=(
            correlation.correlation_id
            if correlation
            else None
        ),
        trace_id=(
            correlation.trace_id
            if correlation
            else None
        ),
        metadata=(
            metadata
            or {}
        ),
    )