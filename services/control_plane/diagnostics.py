"""Diagnostics: redaction, operational snapshot and command timeline
(Commit 29 Part 1.5 §32-34, §39-41).

Sensitive fields must never leak into audit, metrics, traces or logs. All
payloads entering observability pass through :func:`redact`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from .event import ControlEvent

REDACTED = "[REDACTED]"

SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credential",
        "authorization",
        "bearer",
        "session_id",
        "broker_password",
        "account_password",
    }
)


def redact(payload: Mapping[str, Any], fields: frozenset[str] = SENSITIVE_FIELDS) -> dict[str, Any]:
    """Deep-copy ``payload`` with every sensitive value replaced (§33-34).

    Non-sensitive keys are copied verbatim; sensitive keys become the string
    ``[REDACTED]`` regardless of value type.
    """
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in fields:
            result[key] = REDACTED
        elif isinstance(value, Mapping):
            result[key] = redact(value, fields)
        elif isinstance(value, list):
            result[key] = [
                redact(item, fields) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def redact_value(key: str, value: Any, fields: frozenset[str] = SENSITIVE_FIELDS) -> Any:
    """Redact a single key/value pair, e.g. ``("token", ...) -> "[REDACTED]"``."""
    if key.lower() in fields:
        return REDACTED
    return value


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    """Point-in-time operational snapshot (§39)."""

    active_commands: int = 0
    executing_commands: int = 0
    unknown_commands: int = 0
    recovery_commands: int = 0
    failed_commands: int = 0
    active_claims: int = 0
    expired_claims: int = 0
    duplicate_rate: float = 0.0
    timeout_rate: float = 0.0


@dataclass(frozen=True)
class TimelineEntry:
    """One row of a command timeline (§41)."""

    timestamp: datetime
    event_type: str
    sequence: int
    correlation_id: str
    causation_id: str | None = None
    detail: str | None = None


class ControlPlaneDiagnostics:
    """Builds operational snapshots and per-command timelines (§39-41)."""

    def __init__(
        self,
        *,
        command_states: Sequence[str] | None = None,
        claims: Sequence[Any] | None = None,
        metrics: Any | None = None,
        events_provider: Callable[[str], Sequence[ControlEvent]] | None = None,
    ) -> None:
        self._command_states = list(command_states or [])
        self._claims = list(claims or [])
        self._metrics = metrics
        self._events_provider = events_provider

    def snapshot(self) -> DiagnosticsSnapshot:
        active = 0
        executing = 0
        unknown = 0
        recovery = 0
        failed = 0
        for state in self._command_states:
            if state in ("RECEIVED", "AUTHORIZING", "WAITING_APPROVAL", "AUTHORIZED", "DISPATCHING"):
                active += 1
            elif state == "EXECUTING":
                active += 1
                executing += 1
            elif state == "UNKNOWN":
                active += 1
                unknown += 1
            elif state in ("RECOVERY_REQUIRED", "RECONCILING", "RECONCILIATION"):
                active += 1
                recovery += 1
            elif state in ("FAILED", "FAILED_RECOVERY"):
                # FAILED is not terminal in the state machine (retryable via
                # AUTHORIZED/CANCELLED), so it counts as active but is tracked.
                active += 1
                failed += 1

        active_claims = 0
        expired_claims = 0
        for claim in self._claims:
            if isinstance(claim, dict):
                state = claim.get("state")
                if state in ("ACTIVE", "HELD"):
                    active_claims += 1
                elif state == "EXPIRED":
                    expired_claims += 1
            else:
                # ExecutionClaim has no state attribute; use is_expired().
                if getattr(claim, "is_expired", lambda: False)():
                    expired_claims += 1
                else:
                    active_claims += 1

        duplicate_rate = self._metrics.duplicate_rate() if self._metrics else 0.0
        timeout_rate = self._metrics.timeout_rate() if self._metrics else 0.0

        return DiagnosticsSnapshot(
            active_commands=active,
            executing_commands=executing,
            unknown_commands=unknown,
            recovery_commands=recovery,
            failed_commands=failed,
            active_claims=active_claims,
            expired_claims=expired_claims,
            duplicate_rate=duplicate_rate,
            timeout_rate=timeout_rate,
        )

    def timeline(self, command_id: str) -> tuple[TimelineEntry, ...]:
        """Rebuild the command timeline from its event stream (§41)."""
        if self._events_provider is None:
            return ()
        events = sorted(
            self._events_provider(command_id),
            key=lambda event: event.sequence,
        )
        return tuple(
            TimelineEntry(
                timestamp=event.timestamp,
                event_type=event.event_type,
                sequence=event.sequence,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                detail=None,
            )
            for event in events
        )
