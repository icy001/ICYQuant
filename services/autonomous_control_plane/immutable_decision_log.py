"""
Immutable Decision Log — Append-only decision log with hashing.

Critical decisions are written to an immutable log with content hashing
to prevent tampering and enable full replay/reconstruction.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ImmutableDecisionLog:
    """
    Append-only, hashed decision log for critical decisions.

    Each entry contains:
    - Unique decision ID with hash chain
    - Parent decision reference
    - Model/policy version fingerprints
    - Portfolio/risk snapshots
    - Execution plan reference
    - Approval/result context
    """

    def __init__(self):
        self._entries: list[dict] = []
        self._previous_hash: str = "0" * 64

    def record(
        self,
        decision_id: str,
        model_version: str = "",
        policy_version: str = "",
        risk_snapshot: Optional[dict] = None,
        portfolio_snapshot: Optional[dict] = None,
        execution_plan: Optional[dict] = None,
        approval: Optional[dict] = None,
        result: Any = None,
        parent_decision: Optional[str] = None,
    ) -> dict:
        """
        Record an immutable decision log entry.

        Returns the entry including its computed hash.
        """
        entry_data = {
            "decision_id": decision_id,
            "parent_decision": parent_decision,
            "model_version": model_version,
            "policy_version": policy_version,
            "risk_snapshot": risk_snapshot or {},
            "portfolio_snapshot": portfolio_snapshot or {},
            "execution_plan": execution_plan or {},
            "approval": approval or {},
            "result": str(result) if result else "",
            "timestamp": time.time(),
            "previous_hash": self._previous_hash,
        }

        # Compute hash
        content = json.dumps(entry_data, sort_keys=True, default=str)
        entry_hash = hashlib.sha256(content.encode()).hexdigest()

        entry = {
            "entry_id": str(uuid.uuid4()),
            **entry_data,
            "hash": entry_hash,
        }

        self._entries.append(entry)
        self._previous_hash = entry_hash

        logger.info("Immutable log entry: %s (hash=%s...)", decision_id, entry_hash[:16])
        return entry

    def verify_integrity(self) -> tuple[bool, str]:
        """Verify the integrity of the entire log by recomputing hashes."""
        prev_hash = "0" * 64
        for i, entry in enumerate(self._entries):
            content = json.dumps(
                {k: v for k, v in entry.items() if k not in ("entry_id", "hash", "previous_hash")},
                sort_keys=True, default=str,
            )
            computed = hashlib.sha256(content.encode()).hexdigest()
            if computed != entry["hash"]:
                return False, f"Integrity violation at entry {i}"
            if entry["previous_hash"] != prev_hash:
                return False, f"Chain broken at entry {i}"
            prev_hash = computed
        return True, "Valid"

    def get_entry(self, decision_id: str) -> Optional[dict]:
        for entry in self._entries:
            if entry["decision_id"] == decision_id:
                return entry
        return None

    def stats(self) -> dict:
        return {
            "total_entries": len(self._entries),
            "is_valid_chain": self.verify_integrity() if self._entries else (True, ""),
        }
