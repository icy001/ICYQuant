"""FactorExposure — compute and track factor exposures.

Normalizes exposures and tracks changes over time to detect
drift in factor bets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ExposureProfile:
    """Factor exposure profile at a point in time."""

    entity_id: str
    timestamp: float = 0.0
    exposures: Dict[str, float] = field(default_factory=dict)
    total_gross_exposure: float = 0.0
    total_net_exposure: float = 0.0
    long_bias: float = 0.0
    largest_exposure: Tuple[str, float] = ("", 0.0)
    concentration_hhi: float = 0.0


class FactorExposureTracker:
    """Tracks factor exposures across entities.

    Monitors drift, concentration, and potential breaches
    of factor risk budgets.

    Usage::

        tracker = FactorExposureTracker()
        tracker.update("strategy_A", {"Momentum": 1.2, "Growth": 0.8})
        drift = tracker.detect_drift("strategy_A", lookback=20)
    """

    def __init__(self, budget_limits: Optional[Dict[str, float]] = None):
        self._budget_limits = budget_limits or {}
        self._history: Dict[str, List[ExposureProfile]] = {}

    def update(
        self,
        entity_id: str,
        exposures: Dict[str, float],
        timestamp: Optional[float] = None,
    ) -> ExposureProfile:
        """Record a new factor exposure snapshot.

        Args:
            entity_id: strategy or portfolio id
            exposures: {factor_name: exposure_value}
            timestamp: optional timestamp
        """
        import time

        total_gross = sum(abs(v) for v in exposures.values())
        total_net = sum(v for v in exposures.values())
        long_bias = total_net / max(total_gross, 1e-9) if total_gross > 0 else 0.0

        largest = ("", 0.0)
        for f, v in exposures.items():
            if abs(v) > abs(largest[1]):
                largest = (f, abs(v))

        # HHI concentration
        hhi = 0.0
        if total_gross > 0:
            hhi = sum((abs(v) / total_gross) ** 2 for v in exposures.values())

        profile = ExposureProfile(
            entity_id=entity_id,
            timestamp=timestamp or time.time(),
            exposures=exposures,
            total_gross_exposure=total_gross,
            total_net_exposure=total_net,
            long_bias=long_bias,
            largest_exposure=largest,
            concentration_hhi=hhi,
        )

        if entity_id not in self._history:
            self._history[entity_id] = []
        self._history[entity_id].append(profile)

        # trim history
        if len(self._history[entity_id]) > 1000:
            self._history[entity_id] = self._history[entity_id][-1000:]

        return profile

    def get_current(self, entity_id: str) -> Optional[ExposureProfile]:
        """Get the most recent exposure profile."""
        history = self._history.get(entity_id, [])
        return history[-1] if history else None

    def detect_drift(
        self,
        entity_id: str,
        lookback: int = 20,
        drift_threshold: float = 0.5,
    ) -> Dict[str, float]:
        """Detect significant factor exposure drift.

        Returns factors whose exposure has changed more than
        the drift threshold over the lookback period.
        """
        history = self._history.get(entity_id, [])
        if len(history) < lookback:
            return {}

        past = history[-lookback]
        current = history[-1]

        drifts: Dict[str, float] = {}
        all_factors = set(past.exposures.keys()) | set(current.exposures.keys())

        for f in all_factors:
            past_exp = past.exposures.get(f, 0.0)
            curr_exp = current.exposures.get(f, 0.0)
            change = abs(curr_exp - past_exp)
            if change > drift_threshold:
                drifts[f] = change

        return drifts

    def check_budget_breaches(
        self,
        entity_id: str,
    ) -> List[str]:
        """Check for factor budget limit breaches."""
        current = self.get_current(entity_id)
        if not current:
            return []

        breaches = []
        for factor, limit in self._budget_limits.items():
            exposure = current.exposures.get(factor, 0.0)
            if abs(exposure) > limit:
                breaches.append(
                    f"{factor}: {exposure:.2f} > limit {limit:.2f}"
                )
        return breaches

    def reset(self, entity_id: Optional[str] = None) -> None:
        """Reset tracking history."""
        if entity_id:
            self._history.pop(entity_id, None)
        else:
            self._history.clear()
