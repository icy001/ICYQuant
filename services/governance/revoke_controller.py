"""
Revoke Controller — manages authority/delegation revocation with cascade.

Part 1.5: supports targeted revocation with delegation cascade — when an
authority is revoked, all dependent delegations are automatically invalidated.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


class RevokeController:
    """Manages authority and delegation revocation with cascade.

    When Authority A is revoked, all delegations from A become invalid.
    """

    def __init__(self):
        self._revocations: List[Dict[str, Any]] = []
        self._authority_graph: Dict[str, List[str]] = {}  # authority_id → [delegation_ids]

    def register_authority(self, authority_id: str) -> None:
        """Register an authority in the revocation graph."""
        if authority_id not in self._authority_graph:
            self._authority_graph[authority_id] = []

    def register_delegation(self, delegation_id: str, source_authority: str) -> None:
        """Register a delegation from an authority."""
        if source_authority not in self._authority_graph:
            self._authority_graph[source_authority] = []
        if delegation_id not in self._authority_graph[source_authority]:
            self._authority_graph[source_authority].append(delegation_id)

    def revoke(
        self,
        target: str,
        reason: str = "",
        correlation_id: str = "",
        cascade: bool = True,
    ) -> Dict[str, Any]:
        """Revoke an authority and optionally cascade.

        Args:
            target: Authority ID to revoke
            reason: Reason for revocation
            correlation_id: Audit correlation ID
            cascade: Whether to cascade to delegations
        """
        revoke_id = f"REV-{uuid.uuid4().hex[:12].upper()}"

        # Find dependent delegations
        dependent_delegations = []
        if cascade and target in self._authority_graph:
            dependent_delegations = list(self._authority_graph[target])

        record = {
            "revoke_id": revoke_id,
            "target": target,
            "reason": reason,
            "correlation_id": correlation_id,
            "cascade": cascade,
            "dependent_delegations": dependent_delegations,
            "revoked_at": time.time(),
            "status": "COMPLETED",
        }

        # Cascade — invalidate all dependent delegations
        for del_id in dependent_delegations:
            self._authority_graph[target] = [
                d for d in self._authority_graph.get(target, []) if d != del_id
            ]

        self._revocations.append(record)
        return record

    def get_active_revocations(self) -> List[str]:
        """Get list of revoked authority IDs."""
        return [r["target"] for r in self._revocations if r.get("cascade")]

    def get_revocation_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._revocations[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_revocations": len(self._revocations),
            "authorities_tracked": len(self._authority_graph),
            "total_delegations": sum(len(v) for v in self._authority_graph.values()),
        }
