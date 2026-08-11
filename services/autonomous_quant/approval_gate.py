"""Approval Gate — Gates production proposals through approval workflow."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ApprovalGate:
    """Gates autonomous proposals through approval before production."""

    async def request_approval(
        self,
        candidate: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        return {
            "candidate_id": candidate.get("strategy_id", candidate.get("alpha_id", "")),
            "status": "pending_approval",
            "reason": reason,
            "requires_human": True,
        }

    async def approve(self, approval_id: str) -> Dict[str, Any]:
        return {"approval_id": approval_id, "status": "approved"}

    async def reject(self, approval_id: str, reason: str) -> Dict[str, Any]:
        return {"approval_id": approval_id, "status": "rejected", "reason": reason}
