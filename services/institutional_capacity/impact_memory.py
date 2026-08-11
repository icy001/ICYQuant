"""
Impact Memory — Tracks market impact estimates and realized outcomes.

Records predicted vs actual impact for model calibration and
provides historical context for impact-aware execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ImpactEventType(str, Enum):
    ESTIMATED = "estimated"
    REALIZED = "realized"
    CALIBRATED = "calibrated"
    BUDGET_CONSUMED = "budget_consumed"
    BUDGET_RESET = "budget_reset"
    BUDGET_BREACH = "budget_breach"
    MODEL_FIT = "model_fit"
    SNAPSHOT = "snapshot"


@dataclass
class ImpactEvent:
    """A single market impact event."""

    event_id: str = field(default_factory=lambda: f"IE-{uuid.uuid4().hex[:8]}")
    event_type: ImpactEventType = ImpactEventType.ESTIMATED
    asset: str = ""
    order_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Impact values
    estimated_impact_bps: float = 0.0
    realized_impact_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0

    # Order context
    order_size: float = 0.0
    avg_daily_volume: float = 0.0
    volatility: float = 0.0
    participation_rate: float = 0.0
    execution_duration_seconds: float = 0.0

    # Model info
    model_name: str = ""
    model_error_bps: float = 0.0

    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def estimation_error_bps(self) -> float:
        return self.realized_impact_bps - self.estimated_impact_bps

    @property
    def estimation_error_pct(self) -> float:
        if self.estimated_impact_bps == 0:
            return 0.0 if self.realized_impact_bps == 0 else float("inf")
        return (self.realized_impact_bps - self.estimated_impact_bps) / self.estimated_impact_bps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "asset": self.asset,
            "order_id": self.order_id,
            "estimated_impact_bps": round(self.estimated_impact_bps, 4),
            "realized_impact_bps": round(self.realized_impact_bps, 4),
            "estimation_error_bps": round(self.estimation_error_bps, 4),
            "temporary_impact_bps": round(self.temporary_impact_bps, 4),
            "permanent_impact_bps": round(self.permanent_impact_bps, 4),
            "participation_rate": round(self.participation_rate, 4),
            "execution_duration_seconds": self.execution_duration_seconds,
            "model_name": self.model_name,
        }


class ImpactMemory:
    """Records and analyzes market impact events for model improvement.

    Key features:
    - Estimation vs realization tracking
    - Model calibration via error analysis
    - Budget consumption tracking
    - Per-asset impact history
    """

    def __init__(self):
        self._events: List[ImpactEvent] = []
        self._budgets: Dict[str, float] = {}  # per-asset budget
        self._budget_consumed: Dict[str, float] = {}  # consumed amount
        self._max_events: int = 10000

    # ── Event Recording ───────────────────────────────────────────

    def record_estimation(self,
                          asset: str,
                          order_id: str,
                          estimated_impact_bps: float,
                          order_size: float,
                          avg_daily_volume: float,
                          volatility: float,
                          participation_rate: float,
                          model_name: str = "",
                          temporary_impact_bps: float = 0.0,
                          permanent_impact_bps: float = 0.0) -> ImpactEvent:
        """Record a pre-trade impact estimation."""
        event = ImpactEvent(
            event_type=ImpactEventType.ESTIMATED,
            asset=asset,
            order_id=order_id,
            estimated_impact_bps=estimated_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            permanent_impact_bps=permanent_impact_bps,
            order_size=order_size,
            avg_daily_volume=avg_daily_volume,
            volatility=volatility,
            participation_rate=participation_rate,
            model_name=model_name,
        )
        self._events.append(event)
        self._prune()
        return event

    def record_realized(self,
                        asset: str,
                        order_id: str,
                        realized_impact_bps: float,
                        execution_duration_seconds: float = 0.0,
                        temporary_impact_bps: float = 0.0,
                        permanent_impact_bps: float = 0.0) -> ImpactEvent:
        """Record post-trade realized impact."""
        event = ImpactEvent(
            event_type=ImpactEventType.REALIZED,
            asset=asset,
            order_id=order_id,
            realized_impact_bps=realized_impact_bps,
            temporary_impact_bps=temporary_impact_bps,
            permanent_impact_bps=permanent_impact_bps,
            execution_duration_seconds=execution_duration_seconds,
        )
        self._events.append(event)
        self._prune()
        return event

    def record_budget_consumed(self,
                                asset: str,
                                amount_bps: float,
                                order_id: str = "") -> ImpactEvent:
        """Record impact budget consumption."""
        self._budget_consumed[asset] = self._budget_consumed.get(asset, 0.0) + amount_bps

        event = ImpactEvent(
            event_type=ImpactEventType.BUDGET_CONSUMED,
            asset=asset,
            order_id=order_id,
            realized_impact_bps=amount_bps,
            data={
                "budget_limit": self._budgets.get(asset, float("inf")),
                "consumed_total": self._budget_consumed[asset],
                "remaining": self.remaining_budget(asset),
            },
        )

        if self.is_budget_breached(asset):
            event.event_type = ImpactEventType.BUDGET_BREACH

        self._events.append(event)
        self._prune()
        return event

    # ── Budget Management ─────────────────────────────────────────

    def set_budget(self, asset: str, budget_bps: float) -> None:
        self._budgets[asset] = budget_bps

    def get_budget(self, asset: str) -> float:
        return self._budgets.get(asset, float("inf"))

    def consumed_budget(self, asset: str) -> float:
        return self._budget_consumed.get(asset, 0.0)

    def remaining_budget(self, asset: str) -> float:
        return max(0.0, self.get_budget(asset) - self.consumed_budget(asset))

    def is_budget_breached(self, asset: str) -> bool:
        return self.consumed_budget(asset) > self.get_budget(asset)

    def reset_budget(self, asset: str) -> ImpactEvent:
        """Reset consumed budget for an asset."""
        old = self._budget_consumed.get(asset, 0.0)
        self._budget_consumed[asset] = 0.0

        event = ImpactEvent(
            event_type=ImpactEventType.BUDGET_RESET,
            asset=asset,
            data={"previous_consumed": old},
        )
        self._events.append(event)
        return event

    # ── Model Analysis ────────────────────────────────────────────

    def estimation_errors(self,
                           asset: Optional[str] = None,
                           model_name: Optional[str] = None) -> List[float]:
        """Get estimation errors (realized - estimated) for calibration."""
        estimations = {e.order_id: e for e in self._events
                       if e.event_type == ImpactEventType.ESTIMATED}
        realizations = {e.order_id: e for e in self._events
                        if e.event_type == ImpactEventType.REALIZED}

        errors: List[float] = []
        for order_id, est in estimations.items():
            if order_id in realizations:
                if asset and est.asset != asset:
                    continue
                if model_name and est.model_name != model_name:
                    continue
                errors.append(realizations[order_id].realized_impact_bps - est.estimated_impact_bps)

        return errors

    def mean_error_bps(self,
                        asset: Optional[str] = None,
                        model_name: Optional[str] = None) -> float:
        errors = self.estimation_errors(asset, model_name)
        if not errors:
            return 0.0
        return sum(errors) / len(errors)

    def rmse_bps(self,
                  asset: Optional[str] = None,
                  model_name: Optional[str] = None) -> float:
        errors = self.estimation_errors(asset, model_name)
        if not errors:
            return 0.0
        return (sum(e ** 2 for e in errors) / len(errors)) ** 0.5

    def mae_bps(self,
                 asset: Optional[str] = None,
                 model_name: Optional[str] = None) -> float:
        errors = self.estimation_errors(asset, model_name)
        if not errors:
            return 0.0
        return sum(abs(e) for e in errors) / len(errors)

    def hit_rate(self,
                  asset: Optional[str] = None,
                  tolerance_bps: float = 1.0) -> float:
        """Fraction of estimates within N bps of realized."""
        errors = self.estimation_errors(asset)
        if not errors:
            return 1.0
        within = sum(1 for e in errors if abs(e) <= tolerance_bps)
        return within / len(errors)

    # ── Queries ───────────────────────────────────────────────────

    def recent_events(self, limit: int = 100) -> List[ImpactEvent]:
        return self._events[-limit:]

    def events_by_type(self, event_type: ImpactEventType) -> List[ImpactEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def events_by_asset(self, asset: str) -> List[ImpactEvent]:
        return [e for e in self._events if e.asset == asset]

    def events_by_order(self, order_id: str) -> List[ImpactEvent]:
        return [e for e in self._events if e.order_id == order_id]

    def budget_breaches(self) -> List[ImpactEvent]:
        return self.events_by_type(ImpactEventType.BUDGET_BREACH)

    def avg_impact_per_asset(self) -> Dict[str, float]:
        """Average realized impact per asset."""
        realizations = self.events_by_type(ImpactEventType.REALIZED)
        by_asset: Dict[str, List[float]] = {}
        for e in realizations:
            by_asset.setdefault(e.asset, []).append(e.realized_impact_bps)

        return {
            asset: sum(vals) / len(vals)
            for asset, vals in by_asset.items()
        }

    # ── Utility ───────────────────────────────────────────────────

    def _prune(self) -> None:
        while len(self._events) > self._max_events:
            self._events.pop(0)

    def event_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._budgets.clear()
        self._budget_consumed.clear()

    def summary(self) -> Dict[str, Any]:
        return {
            "total_events": self.event_count(),
            "mean_error_bps": round(self.mean_error_bps(), 4),
            "rmse_bps": round(self.rmse_bps(), 4),
            "mae_bps": round(self.mae_bps(), 4),
            "hit_rate_1bps": round(self.hit_rate(tolerance_bps=1.0), 4),
            "budget_breaches": len(self.budget_breaches()),
            "tracked_assets": len(self.avg_impact_per_asset()),
            "budgets": {a: {"limit": self.get_budget(a), "consumed": self.consumed_budget(a),
                            "remaining": self.remaining_budget(a)}
                        for a in set(list(self._budgets.keys()) + list(self._budget_consumed.keys()))},
        }
