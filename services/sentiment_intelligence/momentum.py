"""Sentiment Momentum Engine.

Analyzes the speed and direction of sentiment changes to detect
sentiment acceleration, deceleration, and inflection points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SentimentMomentumResult:
    """Result of sentiment momentum analysis.

    Attributes:
        current: Current sentiment score [0, 100].
        previous: Previous sentiment score [0, 100].
        change: Absolute change (current - previous).
        change_pct: Percentage change relative to previous.
        direction: 'accelerating', 'decelerating', 'reversing', or 'stable'.
        speed: Rate of change per period.
        acceleration: Change in the rate of change (2nd derivative).
        signals: Contributing momentum signals.
        timestamp: Analysis timestamp.
        alert: Whether this change triggers a risk alert.
        description: Human-readable summary.
    """

    current: float = 50.0
    previous: float = 50.0
    change: float = 0.0
    change_pct: float = 0.0
    direction: str = "stable"
    speed: float = 0.0
    acceleration: float = 0.0
    signals: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    alert: bool = False
    description: str = ""

    @property
    def is_rising(self) -> bool:
        return self.change > 0

    @property
    def is_falling(self) -> bool:
        return self.change < 0

    @property
    def is_rapid_change(self) -> bool:
        return abs(self.change) >= 15.0

    @property
    def is_inflection(self) -> bool:
        return self.direction == "reversing"


class SentimentMomentum:
    """Tracks sentiment momentum - speed and acceleration of sentiment shifts.

    Detects rapid sentiment changes, acceleration patterns, and potential
    inflection points where sentiment direction may be reversing.

    Attributes:
        history: Rolling history of sentiment scores.
        change_history: History of score changes.
        max_history: Maximum history length.
        rapid_threshold: Absolute change that triggers rapid flag.
    """

    def __init__(self) -> None:
        self.history: list[float] = []
        self.change_history: list[float] = []
        self.max_history: int = 100
        self.rapid_threshold: float = 15.0

    # --- Calculation ---

    def calculate(self, current: float, previous: float) -> float:
        """Calculate raw sentiment momentum (change).

        Args:
            current: Current sentiment score [0, 100].
            previous: Previous sentiment score [0, 100].

        Returns:
            Momentum value (positive = improving, negative = deteriorating).
        """
        return current - previous

    def analyze(
        self, current: float, previous: float | None = None
    ) -> SentimentMomentumResult:
        """Full momentum analysis with trend and acceleration detection.

        Args:
            current: Current sentiment score [0, 100].
            previous: Previous score; auto-detected from history if None.

        Returns:
            SentimentMomentumResult with detailed analysis.
        """
        if previous is None:
            previous = self.history[-1] if self.history else 50.0

        change = current - previous
        change_pct = (change / previous * 100.0) if previous != 0 else 0.0

        # Update histories
        self.history.append(current)
        self.change_history.append(change)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        if len(self.change_history) > self.max_history:
            self.change_history = self.change_history[-self.max_history:]

        # Determine direction
        direction = self._classify_direction(change)

        # Compute speed
        speed = self._compute_speed()

        # Compute acceleration (2nd derivative)
        acceleration = self._compute_acceleration()

        # Alert detection
        alert = self._detect_alert(change, direction)

        # Signals
        signals: dict[str, float] = {
            "change": change,
            "change_pct": change_pct,
            "speed": speed,
            "acceleration": acceleration,
        }

        # Description
        description = self._generate_description(change, direction, alert)

        return SentimentMomentumResult(
            current=current,
            previous=previous,
            change=change,
            change_pct=change_pct,
            direction=direction,
            speed=speed,
            acceleration=acceleration,
            signals=signals,
            alert=alert,
            description=description,
        )

    def analyze_series(self, scores: list[float]) -> SentimentMomentumResult:
        """Analyze the most recent change in a series of scores.

        Args:
            scores: List of sentiment scores in chronological order.

        Returns:
            SentimentMomentumResult.
        """
        if len(scores) < 2:
            return SentimentMomentumResult(current=scores[0] if scores else 50.0)
        return self.analyze(scores[-1], scores[-2])

    # --- Trend Analysis ---

    def get_trend(self, window: int = 5) -> str:
        """Determine the trend over a given window.

        Args:
            window: Number of recent scores to analyze.

        Returns:
            'rising', 'falling', or 'stable'.
        """
        if len(self.history) < 2:
            return "stable"
        recent = self.history[-window:]
        if len(recent) < 2:
            return "stable"
        mid = len(recent) // 2
        first = sum(recent[:mid]) / mid
        second = sum(recent[mid:]) / (len(recent) - mid)
        diff = second - first
        if diff > 3:
            return "rising"
        elif diff < -3:
            return "falling"
        return "stable"

    def get_reversal_risk(self) -> float:
        """Compute reversal risk [0.0, 1.0] based on momentum patterns.

        Returns:
            Probability of a sentiment reversal.
        """
        if len(self.change_history) < 3:
            return 0.0

        recent = self.change_history[-5:]
        risk = 0.0

        # Large changes increase reversal risk
        if abs(recent[-1]) >= self.rapid_threshold:
            risk += 0.4

        # Deceleration pattern: decreasing magnitude of same-direction changes
        if len(recent) >= 3:
            last3 = recent[-3:]
            if all(c > 0 for c in last3):
                if last3[-1] < last3[-2]:
                    risk += 0.3
            elif all(c < 0 for c in last3):
                if last3[-1] > last3[-2]:
                    risk += 0.3

        # Oscillation: alternating signs
        if len(recent) >= 4:
            signs = [1 if c > 0 else -1 if c < 0 else 0 for c in recent[-4:]]
            if signs[0] != signs[1] and signs[1] != signs[2]:
                risk += 0.2

        return min(1.0, risk)

    # --- Internal ---

    def _classify_direction(self, change: float) -> str:
        """Classify sentiment momentum direction."""
        if abs(change) < 2.0:
            return "stable"
        elif len(self.change_history) >= 2:
            prev = self.change_history[-2]
            if change > 0 and prev > 0 and change > prev:
                return "accelerating"
            elif change > 0 and prev > 0 and change < prev:
                return "decelerating"
            elif change < 0 and prev < 0 and change < prev:
                return "accelerating"
            elif change < 0 and prev < 0 and change > prev:
                return "decelerating"
            elif (change > 0 and prev < 0) or (change < 0 and prev > 0):
                return "reversing"
        if change > 0:
            return "accelerating"
        return "accelerating"

    def _compute_speed(self) -> float:
        """Compute average speed over recent history."""
        if len(self.change_history) < 3:
            return abs(self.change_history[-1]) if self.change_history else 0.0
        return sum(abs(c) for c in self.change_history[-3:]) / 3.0

    def _compute_acceleration(self) -> float:
        """Compute acceleration (change of change)."""
        if len(self.change_history) < 2:
            return 0.0
        return self.change_history[-1] - self.change_history[-2]

    def _detect_alert(self, change: float, direction: str) -> bool:
        """Detect if momentum triggers an alert."""
        return abs(change) >= self.rapid_threshold or direction == "reversing"

    def _generate_description(
        self, change: float, direction: str, alert: bool
    ) -> str:
        """Generate human-readable description."""
        parts: list[str] = []
        if direction == "accelerating":
            dir_word = "rising" if change > 0 else "falling"
            parts.append(f"Sentiment {dir_word} with increasing speed")
        elif direction == "decelerating":
            dir_word = "rise" if change > 0 else "fall"
            parts.append(f"Sentiment {dir_word} losing momentum")
        elif direction == "reversing":
            parts.append("Sentiment direction reversing")
        else:
            parts.append("Sentiment stable")
        parts.append(f"(change: {change:+.1f})")
        if alert:
            parts.append("[ALERT]")
        return " ".join(parts)

    def clear(self) -> None:
        """Reset engine state."""
        self.history.clear()
        self.change_history.clear()
