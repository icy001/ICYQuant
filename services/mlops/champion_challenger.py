"""
Champion / Challenger Framework.

Manages the competition between the current production model (Champion)
and candidate models (Challengers). Automatically promotes a challenger
when it consistently outperforms the champion across multiple metrics.
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CCStatus(str, enum.Enum):
    """Status of a champion/challenger contest."""
    ACTIVE = "active"
    CHALLENGER_WON = "challenger_won"
    CHAMPION_RETAINED = "champion_retained"
    PROMOTING = "promoting"
    CANCELLED = "cancelled"


class PromotionDecision(str, enum.Enum):
    """Decision on whether to promote a challenger."""
    PROMOTE = "promote"
    HOLD = "hold"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CCConfig:
    """Configuration for champion/challenger framework."""

    # Evaluation window
    min_evaluation_days: int = 7
    min_predictions: int = 500
    max_challengers: int = 5

    # Performance thresholds for promotion
    sharpe_improvement_pct: float = 0.10  # 10% better Sharpe
    ic_improvement_pct: float = 0.10
    win_rate_improvement_pct: float = 0.05

    # Consistency requirements
    min_consecutive_winning_days: int = 3
    min_metric_count: int = 3  # Must beat in at least N metrics

    # Traffic split
    champion_traffic_pct: float = 80.0
    challenger_traffic_pct: float = 20.0

    # Auto-promotion
    auto_promote: bool = False
    require_approval: bool = True
    cooldown_days: int = 14  # Min days between promotions


@dataclass
class ChampionRecord:
    """Current champion model record."""

    model_name: str = ""
    model_version: str = ""
    deployed_at: float = field(default_factory=time.time)
    metrics_snapshot: Dict[str, float] = field(default_factory=dict)


@dataclass
class ChallengerRecord:
    """A challenger model competing against the champion."""

    model_name: str = ""
    model_version: str = ""
    registered_at: float = field(default_factory=time.time)

    # Cumulative performance during contest
    metrics: Dict[str, float] = field(default_factory=dict)
    predictions_count: int = 0
    evaluation_days: int = 0

    # Head-to-head record
    daily_wins: int = 0
    daily_losses: int = 0
    consecutive_wins: int = 0

    status: CCStatus = CCStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "metrics": self.metrics,
            "predictions_count": self.predictions_count,
            "evaluation_days": self.evaluation_days,
            "daily_wins": self.daily_wins,
            "daily_losses": self.daily_losses,
            "consecutive_wins": self.consecutive_wins,
            "status": self.status.value,
        }


@dataclass
class CCResult:
    """Result of a champion vs challenger evaluation."""

    result_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    champion: ChampionRecord = field(default_factory=ChampionRecord)
    challenger: ChallengerRecord = field(default_factory=ChallengerRecord)

    decision: PromotionDecision = PromotionDecision.HOLD
    reason: str = ""

    # Detailed comparison
    metric_comparisons: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Timing
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "champion": self.champion.model_name,
            "challenger": self.challenger.model_name,
            "decision": self.decision.value,
            "reason": self.reason,
            "metric_comparisons": self.metric_comparisons,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# Champion Challenger
# ---------------------------------------------------------------------------

class ChampionChallenger:
    """Manages champion vs challenger competitions.

    Maintains the current champion model and evaluates challengers
    against it using live prediction data. Automatically determines
    if a challenger should be promoted.

    Usage::

        cc = ChampionChallenger(config)
        cc.set_champion("Alpha_v38", "1.0.0")
        cc.add_challenger("Alpha_v39", "1.0.1")
        result = cc.evaluate()
        if result.decision == PromotionDecision.PROMOTE:
            cc.promote_challenger(result.challenger.model_name)
    """

    # Metrics where higher is better
    HIGHER_BETTER = {"sharpe", "sortino", "ic", "rank_ic", "win_rate", "accuracy"}
    # Metrics where lower is better
    LOWER_BETTER = {"max_drawdown", "turnover", "rmse", "mse", "mae"}

    def __init__(self, config: CCConfig):
        self.config = config

        self._champion: Optional[ChampionRecord] = None
        self._challengers: Dict[str, ChallengerRecord] = {}
        self._history: List[CCResult] = []
        self._last_promotion_time: float = 0.0

        self._on_promote_callbacks: List[Callable] = []

    # ------------------------------------------------------------------
    # Champion Management
    # ------------------------------------------------------------------

    def set_champion(
        self, model_name: str, model_version: str, metrics: Optional[Dict[str, float]] = None
    ) -> ChampionRecord:
        """Set the current champion model.

        Args:
            model_name: Champion model name.
            model_version: Champion version.
            metrics: Baseline metrics snapshot.

        Returns:
            The ChampionRecord.
        """
        self._champion = ChampionRecord(
            model_name=model_name,
            model_version=model_version,
            metrics_snapshot=metrics or {},
        )
        logger.info(f"Champion set: {model_name} v{model_version}")
        return self._champion

    def get_champion(self) -> Optional[ChampionRecord]:
        """Get the current champion."""
        return self._champion

    def update_champion_metrics(self, metrics: Dict[str, float]) -> None:
        """Update the champion's live metrics."""
        if self._champion:
            self._champion.metrics_snapshot.update(metrics)

    # ------------------------------------------------------------------
    # Challenger Management
    # ------------------------------------------------------------------

    def add_challenger(
        self,
        model_name: str,
        model_version: str,
        initial_metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[ChallengerRecord]:
        """Register a new challenger.

        Args:
            model_name: Challenger model name.
            model_version: Challenger version.
            initial_metrics: Optional initial performance metrics.

        Returns:
            ChallengerRecord or None if max challengers reached.
        """
        if len(self._challengers) >= self.config.max_challengers:
            logger.warning(
                f"Max challengers ({self.config.max_challengers}) reached"
            )
            return None

        record = ChallengerRecord(
            model_name=model_name,
            model_version=model_version,
        )
        if initial_metrics:
            record.metrics = initial_metrics

        self._challengers[model_name] = record
        logger.info(f"Challenger added: {model_name} v{model_version}")
        return record

    def remove_challenger(self, model_name: str) -> bool:
        """Remove a challenger from the contest."""
        if model_name in self._challengers:
            del self._challengers[model_name]
            return True
        return False

    def get_challenger(self, model_name: str) -> Optional[ChallengerRecord]:
        """Get a specific challenger."""
        return self._challengers.get(model_name)

    def list_challengers(self) -> List[ChallengerRecord]:
        """List all active challengers."""
        return list(self._challengers.values())

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def record_prediction(
        self,
        challenger_name: str,
        champion_return: float,
        challenger_return: float,
    ) -> None:
        """Record a single prediction comparison.

        Args:
            challenger_name: The challenger being evaluated.
            champion_return: Actual return using champion's prediction.
            challenger_return: Actual return using challenger's prediction.
        """
        challenger = self._challengers.get(challenger_name)
        if not challenger:
            return

        challenger.predictions_count += 1

        if challenger_return > champion_return:
            challenger.daily_wins += 1
            challenger.consecutive_wins += 1
        else:
            challenger.daily_losses += 1
            challenger.consecutive_wins = 0

    def evaluate(self) -> List[CCResult]:
        """Evaluate all challengers against the champion.

        Returns:
            List of CCResult, one per challenger.
        """
        if not self._champion:
            logger.warning("No champion set, cannot evaluate")
            return []

        results: List[CCResult] = []
        for name, challenger in list(self._challengers.items()):
            result = self._evaluate_challenger(challenger)
            results.append(result)

            # Handle auto-promotion
            if result.decision == PromotionDecision.PROMOTE:
                if self.config.auto_promote:
                    self.promote_challenger(name)
                else:
                    logger.info(
                        f"Challenger {name} ready for promotion "
                        f"(approval required)"
                    )

        return results

    def _evaluate_challenger(self, challenger: ChallengerRecord) -> CCResult:
        """Evaluate a single challenger against the champion."""
        if not self._champion:
            return CCResult(
                challenger=challenger,
                decision=PromotionDecision.REJECT,
                reason="No champion set",
            )

        champion = self._champion

        # Check minimum evaluation period
        if challenger.evaluation_days < self.config.min_evaluation_days:
            return CCResult(
                champion=champion,
                challenger=challenger,
                decision=PromotionDecision.HOLD,
                reason=f"Need {self.config.min_evaluation_days} days, have {challenger.evaluation_days}",
            )

        if challenger.predictions_count < self.config.min_predictions:
            return CCResult(
                champion=champion,
                challenger=challenger,
                decision=PromotionDecision.HOLD,
                reason=f"Need {self.config.min_predictions} predictions, have {challenger.predictions_count}",
            )

        # Check cooldown
        if time.time() - self._last_promotion_time < self.config.cooldown_days * 86400:
            return CCResult(
                champion=champion,
                challenger=challenger,
                decision=PromotionDecision.HOLD,
                reason=f"Cooldown period ({self.config.cooldown_days}d) not elapsed",
            )

        # Compare metrics
        champion_metrics = champion.metrics_snapshot
        challenger_metrics = challenger.metrics

        comparisons: Dict[str, Dict[str, float]] = {}
        wins = 0
        total_metrics = 0

        for metric_name in set(
            list(champion_metrics.keys()) + list(challenger_metrics.keys())
        ):
            cv = champion_metrics.get(metric_name, 0)
            clv = challenger_metrics.get(metric_name, 0)

            comparisons[metric_name] = {
                "champion": cv,
                "challenger": clv,
                "diff": clv - cv,
            }

            if metric_name in self.HIGHER_BETTER:
                is_win = clv > cv
            elif metric_name in self.LOWER_BETTER:
                is_win = clv < cv
            else:
                continue  # Unknown metric direction, skip

            if is_win:
                wins += 1
            total_metrics += 1

        # Decision
        result = CCResult(
            champion=champion,
            challenger=challenger,
            metric_comparisons=comparisons,
        )

        win_rate = wins / max(total_metrics, 1)

        if (
            win_rate >= 0.5  # Wins majority of metrics
            and challenger.consecutive_wins >= self.config.min_consecutive_winning_days
        ):
            result.decision = PromotionDecision.PROMOTE
            result.reason = (
                f"Challenger wins {wins}/{total_metrics} metrics "
                f"with {challenger.consecutive_wins} consecutive wins"
            )
        elif win_rate >= 0.5:
            result.decision = PromotionDecision.HOLD
            result.reason = (
                f"Challenger leads {wins}/{total_metrics} metrics "
                f"but needs {self.config.min_consecutive_winning_days} consecutive wins "
                f"(has {challenger.consecutive_wins})"
            )
        else:
            result.decision = PromotionDecision.REJECT
            result.reason = f"Challenger wins only {wins}/{total_metrics} metrics"

        self._history.append(result)
        return result

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def promote_challenger(self, challenger_name: str) -> bool:
        """Promote a challenger to champion.

        Args:
            challenger_name: Name of the challenger to promote.

        Returns:
            True if promotion successful.
        """
        challenger = self._challengers.get(challenger_name)
        if not challenger:
            logger.error(f"Challenger {challenger_name} not found")
            return False

        old_champion = self._champion

        # Set new champion
        self._champion = ChampionRecord(
            model_name=challenger.model_name,
            model_version=challenger.model_version,
            metrics_snapshot=dict(challenger.metrics),
        )

        # Remove promoted challenger
        del self._challengers[challenger_name]

        self._last_promotion_time = time.time()

        logger.info(
            f"Challenger promoted: {challenger.model_name} v{challenger.model_version} "
            f"replaces {old_champion.model_name if old_champion else 'None'}"
        )

        # Archive old champion as new challenger if desired
        if old_champion and old_champion.model_name != challenger.model_name:
            # Old champion becomes a challenger for future comparison
            if len(self._challengers) < self.config.max_challengers:
                self._challengers[old_champion.model_name] = ChallengerRecord(
                    model_name=old_champion.model_name,
                    model_version=old_champion.model_version,
                    metrics=old_champion.metrics_snapshot,
                    status=CCStatus.CHAMPION_RETAINED,
                )

        self._notify_promote(challenger, old_champion)
        return True

    # ------------------------------------------------------------------
    # Callbacks & History
    # ------------------------------------------------------------------

    def on_promote(self, callback: Callable) -> None:
        """Register a callback for challenger promotion events."""
        self._on_promote_callbacks.append(callback)

    def _notify_promote(
        self, challenger: ChallengerRecord, old_champion: Optional[ChampionRecord]
    ) -> None:
        for cb in self._on_promote_callbacks:
            try:
                cb(challenger, old_champion)
            except Exception as e:
                logger.error(f"Promote callback error: {e}")

    def get_history(self, limit: int = 50) -> List[CCResult]:
        """Get champion/challenger evaluation history."""
        return sorted(self._history, key=lambda r: r.evaluated_at, reverse=True)[:limit]

    def get_status(self) -> Dict[str, Any]:
        """Get current champion/challenger status summary."""
        return {
            "champion": (
                {
                    "model_name": self._champion.model_name,
                    "model_version": self._champion.model_version,
                    "deployed_at": self._champion.deployed_at,
                }
                if self._champion
                else None
            ),
            "challengers": [c.to_dict() for c in self._challengers.values()],
            "challenger_count": len(self._challengers),
            "total_evaluations": len(self._history),
        }

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._champion = None
        self._challengers.clear()
        self._history.clear()
        self._last_promotion_time = 0.0
