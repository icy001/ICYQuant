"""
Approval Manager
================
Manages the approval chain for strategy promotion to live trading.

Supports:
    - Manual Approval
    - Multi-Level Approval
    - Risk Approval
    - Compliance Approval
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_REVISION = "NEEDS_REVISION"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class ApprovalLevel(str, Enum):
    ANALYST = "ANALYST"            # Strategy analyst review
    RISK = "RISK"                  # Risk manager review
    COMPLIANCE = "COMPLIANCE"      # Compliance review
    SENIOR = "SENIOR"              # Senior management sign-off
    FINAL = "FINAL"                # Final approval


@dataclass
class ApprovalRequest:
    """An approval request in the chain."""
    approval_id: str = field(default_factory=lambda: f"appr_{uuid4().hex[:12]}")
    strategy_id: str = ""
    level: ApprovalLevel = ApprovalLevel.ANALYST
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = ""
    assigned_to: str = ""
    comments: str = ""
    decided_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ApprovalManager:
    """Manages multi-level approval chain for strategy promotion.

    Supports Analyst → Risk → Compliance → Senior → Final approval flow.
    """

    # Default approval chain for live deployment
    LIVE_APPROVAL_CHAIN: List[ApprovalLevel] = [
        ApprovalLevel.ANALYST,
        ApprovalLevel.RISK,
        ApprovalLevel.COMPLIANCE,
        ApprovalLevel.SENIOR,
        ApprovalLevel.FINAL,
    ]

    def __init__(self):
        self._approvals: Dict[str, List[ApprovalRequest]] = {}
        self._chain = list(self.LIVE_APPROVAL_CHAIN)
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("ApprovalManager initialized (chain=%s)",
                     [l.value for l in self._chain])

    # ------------------------------------------------------------------
    # Approval Flow
    # ------------------------------------------------------------------

    async def submit_for_approval(self, strategy_id: str,
                                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Submit a strategy for the full approval chain."""
        approvals = []
        for level in self._chain:
            approval = ApprovalRequest(
                strategy_id=strategy_id,
                level=level,
                metadata=metadata or {},
            )
            approvals.append(approval)

        self._approvals[strategy_id] = approvals
        logger.info("Strategy %s submitted for approval: %d levels",
                     strategy_id, len(approvals))

        return {
            "strategy_id": strategy_id,
            "total_levels": len(approvals),
            "current_level": self._chain[0].value,
            "status": ApprovalStatus.PENDING.value,
        }

    async def approve(self, strategy_id: str, level: ApprovalLevel,
                      reviewer: str = "", comments: str = "") -> bool:
        """Approve a strategy at a specific approval level."""
        approvals = self._approvals.get(strategy_id, [])
        for a in approvals:
            if a.level == level and a.status == ApprovalStatus.PENDING:
                a.status = ApprovalStatus.APPROVED
                a.assigned_to = reviewer
                a.comments = comments
                a.decided_at = datetime.now(timezone.utc)
                logger.info("Strategy %s approved at level %s by %s",
                             strategy_id, level.value, reviewer)
                return True
        return False

    async def reject(self, strategy_id: str, level: ApprovalLevel,
                     reviewer: str = "", reason: str = "") -> bool:
        """Reject a strategy at a specific approval level."""
        approvals = self._approvals.get(strategy_id, [])
        for a in approvals:
            if a.level == level and a.status == ApprovalStatus.PENDING:
                a.status = ApprovalStatus.REJECTED
                a.assigned_to = reviewer
                a.comments = reason
                a.decided_at = datetime.now(timezone.utc)
                logger.warning("Strategy %s REJECTED at level %s by %s: %s",
                               strategy_id, level.value, reviewer, reason)
                return True
        return False

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def check_status(self, strategy_id: str) -> str:
        """Check overall approval status for a strategy."""
        approvals = self._approvals.get(strategy_id, [])
        if not approvals:
            return "not_submitted"

        if any(a.status == ApprovalStatus.REJECTED for a in approvals):
            return "rejected"

        if all(a.status == ApprovalStatus.APPROVED for a in approvals):
            return "approved"

        return "pending"

    def pending_levels(self, strategy_id: str) -> List[ApprovalLevel]:
        """Get pending approval levels for a strategy."""
        approvals = self._approvals.get(strategy_id, [])
        return [a.level for a in approvals if a.status == ApprovalStatus.PENDING]

    def current_level(self, strategy_id: str) -> Optional[ApprovalLevel]:
        """Get the current (first pending) approval level."""
        pending = self.pending_levels(strategy_id)
        return pending[0] if pending else None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_chain(self, chain: List[ApprovalLevel]) -> None:
        self._chain = chain

    def get_metrics(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._approvals.values())
        approved = sum(
            1 for v in self._approvals.values()
            for a in v if a.status == ApprovalStatus.APPROVED
        )
        return {
            "strategies_in_approval": len(self._approvals),
            "total_approval_requests": total,
            "approved_count": approved,
            "chain": [l.value for l in self._chain],
        }
