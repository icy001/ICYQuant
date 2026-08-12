"""
IncidentDetectionEngine — the event -> detection pipeline.

Pipeline (spec section 3):

    raw event -> normalize (DetectionContext) -> deduplicate (event_id) ->
    evaluate rules (highest priority first) -> DetectionResult

Two independent suppression mechanisms (spec section 43):

1. event_id deduplication — the same event delivered twice produces at most
   one detection within the deduplication window.
2. rule cooldown — a rule that already fired will not fire again until its
   cooldown window has elapsed.

A DetectionResult is NOT an incident yet: it only says "this event is
anomalous". Correlation decides what it means.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .detection_context import DetectionContext
from .detection_registry import DetectionRegistry
from .detection_result import DetectionResult
from .detection_rule import DetectionRule


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentDetectionEngine:
    """Evaluate raw events against a DetectionRegistry."""

    def __init__(
        self,
        registry: Optional[DetectionRegistry] = None,
        dedupe_window_seconds: float = 300.0,
    ) -> None:
        self.registry = registry or DetectionRegistry()
        self.dedupe_window_seconds = dedupe_window_seconds
        self._seen_event_ids: Dict[str, datetime] = {}
        self._last_fired: Dict[str, datetime] = {}

    # -- pipeline --------------------------------------------------------

    def evaluate(self, event: Dict[str, Any]) -> DetectionResult:
        """Normalize, deduplicate and evaluate a raw system event."""
        context = DetectionContext.from_event(event)

        if self._is_duplicate(context):
            return DetectionResult(
                matched=False,
                event_id=context.event_id,
                event_type=context.event_type,
                suppressed=True,
                suppression_reason="duplicate event_id",
                occurred_at=context.occurred_at,
            )

        self._mark_seen(context)

        for rule in self.registry.list_for_event_type(context.event_type):
            if not rule.matches(event):
                continue

            if self._in_cooldown(rule):
                return DetectionResult(
                    matched=False,
                    rule_id=rule.rule_id,
                    event_id=context.event_id,
                    event_type=context.event_type,
                    incident_type=rule.incident_type,
                    severity=rule.severity,
                    scope=rule.scope,
                    source=rule.source,
                    service=context.service,
                    account=context.account,
                    strategy=context.strategy,
                    instrument=context.instrument,
                    venue=context.venue,
                    detail=context.detail,
                    occurred_at=context.occurred_at,
                    suppressed=True,
                    suppression_reason="rule cooldown active",
                )

            self._mark_fired(rule)

            return DetectionResult(
                matched=True,
                rule_id=rule.rule_id,
                event_id=context.event_id,
                event_type=context.event_type,
                incident_type=rule.incident_type,
                severity=rule.severity,
                scope=rule.scope,
                source=rule.source,
                service=context.service,
                account=context.account,
                strategy=context.strategy,
                instrument=context.instrument,
                venue=context.venue,
                detail=context.detail,
                occurred_at=context.occurred_at,
            )

        return DetectionResult.unmatched(context.event_type)

    # -- suppression helpers ---------------------------------------------

    def _is_duplicate(self, context: DetectionContext) -> bool:
        if not context.event_id:
            return False
        previous = self._seen_event_ids.get(context.event_id)
        if previous is None:
            return False
        elapsed = (context.occurred_at - previous).total_seconds()
        return 0 <= elapsed < self.dedupe_window_seconds

    def _mark_seen(self, context: DetectionContext) -> None:
        if context.event_id:
            self._seen_event_ids[context.event_id] = context.occurred_at

    def _in_cooldown(self, rule: DetectionRule) -> bool:
        if not rule.cooldown_seconds:
            return False
        last = self._last_fired.get(rule.rule_id)
        if last is None:
            return False
        elapsed = (_utcnow() - last).total_seconds()
        return elapsed < rule.cooldown_seconds

    def _mark_fired(self, rule: DetectionRule) -> None:
        self._last_fired[rule.rule_id] = _utcnow()

    # -- lifecycle --------------------------------------------------------

    def clear(self) -> None:
        """Forget all deduplication and cooldown state (tests / restart)."""
        self._seen_event_ids.clear()
        self._last_fired.clear()
