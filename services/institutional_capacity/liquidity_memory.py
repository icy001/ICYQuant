"""
Liquidity Memory — Append-only event log for liquidity lifecycle events.

Records liquidity regime changes, score variations, shock events,
and provides historical context for liquidity analysis.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .liquidity_profile import LiquidityProfile


class LiquidityEventType(str, Enum):
    REGIME_CHANGE = "regime_change"
    SCORE_UPDATE = "score_update"
    PROFILE_UPDATED = "profile_updated"
    SPREAD_EVENT = "spread_event"
    VOLUME_EVENT = "volume_event"
    DEPTH_EVENT = "depth_event"
    SHOCK_DETECTED = "shock_detected"
    STRESS_TEST = "stress_test"
    SCENARIO_RUN = "scenario_run"
    THRESHOLD_BREACH = "threshold_breach"
    ALERT_TRIGGERED = "alert_triggered"
    SNAPSHOT = "snapshot"


@dataclass
class LiquidityEvent:
    """A single liquidity lifecycle event."""

    event_id: str = field(default_factory=lambda: f"LE-{uuid.uuid4().hex[:8]}")
    event_type: LiquidityEventType = LiquidityEventType.SCORE_UPDATE
    asset: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Event data
    previous_regime: str = ""
    new_regime: str = ""
    previous_score: float = 0.0
    new_score: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "asset": self.asset,
            "timestamp": self.timestamp.isoformat(),
            "previous_regime": self.previous_regime,
            "new_regime": self.new_regime,
            "previous_score": self.previous_score,
            "new_score": self.new_score,
            "data": self.data,
        }


@dataclass
class LiquiditySnapshot:
    """Point-in-time snapshot of liquidity state across assets."""

    snapshot_id: str = field(default_factory=lambda: f"LSNAP-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    label: str = ""

    # Per-asset state
    profiles: Dict[str, LiquidityProfile] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    regimes: Dict[str, str] = field(default_factory=dict)
    spreads: Dict[str, float] = field(default_factory=dict)
    volumes: Dict[str, float] = field(default_factory=dict)

    # Aggregate
    avg_score: float = 0.0
    crisis_assets: int = 0
    stressed_assets: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "label": self.label,
            "asset_count": len(self.profiles),
            "avg_score": round(self.avg_score, 2),
            "crisis_assets": self.crisis_assets,
            "stressed_assets": self.stressed_assets,
            "regimes": self.regimes,
        }


class LiquidityMemory:
    """Append-only event log for liquidity lifecycle.

    Tracks: regime transitions, score trends, shock events,
    and market-wide liquidity evolution over time.
    """

    def __init__(self):
        self._events: List[LiquidityEvent] = []
        self._snapshots: List[LiquiditySnapshot] = []
        self._current_regimes: Dict[str, str] = {}
        self._current_scores: Dict[str, float] = {}
        self._max_events: int = 10000
        self._max_snapshots: int = 100

    # ── Event Recording ───────────────────────────────────────────

    def record_event(self,
                     event_type: LiquidityEventType,
                     asset: str = "",
                     data: Optional[Dict[str, Any]] = None,
                     previous_regime: str = "",
                     new_regime: str = "",
                     previous_score: float = 0.0,
                     new_score: float = 0.0) -> LiquidityEvent:
        """Record a liquidity event."""
        event = LiquidityEvent(
            event_type=event_type,
            asset=asset,
            data=data or {},
            previous_regime=previous_regime,
            new_regime=new_regime,
            previous_score=previous_score,
            new_score=new_score,
        )
        self._events.append(event)

        # Update current state
        if new_regime:
            self._current_regimes[asset] = new_regime
        if new_score > 0:
            self._current_scores[asset] = new_score

        # Prune
        while len(self._events) > self._max_events:
            self._events.pop(0)

        return event

    def record_regime_change(self,
                              asset: str,
                              from_regime: str,
                              to_regime: str,
                              reason: str = "") -> LiquidityEvent:
        return self.record_event(
            event_type=LiquidityEventType.REGIME_CHANGE,
            asset=asset,
            previous_regime=from_regime,
            new_regime=to_regime,
            data={"reason": reason},
        )

    def record_score_update(self,
                             asset: str,
                             old_score: float,
                             new_score: float) -> LiquidityEvent:
        return self.record_event(
            event_type=LiquidityEventType.SCORE_UPDATE,
            asset=asset,
            previous_score=old_score,
            new_score=new_score,
            data={"delta": new_score - old_score},
        )

    def record_shock(self,
                     asset: str,
                     severity: float,
                     shock_type: str = "") -> LiquidityEvent:
        return self.record_event(
            event_type=LiquidityEventType.SHOCK_DETECTED,
            asset=asset,
            data={"severity": severity, "shock_type": shock_type},
        )

    def record_alarm(self,
                     asset: str,
                     message: str,
                     threshold: float,
                     current: float) -> LiquidityEvent:
        return self.record_event(
            event_type=LiquidityEventType.THRESHOLD_BREACH,
            asset=asset,
            data={
                "message": message,
                "threshold": threshold,
                "current": current,
            },
        )

    # ── Snapshot ──────────────────────────────────────────────────

    def create_snapshot(self,
                        label: str = "",
                        profiles: Optional[Dict[str, LiquidityProfile]] = None) -> LiquiditySnapshot:
        """Create a point-in-time liquidity snapshot."""
        profiles = profiles or {}
        scores = self._current_scores.copy()
        regimes = self._current_regimes.copy()

        snapshot = LiquiditySnapshot(
            label=label,
            profiles=profiles,
            scores=scores,
            regimes=regimes,
            spreads={k: v.spread_bps for k, v in profiles.items()},
            volumes={k: v.avg_daily_volume for k, v in profiles.items()},
            avg_score=sum(scores.values()) / len(scores) if scores else 0.0,
            crisis_assets=sum(1 for r in regimes.values() if r == "CRISIS"),
            stressed_assets=sum(1 for r in regimes.values() if r in ("STRESSED", "CRISIS")),
        )
        self._snapshots.append(snapshot)

        self.record_event(
            event_type=LiquidityEventType.SNAPSHOT,
            data={"label": label, "snapshot_id": snapshot.snapshot_id},
        )

        while len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

        return snapshot

    # ── Queries ───────────────────────────────────────────────────

    def recent_events(self, limit: int = 100) -> List[LiquidityEvent]:
        return self._events[-limit:]

    def events_by_type(self, event_type: LiquidityEventType) -> List[LiquidityEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def events_by_asset(self, asset: str) -> List[LiquidityEvent]:
        return [e for e in self._events if e.asset == asset]

    def regime_changes(self, asset: Optional[str] = None) -> List[LiquidityEvent]:
        events = self.events_by_type(LiquidityEventType.REGIME_CHANGE)
        if asset:
            events = [e for e in events if e.asset == asset]
        return events

    def get_current_regime(self, asset: str) -> str:
        return self._current_regimes.get(asset, "UNKNOWN")

    def get_current_score(self, asset: str) -> float:
        return self._current_scores.get(asset, 0.0)

    def latest_snapshot(self) -> Optional[LiquiditySnapshot]:
        return self._snapshots[-1] if self._snapshots else None

    def snapshots_since(self, since: datetime) -> List[LiquiditySnapshot]:
        return [s for s in self._snapshots if s.timestamp >= since]

    def shock_events(self) -> List[LiquidityEvent]:
        return self.events_by_type(LiquidityEventType.SHOCK_DETECTED)

    def threshold_breaches(self) -> List[LiquidityEvent]:
        return self.events_by_type(LiquidityEventType.THRESHOLD_BREACH)

    def count_crisis_events(self, asset: Optional[str] = None) -> int:
        changes = self.regime_changes(asset)
        return sum(1 for e in changes if e.new_regime == "CRISIS")

    # ── Trend Analysis ────────────────────────────────────────────

    def score_trend(self, asset: str, lookback_events: int = 20) -> List[float]:
        """Recent score trajectory for an asset."""
        events = self.events_by_asset(asset)
        score_events = [e for e in events if e.event_type == LiquidityEventType.SCORE_UPDATE]
        return [e.new_score for e in score_events[-lookback_events:]]

    def regime_duration(self, asset: str, regime: str) -> int:
        """Count of consecutive events in the specified regime."""
        events = self.regime_changes(asset)
        count = 0
        for e in reversed(events):
            if e.new_regime == regime:
                count += 1
            else:
                break
        return count

    # ── Counts ────────────────────────────────────────────────────

    def event_count(self) -> int:
        return len(self._events)

    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def clear(self) -> None:
        self._events.clear()
        self._snapshots.clear()
        self._current_regimes.clear()
        self._current_scores.clear()

    def summary(self) -> Dict[str, Any]:
        return {
            "total_events": self.event_count(),
            "total_snapshots": self.snapshot_count(),
            "tracked_assets": len(self._current_scores),
            "assets_in_crisis": sum(1 for r in self._current_regimes.values() if r == "CRISIS"),
            "shock_events": len(self.shock_events()),
            "threshold_breaches": len(self.threshold_breaches()),
            "latest_snapshot": self.latest_snapshot().to_dict() if self._snapshots else None,
        }
