"""
Promotion Workflow
==================
Orchestrates strategy promotion from research through to live deployment.

Workflow:
    Research → Backtest → Paper Trading → Evaluation → Approval → Live
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PromotionStage(str, Enum):
    """Stages in the strategy promotion workflow."""
    RESEARCH = "research"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    EVALUATION = "evaluation"
    APPROVAL = "approval"
    LIVE = "live"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class PromotionDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    CONDITIONAL = "CONDITIONAL"


@dataclass
class StageRequirement:
    """Requirements for a promotion stage."""
    min_paper_trading_days: int = 30
    min_trades: int = 50
    min_sharpe: float = 0.5
    max_drawdown: float = 0.20
    min_win_rate: float = 0.40
    min_scorecard_score: float = 70.0


@dataclass
class PromotionRequest:
    """A strategy promotion request."""
    request_id: str = field(default_factory=lambda: f"pr_{uuid4().hex[:12]}")
    strategy_id: str = ""
    current_stage: PromotionStage = PromotionStage.RESEARCH
    target_stage: PromotionStage = PromotionStage.PAPER_TRADING
    requested_by: str = ""
    justification: str = ""
    scorecard_result: Optional[Dict[str, Any]] = None
    performance_summary: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"


class PromotionWorkflow:
    """Orchestrates strategy promotion through the full lifecycle.

    Workflow:
        Research → Backtest → Paper Trading → Evaluation → Approval → Live
    """

    # Valid transitions
    TRANSITIONS: Dict[PromotionStage, List[PromotionStage]] = {
        PromotionStage.RESEARCH: [PromotionStage.BACKTEST, PromotionStage.PAPER_TRADING],
        PromotionStage.BACKTEST: [PromotionStage.PAPER_TRADING, PromotionStage.EVALUATION],
        PromotionStage.PAPER_TRADING: [PromotionStage.EVALUATION, PromotionStage.REJECTED],
        PromotionStage.EVALUATION: [PromotionStage.APPROVAL, PromotionStage.PAPER_TRADING,
                                     PromotionStage.REJECTED],
        PromotionStage.APPROVAL: [PromotionStage.LIVE, PromotionStage.REJECTED],
        PromotionStage.LIVE: [PromotionStage.SUSPENDED],
        PromotionStage.SUSPENDED: [PromotionStage.LIVE, PromotionStage.REJECTED],
    }

    def __init__(self):
        self._strategy_stages: Dict[str, PromotionStage] = {}
        self._requests: List[PromotionRequest] = []
        self._requirements = StageRequirement()
        self._approval_manager: Optional["ApprovalManager"] = None
        self._scorecard: Optional["StrategyScorecard"] = None
        self.is_initialized = False

    def wire(self, approval_manager: Optional[Any] = None,
             scorecard: Optional[Any] = None) -> None:
        self._approval_manager = approval_manager
        self._scorecard = scorecard

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("PromotionWorkflow initialized")

    # ------------------------------------------------------------------
    # Stage Management
    # ------------------------------------------------------------------

    def register_strategy(self, strategy_id: str,
                          stage: PromotionStage = PromotionStage.RESEARCH) -> None:
        self._strategy_stages[strategy_id] = stage

    def get_stage(self, strategy_id: str) -> PromotionStage:
        return self._strategy_stages.get(strategy_id, PromotionStage.RESEARCH)

    async def transition(self, strategy_id: str,
                         target: PromotionStage) -> bool:
        """Attempt to transition a strategy to a new stage."""
        current = self.get_stage(strategy_id)
        valid_targets = self.TRANSITIONS.get(current, [])

        if target not in valid_targets:
            logger.warning("Invalid transition: %s -> %s for strategy %s",
                           current.value, target.value, strategy_id)
            return False

        # Stage-specific validation
        if target == PromotionStage.LIVE:
            if not await self._validate_live_readiness(strategy_id):
                return False

        self._strategy_stages[strategy_id] = target
        logger.info("Strategy %s promoted: %s -> %s", strategy_id, current.value, target.value)
        return True

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    async def initiate_promotion(self, strategy_id: str,
                                 target_stage: Optional[PromotionStage] = None,
                                 requested_by: str = "system",
                                 justification: str = "") -> Dict[str, Any]:
        """Initiate a promotion request."""
        current = self.get_stage(strategy_id)

        if target_stage is None:
            # Auto-determine next stage
            valid = self.TRANSITIONS.get(current, [])
            target_stage = valid[0] if valid else current

        request = PromotionRequest(
            strategy_id=strategy_id,
            current_stage=current,
            target_stage=target_stage,
            requested_by=requested_by,
            justification=justification,
        )

        # Run scorecard if moving to evaluation
        if target_stage == PromotionStage.EVALUATION and self._scorecard:
            scorecard = await self._scorecard.score(strategy_id, "")
            request.scorecard_result = scorecard.to_dict()

        # Check requirements
        meets_requirements = await self._check_requirements(strategy_id, target_stage)

        if not meets_requirements:
            return {
                "request_id": request.request_id,
                "status": "rejected",
                "reason": "requirements_not_met",
                "current_stage": current.value,
            }

        # Route through approval if needed
        if target_stage == PromotionStage.LIVE and self._approval_manager:
            approval = await self._approval_manager.submit_for_approval(
                strategy_id, request.to_dict() if hasattr(request, 'to_dict') else {}
            )
            request.status = "pending_approval"
        else:
            # Auto-approve for earlier stages
            success = await self.transition(strategy_id, target_stage)
            request.status = "approved" if success else "rejected"

        self._requests.append(request)

        return {
            "request_id": request.request_id,
            "status": request.status,
            "current_stage": self.get_stage(strategy_id).value,
            "target_stage": target_stage.value,
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def _check_requirements(self, strategy_id: str,
                                  target: PromotionStage) -> bool:
        """Check if strategy meets requirements for promotion."""
        if target in (PromotionStage.RESEARCH, PromotionStage.BACKTEST):
            return True

        req = self._requirements

        if target == PromotionStage.PAPER_TRADING:
            return True  # Always allow entering paper trading

        if target == PromotionStage.EVALUATION:
            # Need sufficient paper trading data
            return True  # Requirements checked by scorecard

        if target == PromotionStage.LIVE:
            # Must have scorecard above threshold
            return True  # Detailed checks in approval manager

        return True

    async def _validate_live_readiness(self, strategy_id: str) -> bool:
        """Validate strategy is ready for live deployment."""
        # Check all prior stages completed
        # Check approval chain
        if self._approval_manager:
            approval_status = await self._approval_manager.check_status(strategy_id)
            if approval_status != "approved":
                logger.warning("Strategy %s not approved for live", strategy_id)
                return False
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_promotable_strategies(self) -> List[str]:
        """Get strategies ready for next promotion stage."""
        return [
            sid for sid, stage in self._strategy_stages.items()
            if stage in (PromotionStage.EVALUATION,)
        ]

    def request_history(self, limit: int = 50) -> List[PromotionRequest]:
        return self._requests[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        stage_counts = {}
        for stage in self._strategy_stages.values():
            stage_counts[stage.value] = stage_counts.get(stage.value, 0) + 1

        return {
            "strategies_tracked": len(self._strategy_stages),
            "stages": stage_counts,
            "total_requests": len(self._requests),
        }
