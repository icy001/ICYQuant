"""
Decision Engine — Centralized autonomous decision processing.

All autonomous decisions flow through the Decision Engine, which
records, validates, and finalizes every decision made by the system.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DecisionStatus(Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    ALLOWED = "allowed"
    DENIED = "denied"
    DEFERRED = "deferred"
    RESIZED = "resized"
    REVIEW_REQUIRED = "review_required"
    QUARANTINED = "quarantined"
    ROLLED_BACK = "rolled_back"
    HALTED = "halted"


@dataclass
class DecisionRecord:
    """Immutable record of a single autonomous decision."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    entity_type: str = ""
    entity_id: str = ""
    action: str = ""
    requested_scope: str = ""
    final_status: str = DecisionStatus.PENDING.value
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    autonomy_level: Optional[int] = None
    approval_id: Optional[str] = None
    trace_id: str = ""
    context_snapshot: Optional[dict] = None
    reason: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "requested_scope": self.requested_scope,
            "final_status": self.final_status,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "autonomy_level": self.autonomy_level,
            "approval_id": self.approval_id,
            "trace_id": self.trace_id,
            "reason": self.reason,
            "duration_ms": self.duration_ms,
        }


class DecisionEngine:
    """
    Central decision processing engine.

    Records every autonomous decision with full context, enabling
    complete audit trails and lineage tracking.
    """

    def __init__(self, registry=None):
        from .decision_registry import DecisionRegistry
        self._registry = registry or DecisionRegistry()
        self._decision_count = 0
        self._allow_count = 0
        self._deny_count = 0
        self._lineage: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        logger.info("DecisionEngine started")

    async def stop(self):
        logger.info("DecisionEngine stopped — %d decisions processed", self._decision_count)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    async def decide(self, context) -> DecisionStatus:
        """
        Finalize a decision through the engine.

        Records the decision with full lineage and returns the status.
        """
        start = time.time()
        self._decision_count += 1

        record = DecisionRecord(
            entity_type=getattr(context, "entity_type", "unknown"),
            entity_id=getattr(context, "entity_id", ""),
            action=getattr(context, "action", "evaluate"),
            trace_id=getattr(context, "trace_id", ""),
        )

        # Determine final status
        status = await self._evaluate(context, record)
        record.final_status = status.value
        record.duration_ms = (time.time() - start) * 1000

        # Record in registry
        self._registry.add(record)

        # Track lineage
        parent_id = getattr(context, "parent_decision_id", None)
        if parent_id:
            self._lineage.setdefault(parent_id, []).append(record.decision_id)

        if status == DecisionStatus.ALLOWED:
            self._allow_count += 1
        else:
            self._deny_count += 1

        return status

    async def _evaluate(self, context, record: DecisionRecord) -> DecisionStatus:
        """Internal evaluation logic."""
        requested_action = getattr(context, "action", "evaluate")
        requested_scope = getattr(context, "requested_scope", "default")

        if requested_scope == "production" and requested_action == "autonomous_execution":
            return DecisionStatus.REVIEW_REQUIRED

        if requested_scope == "capital" and requested_action == "allocate_capital":
            return DecisionStatus.REVIEW_REQUIRED

        # Default — allow (policy/permission checks happen upstream)
        return DecisionStatus.ALLOWED

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    async def get_lineage(self, decision_id: str) -> dict:
        """Get the full lineage for a decision."""
        record = self._registry.get(decision_id)
        if not record:
            return {"error": "not_found"}

        children = self._lineage.get(decision_id, [])
        parent = None
        for pid, cids in self._lineage.items():
            if decision_id in cids:
                parent = self._registry.get(pid)
                break

        return {
            "decision": record.to_dict() if record else None,
            "parent": parent.to_dict() if parent else None,
            "children": [
                self._registry.get(c).to_dict()
                for c in children
                if self._registry.get(c)
            ],
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        return self._registry.get(decision_id)

    def query_decisions(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[DecisionRecord]:
        return self._registry.query(
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "decisions_total": self._decision_count,
            "allow_count": self._allow_count,
            "deny_count": self._deny_count,
            "allow_rate": self._allow_count / max(self._decision_count, 1),
            "lineage_trees": len(self._lineage),
        }
