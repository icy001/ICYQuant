"""Hypothesis Manager — Lifecycle management for research hypotheses.

Manages the full lifecycle of hypotheses from generation through
validation, experimentation, to completion or rejection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HypothesisStatus(str, Enum):
    """Hypothesis lifecycle states."""

    DRAFT = "draft"
    VALIDATING = "validating"
    VALID = "valid"
    REJECTED = "rejected"
    PLANNING = "planning"
    EXPERIMENTING = "experimenting"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class HypothesisManager:
    """Hypothesis Manager — manages hypothesis lifecycle.

    Tracks all hypotheses:
        - Status transitions
        - Validation results
        - Experiment references
        - Historical performance

    Integrates with discovery memory to avoid repeating rejected hypotheses.
    """

    def __init__(self) -> None:
        self._hypotheses: Dict[str, Dict[str, Any]] = {}
        self._status_history: Dict[str, List[Dict[str, Any]]] = {}

    def register(self, hypothesis: Dict[str, Any]) -> str:
        """Register a new hypothesis."""
        hyp_id = hypothesis.get("hypothesis_id", "")
        if not hyp_id:
            raise ValueError("Hypothesis must have hypothesis_id")

        hypothesis.setdefault("status", HypothesisStatus.DRAFT.value)
        hypothesis.setdefault("registered_at", datetime.now(timezone.utc).isoformat())

        self._hypotheses[hyp_id] = hypothesis
        self._status_history[hyp_id] = [{
            "status": hypothesis["status"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

        logger.debug("Hypothesis registered: %s", hyp_id)
        return hyp_id

    def transition_status(
        self,
        hyp_id: str,
        new_status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Transition a hypothesis to a new status."""
        hyp = self._hypotheses.get(hyp_id)
        if not hyp:
            logger.warning("Hypothesis not found: %s", hyp_id)
            return None

        old_status = hyp.get("status", "")
        if not self._valid_transition(old_status, new_status):
            logger.warning(
                "Invalid transition: %s → %s for %s",
                old_status, new_status, hyp_id,
            )
            return None

        hyp["status"] = new_status
        hyp["updated_at"] = datetime.now(timezone.utc).isoformat()
        if metadata:
            hyp.setdefault("metadata", {}).update(metadata)

        self._status_history[hyp_id].append({
            "status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
        })

        logger.info("Hypothesis %s: %s → %s", hyp_id, old_status, new_status)
        return hyp

    def get(self, hyp_id: str) -> Optional[Dict[str, Any]]:
        """Get a hypothesis by ID."""
        return self._hypotheses.get(hyp_id)

    def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all hypotheses in a given status."""
        return [h for h in self._hypotheses.values() if h.get("status") == status]

    def get_history(self, hyp_id: str) -> List[Dict[str, Any]]:
        """Get status transition history."""
        return self._status_history.get(hyp_id, [])

    def list_all(self) -> Dict[str, Any]:
        """List all hypotheses with summaries."""
        by_status: Dict[str, int] = {}
        for h in self._hypotheses.values():
            s = h.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "total": len(self._hypotheses),
            "by_status": by_status,
            "status": HypothesisStatus,
        }

    @staticmethod
    def _valid_transition(old: str, new: str) -> bool:
        """Check if a status transition is valid."""
        valid_transitions = {
            HypothesisStatus.DRAFT.value: [
                HypothesisStatus.VALIDATING.value,
            ],
            HypothesisStatus.VALIDATING.value: [
                HypothesisStatus.VALID.value,
                HypothesisStatus.REJECTED.value,
            ],
            HypothesisStatus.VALID.value: [
                HypothesisStatus.PLANNING.value,
                HypothesisStatus.REJECTED.value,
            ],
            HypothesisStatus.PLANNING.value: [
                HypothesisStatus.EXPERIMENTING.value,
            ],
            HypothesisStatus.EXPERIMENTING.value: [
                HypothesisStatus.COMPLETED.value,
                HypothesisStatus.REJECTED.value,
            ],
            HypothesisStatus.COMPLETED.value: [
                HypothesisStatus.ARCHIVED.value,
            ],
            HypothesisStatus.REJECTED.value: [
                HypothesisStatus.ARCHIVED.value,
            ],
        }
        return new in valid_transitions.get(old, [])
