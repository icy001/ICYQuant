"""Model Promotion Manager.

Automatic model stage promotion based on configurable criteria.
Champions are promoted through: Experiment -> Validated -> Champion -> Staging -> Production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PromotionStage(str, Enum):
    EXPERIMENT = "experiment"
    VALIDATED = "validated"
    CHAMPION = "champion"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


@dataclass
class PromotionCriteria:
    """Criteria for automatic promotion.

    Attributes:
        stage: Target stage these criteria apply to.
        min_sharpe: Minimum Sharpe ratio.
        max_drawdown: Maximum drawdown (fraction).
        min_stability: Minimum stability score [0, 1].
        min_ic: Minimum IC.
        min_win_rate: Minimum win rate.
        require_walk_forward: Require walk-forward validation.
        require_champion_superseded: Champion must be superseded for promotion.
    """

    stage: PromotionStage
    min_sharpe: float = 0.0
    max_drawdown: float = 1.0
    min_stability: float = 0.0
    min_ic: float = 0.0
    min_win_rate: float = 0.0
    require_walk_forward: bool = False
    require_champion_superseded: bool = False


@dataclass
class PromotionResult:
    """Result of a promotion check."""

    model_name: str
    from_stage: PromotionStage
    to_stage: Optional[PromotionStage] = None
    promoted: bool = False
    reason: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class PromotionConfig:
    """Promotion system configuration.

    Attributes:
        auto_promote: Enable automatic promotion.
        require_approval: Require human approval for production.
        criteria: Per-stage promotion criteria.
        max_champions: Maximum concurrent champion models.
    """

    auto_promote: bool = True
    require_approval: bool = True
    criteria: List[PromotionCriteria] = field(default_factory=list)
    max_champions: int = 5

    def __post_init__(self) -> None:
        if not self.criteria:
            self.criteria = [
                PromotionCriteria(
                    stage=PromotionStage.VALIDATED,
                    min_sharpe=1.0,
                    max_drawdown=0.3,
                ),
                PromotionCriteria(
                    stage=PromotionStage.CHAMPION,
                    min_sharpe=1.5,
                    max_drawdown=0.2,
                    min_stability=0.6,
                    min_ic=0.02,
                    require_walk_forward=True,
                ),
                PromotionCriteria(
                    stage=PromotionStage.STAGING,
                    min_sharpe=2.0,
                    max_drawdown=0.15,
                    min_stability=0.7,
                    min_ic=0.03,
                ),
                PromotionCriteria(
                    stage=PromotionStage.PRODUCTION,
                    min_sharpe=2.0,
                    max_drawdown=0.1,
                    min_stability=0.8,
                    min_ic=0.04,
                    require_champion_superseded=True,
                ),
            ]


class PromotionManager:
    """Automatic model stage promotion system.

    Evaluates models against criteria and promotes champions
    through the lifecycle stages.
    """

    STAGE_ORDER = [
        PromotionStage.EXPERIMENT,
        PromotionStage.VALIDATED,
        PromotionStage.CHAMPION,
        PromotionStage.STAGING,
        PromotionStage.PRODUCTION,
    ]

    # ---- init ----

    def __init__(self, config: Optional[PromotionConfig] = None) -> None:
        self.config = config or PromotionConfig()
        self._models: Dict[str, PromotionStage] = {}
        self._history: List[PromotionResult] = []

    # ---- stage management ----

    def register(self, model_name: str, stage: PromotionStage = PromotionStage.EXPERIMENT) -> None:
        self._models[model_name] = stage

    def get_stage(self, model_name: str) -> Optional[PromotionStage]:
        return self._models.get(model_name)

    def set_stage(self, model_name: str, stage: PromotionStage) -> None:
        self._models[model_name] = stage

    def is_promotable(self, model_name: str) -> bool:
        stage = self._models.get(model_name)
        if stage is None or stage == PromotionStage.PRODUCTION:
            return False
        return True

    # ---- promotion evaluation ----

    def evaluate(
        self,
        model_name: str,
        metrics: Dict[str, float],
        has_walk_forward: bool = False,
    ) -> PromotionResult:
        """Evaluate a model against promotion criteria.

        Args:
            model_name: Model identifier.
            metrics: Evaluation metrics (sharpe, max_drawdown, stability, ic, win_rate).
            has_walk_forward: Whether walk-forward validation was performed.

        Returns:
            PromotionResult with promotion decision.
        """
        current_stage = self._models.get(model_name, PromotionStage.EXPERIMENT)

        if not self.config.auto_promote:
            return PromotionResult(
                model_name=model_name,
                from_stage=current_stage,
                promoted=False,
                reason="Auto-promotion disabled.",
                metrics=metrics,
            )

        # Find next stage criteria
        current_idx = self.STAGE_ORDER.index(current_stage) if current_stage in self.STAGE_ORDER else 0
        if current_idx >= len(self.STAGE_ORDER) - 1:
            return PromotionResult(
                model_name=model_name,
                from_stage=current_stage,
                promoted=False,
                reason="Already at highest stage.",
                metrics=metrics,
            )

        next_stage = self.STAGE_ORDER[current_idx + 1]
        criteria = self._get_criteria(next_stage)
        if criteria is None:
            return PromotionResult(
                model_name=model_name,
                from_stage=current_stage,
                promoted=False,
                reason=f"No criteria for {next_stage.value}.",
                metrics=metrics,
            )

        # Check criteria
        if not self._meets_criteria(metrics, criteria, has_walk_forward):
            reason = self._failure_reason(metrics, criteria, has_walk_forward)
            return PromotionResult(
                model_name=model_name,
                from_stage=current_stage,
                promoted=False,
                reason=reason,
                metrics=metrics,
            )

        # Check champion limit
        if next_stage == PromotionStage.CHAMPION:
            champion_count = sum(
                1 for s in self._models.values()
                if s in (PromotionStage.CHAMPION, PromotionStage.STAGING, PromotionStage.PRODUCTION)
            )
            if champion_count >= self.config.max_champions:
                return PromotionResult(
                    model_name=model_name,
                    from_stage=current_stage,
                    promoted=False,
                    reason=f"Max champions ({self.config.max_champions}) reached.",
                    metrics=metrics,
                )

        # Check human approval
        if next_stage == PromotionStage.PRODUCTION and self.config.require_approval:
            return PromotionResult(
                model_name=model_name,
                from_stage=current_stage,
                to_stage=next_stage,
                promoted=False,
                reason="Production promotion requires human approval.",
                metrics=metrics,
            )

        # Promote!
        self._models[model_name] = next_stage
        result = PromotionResult(
            model_name=model_name,
            from_stage=current_stage,
            to_stage=next_stage,
            promoted=True,
            reason=f"Promoted to {next_stage.value}.",
            metrics=metrics,
        )
        self._history.append(result)
        return result

    def evaluate_batch(
        self,
        candidates: Dict[str, Dict[str, float]],
        has_walk_forward: bool = False,
    ) -> List[PromotionResult]:
        """Evaluate multiple models."""
        results = []
        for name, metrics in candidates.items():
            results.append(self.evaluate(name, metrics, has_walk_forward))
        return results

    # ---- champions ----

    def list_champions(self) -> List[str]:
        return [
            name for name, stage in self._models.items()
            if stage == PromotionStage.CHAMPION
        ]

    def list_production(self) -> List[str]:
        return [
            name for name, stage in self._models.items()
            if stage == PromotionStage.PRODUCTION
        ]

    def demote(self, model_name: str, reason: str = "") -> PromotionResult:
        """Demote a model to ARCHIVED."""
        old_stage = self._models.get(model_name, PromotionStage.EXPERIMENT)
        self._models[model_name] = PromotionStage.ARCHIVED
        result = PromotionResult(
            model_name=model_name,
            from_stage=old_stage,
            to_stage=PromotionStage.ARCHIVED,
            promoted=False,
            reason=reason or "Manually demoted.",
        )
        self._history.append(result)
        return result

    # ---- history ----

    def get_history(self, model_name: Optional[str] = None) -> List[PromotionResult]:
        if model_name:
            return [r for r in self._history if r.model_name == model_name]
        return list(self._history)

    # ---- internal ----

    def _get_criteria(self, stage: PromotionStage) -> Optional[PromotionCriteria]:
        for c in self.config.criteria:
            if c.stage == stage:
                return c
        return None

    @staticmethod
    def _meets_criteria(
        metrics: Dict[str, float],
        criteria: PromotionCriteria,
        has_walk_forward: bool,
    ) -> bool:
        sharpe = metrics.get("sharpe", 0)
        mdd = metrics.get("max_drawdown", 1)
        stability = metrics.get("stability", 0)
        ic = metrics.get("ic_mean", metrics.get("ic", 0))
        win_rate = metrics.get("win_rate", 0)

        if sharpe < criteria.min_sharpe:
            return False
        if mdd > criteria.max_drawdown:
            return False
        if stability < criteria.min_stability:
            return False
        if ic < criteria.min_ic:
            return False
        if win_rate < criteria.min_win_rate:
            return False
        if criteria.require_walk_forward and not has_walk_forward:
            return False
        return True

    @staticmethod
    def _failure_reason(
        metrics: Dict[str, float],
        criteria: PromotionCriteria,
        has_walk_forward: bool,
    ) -> str:
        reasons = []
        if metrics.get("sharpe", 0) < criteria.min_sharpe:
            reasons.append(f"Sharpe {metrics.get('sharpe', 0):.2f} < {criteria.min_sharpe}")
        if metrics.get("max_drawdown", 1) > criteria.max_drawdown:
            reasons.append(f"MaxDD {metrics.get('max_drawdown', 1):.2%} > {criteria.max_drawdown:.2%}")
        if metrics.get("stability", 0) < criteria.min_stability:
            reasons.append(f"Stability {metrics.get('stability', 0):.2f} < {criteria.min_stability}")
        if metrics.get("ic", 0) < criteria.min_ic:
            reasons.append(f"IC {metrics.get('ic', 0):.4f} < {criteria.min_ic}")
        if criteria.require_walk_forward and not has_walk_forward:
            reasons.append("Walk-forward validation required")
        return "; ".join(reasons) if reasons else "Unknown failure."
