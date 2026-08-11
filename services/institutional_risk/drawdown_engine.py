"""DrawdownEngine — unified drawdown tracking across all levels.

Tracks drawdown at Strategy, Portfolio, and Capital Pool levels
with recovery analysis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class DrawdownLevel(Enum):
    STRATEGY = auto()
    PORTFOLIO = auto()
    CAPITAL = auto()


@dataclass
class DrawdownRecord:
    """A single drawdown event record."""

    level: DrawdownLevel
    entity_id: str
    peak_value: float = 0.0
    trough_value: float = 0.0
    current_value: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_time: float = 0.0
    trough_time: float = 0.0
    duration_days: float = 0.0
    recovered: bool = False
    recovery_days: Optional[float] = None
    recovery_needed_pct: float = 0.0


@dataclass
class DrawdownState:
    """Continuous drawdown tracking state."""

    peak_value: float = 0.0
    current_value: float = 0.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_time: float = 0.0
    trough_value: float = float("inf")
    in_drawdown: bool = False
    drawdown_start_time: Optional[float] = None


class DrawdownEngine:
    """Unified drawdown tracking engine.

    Tracks drawdown across three levels:
    1. Strategy drawdown
    2. Portfolio drawdown
    3. Capital pool drawdown

    Usage::

        engine = DrawdownEngine()
        engine.update("capital", 100_000_000)
        engine.update("capital", 95_000_000)  # -5% drawdown
        status = engine.get_status("capital")
        print(f"Drawdown: {status.drawdown_pct:.1f}%")
    """

    def __init__(self):
        self._states: Dict[str, DrawdownState] = {}
        self._history: List[DrawdownRecord] = []
        self._entity_levels: Dict[str, DrawdownLevel] = {}

    # ── update ──────────────────────────────────────────────────────

    def update(
        self,
        entity_id: str,
        current_value: float,
        level: DrawdownLevel = DrawdownLevel.CAPITAL,
        timestamp: Optional[float] = None,
    ) -> DrawdownState:
        """Update drawdown tracking for an entity.

        Args:
            entity_id: identifier (strategy_id, portfolio_id, or "capital")
            current_value: current value of the entity
            level: drawdown tracking level
            timestamp: optional timestamp
        """
        ts = timestamp or time.time()
        self._entity_levels[entity_id] = level

        if entity_id not in self._states:
            self._states[entity_id] = DrawdownState(
                peak_value=current_value,
                current_value=current_value,
                peak_time=ts,
                trough_value=current_value,
            )
            return self._states[entity_id]

        state = self._states[entity_id]
        state.current_value = current_value

        # new peak
        if current_value > state.peak_value:
            # if we were in drawdown, record it
            if state.in_drawdown:
                record = self._create_record(entity_id, level, state, ts)
                record.recovered = True
                self._history.append(record)

            state.peak_value = current_value
            state.peak_time = ts
            state.drawdown_pct = 0.0
            state.trough_value = current_value
            state.in_drawdown = False
            state.drawdown_start_time = None
        else:
            if not state.in_drawdown:
                state.in_drawdown = True
                state.drawdown_start_time = ts

            if current_value < state.trough_value:
                state.trough_value = current_value

            dd_pct = (state.peak_value - current_value) / state.peak_value * 100
            state.drawdown_pct = dd_pct
            state.max_drawdown_pct = max(state.max_drawdown_pct, dd_pct)

        return state

    def update_batch(
        self,
        values: Dict[str, Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> Dict[str, DrawdownState]:
        """Update multiple entities at once.

        Args:
            values: {entity_id: {"value": float, "level": DrawdownLevel}}
            timestamp: optional timestamp
        """
        results = {}
        for eid, info in values.items():
            state = self.update(
                entity_id=eid,
                current_value=info["value"],
                level=info.get("level", DrawdownLevel.CAPITAL),
                timestamp=timestamp,
            )
            results[eid] = state
        return results

    # ── queries ─────────────────────────────────────────────────────

    def get_state(self, entity_id: str) -> Optional[DrawdownState]:
        """Get current drawdown state for an entity."""
        return self._states.get(entity_id)

    def get_status(self, entity_id: str) -> Dict[str, Any]:
        """Get drawdown status summary."""
        state = self._states.get(entity_id)
        if not state:
            return {}
        return {
            "peak_value": state.peak_value,
            "current_value": state.current_value,
            "drawdown_pct": state.drawdown_pct,
            "max_drawdown_pct": state.max_drawdown_pct,
            "in_drawdown": state.in_drawdown,
            "recovery_needed_pct": (
                (state.peak_value - state.current_value) / state.current_value * 100
                if state.current_value > 0 and state.in_drawdown else 0.0
            ),
        }

    def get_history(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[DrawdownRecord]:
        """Get drawdown history, optionally filtered by entity."""
        records = self._history
        if entity_id:
            records = [r for r in records if r.entity_id == entity_id]
        return records[-limit:]

    def get_max_drawdown(self, entity_id: str) -> float:
        """Get maximum drawdown percentage for an entity."""
        state = self._states.get(entity_id)
        if not state:
            return 0.0
        return state.max_drawdown_pct

    # ── recovery analysis ───────────────────────────────────────────

    def compute_recovery_needed(self, entity_id: str) -> float:
        """Compute required return to recover from current drawdown.

        recovery_needed% = (peak / current - 1) * 100
        """
        state = self._states.get(entity_id)
        if not state or state.current_value <= 0:
            return 0.0
        if state.current_value >= state.peak_value:
            return 0.0
        return (state.peak_value / state.current_value - 1) * 100

    def estimate_recovery_time(
        self,
        entity_id: str,
        expected_daily_return: float,
        expected_daily_vol: float = 0.0,
    ) -> Optional[float]:
        """Rough estimate of recovery time in trading days.

        Uses expected return and a risk buffer.
        """
        recovery_needed_pct = self.compute_recovery_needed(entity_id)
        if recovery_needed_pct <= 0 or expected_daily_return <= 0:
            return None

        # risk-adjusted daily return
        adj_return = max(expected_daily_return - 0.5 * expected_daily_vol, expected_daily_return * 0.5)
        if adj_return <= 0:
            return None

        return recovery_needed_pct / (adj_return * 100)

    # ── internal ────────────────────────────────────────────────────

    def _create_record(
        self,
        entity_id: str,
        level: DrawdownLevel,
        state: DrawdownState,
        timestamp: float,
    ) -> DrawdownRecord:
        """Create a drawdown record from current state."""
        duration = 0.0
        if state.drawdown_start_time:
            duration = (timestamp - state.drawdown_start_time) / 86400.0  # days

        recovery_needed = 0.0
        if state.current_value > 0 and state.trough_value < state.peak_value:
            recovery_needed = (state.peak_value / state.trough_value - 1) * 100

        return DrawdownRecord(
            level=level,
            entity_id=entity_id,
            peak_value=state.peak_value,
            trough_value=state.trough_value,
            current_value=state.current_value,
            drawdown_pct=state.drawdown_pct,
            max_drawdown_pct=state.max_drawdown_pct,
            peak_time=state.peak_time,
            trough_time=timestamp,
            duration_days=duration,
            recovery_needed_pct=recovery_needed,
        )

    def reset(self) -> None:
        """Reset all drawdown tracking."""
        self._states.clear()
        self._history.clear()
        self._entity_levels.clear()
